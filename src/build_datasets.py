"""从淘宝归因订单工作簿生成可复现的分析数据集。

脚本不会修改原始文件；它会生成商品订单明细、订单汇总、SKU 维表以及简明的数据质量报告。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RAW_DIR = PROJECT_ROOT.parent / "淘宝订单数据by点击日期"
DEFAULT_LABEL_FILE = PROJECT_ROOT.parent / "淘宝sku标签.xlsx"
OUTPUT_DIR = PROJECT_ROOT / "data" / "processed"
QUALITY_DIR = PROJECT_ROOT / "outputs" / "data_quality"

REQUIRED_ORDER_COLUMNS = [
    "点击月份", "点击日期", "点击时间", "结算时间", "创建时间", "付款时间", "淘宝付款时间",
    "品牌名称", "商品ID", "商品标题", "掌柜旺旺", "店铺名称", "商品数量", "商品单价", "类目名称",
    "淘宝订单编号", "淘宝子订单号", "订单状态", "订单类型", "付款金额", "结算金额", "佣金比率",
    "佣金金额", "推广位ID", "推广位名称", "成交平台",
]
REQUIRED_LABEL_COLUMNS = ["商品ID", "商品标题", "一级标签", "二级标签"]
IDENTIFIER_COLUMNS = ["商品ID", "淘宝订单编号", "淘宝子订单号", "推广位ID"]
DATE_COLUMNS = ["点击日期", "点击时间", "结算时间", "创建时间", "付款时间", "淘宝付款时间"]
NUMERIC_COLUMNS = ["商品数量", "商品单价", "付款金额", "结算金额", "佣金比率", "佣金金额"]
NON_INVALID_STATUSES = {"已付款", "已收货"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="生成淘宝归因订单分析数据集。")
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=DEFAULT_RAW_DIR,
        help="存放月度订单工作簿和 SKU 标签工作簿的目录。",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=OUTPUT_DIR,
        help="生成分析 CSV 文件的目录。",
    )
    parser.add_argument(
        "--quality-dir",
        type=Path,
        default=QUALITY_DIR,
        help="生成数据质量报告的目录。",
    )
    parser.add_argument(
        "--label-file",
        type=Path,
        default=DEFAULT_LABEL_FILE,
        help="SKU 标签工作簿路径。",
    )
    return parser.parse_args()


def normalize_identifier(series: pd.Series) -> pd.Series:
    """将 Excel 长 ID 保留为字符串，并移除可能出现的小数后缀。"""
    result = series.astype("string").str.strip()
    return result.str.replace(r"\.0$", "", regex=True)


def classify_order_status(statuses: pd.Series) -> str:
    unique_statuses = set(statuses.dropna().astype(str))
    if unique_statuses == {"已失效"}:
        return "invalid_order"
    if unique_statuses and unique_statuses.issubset(NON_INVALID_STATUSES):
        return "non_invalid_order"
    return "mixed_status_order"


def read_source_files(raw_dir: Path, label_file: Path) -> tuple[list[Path], Path]:
    if not raw_dir.exists():
        raise FileNotFoundError(f"原始数据目录不存在：{raw_dir}")

    workbooks = [p for p in raw_dir.glob("*.xlsx") if not p.name.startswith("~$")]
    order_files = sorted(p for p in workbooks if "淘宝订单" in p.name)
    if not order_files:
        raise FileNotFoundError("未找到文件名含“淘宝订单”的月度工作簿。")
    if not label_file.exists():
        raise FileNotFoundError(f"SKU 标签工作簿不存在：{label_file}")
    return order_files, label_file


def load_orders(order_files: list[Path]) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    parts: list[pd.DataFrame] = []
    source_profile: list[dict[str, Any]] = []

    for path in order_files:
        frame = pd.read_excel(path, dtype={column: "string" for column in IDENTIFIER_COLUMNS})
        missing = [column for column in REQUIRED_ORDER_COLUMNS if column not in frame.columns]
        extra = [column for column in frame.columns if column not in REQUIRED_ORDER_COLUMNS]
        if missing or extra:
            raise ValueError(f"{path.name} 的字段结构不一致：缺失={missing}，多余={extra}")

        frame = frame[REQUIRED_ORDER_COLUMNS].copy()
        for column in IDENTIFIER_COLUMNS:
            frame[column] = normalize_identifier(frame[column])
        frame["source_file"] = path.name
        parts.append(frame)
        source_profile.append({"source_file": path.name, "rows": int(len(frame))})

    return pd.concat(parts, ignore_index=True), source_profile


def prepare_order_lines(order_lines: pd.DataFrame) -> tuple[pd.DataFrame, list[dict[str, Any]], dict[str, bool]]:
    frame = order_lines.copy()
    for column in DATE_COLUMNS:
        frame[column] = pd.to_datetime(frame[column], errors="coerce")
    for column in NUMERIC_COLUMNS:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")

    frame["click_month"] = frame["点击日期"].dt.to_period("M").astype("string")
    coverage: list[dict[str, Any]] = []
    complete_month_map: dict[str, bool] = {}
    for month, group in frame.groupby("click_month", dropna=True, sort=True):
        unique_dates = group["点击日期"].dt.normalize().dropna().unique()
        period = pd.Period(month, freq="M")
        expected_dates = pd.date_range(period.start_time, period.end_time.normalize(), freq="D")
        is_complete = len(unique_dates) == len(expected_dates) and set(unique_dates) == set(expected_dates)
        complete_month_map[str(month)] = is_complete
        coverage.append({
            "click_month": str(month),
            "row_count": int(len(group)),
            "date_min": group["点击日期"].min().date().isoformat(),
            "date_max": group["点击日期"].max().date().isoformat(),
            "observed_days": int(len(unique_dates)),
            "expected_days": int(len(expected_dates)),
            "is_complete_month": is_complete,
        })

    frame["is_complete_month"] = frame["click_month"].map(complete_month_map).fillna(False)
    frame["list_amount"] = frame["商品数量"] * frame["商品单价"]
    frame["payment_to_list_ratio"] = frame["付款金额"].div(frame["list_amount"]).where(frame["list_amount"] > 0)
    frame["is_zero_payment_line"] = frame["付款金额"].eq(0)
    frame["is_invalid_line"] = frame["订单状态"].eq("已失效")
    frame["line_status_group"] = frame["订单状态"].map(
        {"已失效": "invalid_line", "已付款": "non_invalid_line", "已收货": "non_invalid_line"}
    ).fillna("other_status_line")
    # 源数据的淘宝子订单号为空。组合键用于定位“订单 + SKU”，而非替代真实子订单号；
    # 同一组合出现多行时，保留所有行并增加输入顺序序号，使技术行键唯一。
    frame["order_sku_key"] = frame["淘宝订单编号"] + "__" + frame["商品ID"]
    frame["order_sku_line_sequence"] = (
        frame.groupby(["淘宝订单编号", "商品ID"], dropna=False).cumcount().add(1).astype("Int64")
    )
    frame["order_line_key"] = (
        frame["order_sku_key"] + "__" + frame["order_sku_line_sequence"].astype("string")
    )
    frame["click_to_payment_hours"] = (
        frame["付款时间"] - frame["点击时间"]
    ).dt.total_seconds().div(3600)
    return frame, coverage, complete_month_map


def prepare_sku_dimension(label_path: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    labels = pd.read_excel(label_path, dtype={"商品ID": "string"})
    missing = [column for column in REQUIRED_LABEL_COLUMNS if column not in labels.columns]
    extra = [column for column in labels.columns if column not in REQUIRED_LABEL_COLUMNS]
    if missing or extra:
            raise ValueError(f"{label_path.name} 的字段结构不一致：缺失={missing}，多余={extra}")

    labels = labels[REQUIRED_LABEL_COLUMNS].copy()
    labels["商品ID"] = normalize_identifier(labels["商品ID"])
    tag_pairs = labels[["商品ID", "一级标签", "二级标签"]].drop_duplicates()
    tag_pair_counts = tag_pairs.groupby("商品ID").size()
    conflicting_product_ids = tag_pair_counts[tag_pair_counts > 1]
    if not conflicting_product_ids.empty:
        raise ValueError("存在一个商品 ID 对应多个标签组合的情况，需先解决标签映射冲突。")

    sku_dimension = (
        labels.sort_values(["商品ID", "商品标题"])
        .drop_duplicates(subset="商品ID", keep="first")
        .rename(columns={"商品标题": "label_reference_title"})
        .reset_index(drop=True)
    )
    profile = {
        "source_rows": int(len(labels)),
        "unique_product_ids": int(sku_dimension["商品ID"].nunique()),
        "duplicate_product_id_rows": int(labels.duplicated(subset="商品ID").sum()),
        "conflicting_tag_pair_product_ids": int(len(conflicting_product_ids)),
    }
    return sku_dimension, profile


def prepare_orders(order_lines: pd.DataFrame, complete_month_map: dict[str, bool]) -> pd.DataFrame:
    order_id = "淘宝订单编号"
    grouped = order_lines.groupby(order_id, dropna=False)
    orders = grouped.agg(
        order_first_click_time=("点击时间", "min"),
        order_first_payment_time=("付款时间", "min"),
        order_last_payment_time=("付款时间", "max"),
        order_line_count=(order_id, "size"),
        distinct_sku_count=("商品ID", "nunique"),
        total_quantity=("商品数量", "sum"),
        attributed_payment_amount=("付款金额", "sum"),
        list_amount=("list_amount", "sum"),
        invalid_line_count=("is_invalid_line", "sum"),
        zero_payment_line_count=("is_zero_payment_line", "sum"),
        promotion_slot_count=("推广位ID", "nunique"),
        click_month_count=("click_month", "nunique"),
    ).reset_index()

    status_classification = grouped["订单状态"].agg(classify_order_status).rename("order_status_classification")
    month_values = grouped["click_month"].min().rename("order_click_month")
    order_type_values = grouped["订单类型"].agg(
        lambda values: " | ".join(sorted(set(values.dropna().astype(str))))
    ).rename("order_types")
    orders = orders.merge(status_classification, on=order_id).merge(month_values, on=order_id).merge(order_type_values, on=order_id)
    orders["is_complete_month"] = orders["order_click_month"].map(complete_month_map).fillna(False)
    orders["is_zero_payment_order"] = orders["attributed_payment_amount"].eq(0)
    orders["payment_to_list_ratio"] = orders["attributed_payment_amount"].div(orders["list_amount"]).where(orders["list_amount"] > 0)
    orders["is_multi_sku_order"] = orders["distinct_sku_count"].gt(1)
    orders["spans_click_months"] = orders["click_month_count"].gt(1)
    orders["order_click_to_first_payment_hours"] = (
        orders["order_first_payment_time"] - orders["order_first_click_time"]
    ).dt.total_seconds().div(3600)
    return orders.sort_values(["order_first_click_time", order_id]).reset_index(drop=True)


def make_quality_summary(
    order_lines: pd.DataFrame,
    orders: pd.DataFrame,
    source_profile: list[dict[str, Any]],
    coverage: list[dict[str, Any]],
    sku_profile: dict[str, Any],
) -> dict[str, Any]:
    exact_duplicate_lines = int(order_lines.duplicated().sum())
    order_sku_counts = order_lines.groupby(["淘宝订单编号", "商品ID"], dropna=False).size()
    slot_name_counts = order_lines.groupby("推广位ID", dropna=False)["推广位名称"].nunique(dropna=False)
    payment_over_list = int((order_lines["付款金额"] > order_lines["list_amount"]).sum())
    negative_click_to_payment = int(order_lines["click_to_payment_hours"].lt(0).sum())
    unmatched_lines = int(order_lines["一级标签"].isna().sum())
    null_rates = {
        column: round(float(order_lines[column].isna().mean() * 100), 2)
        for column in REQUIRED_ORDER_COLUMNS
    }
    check_results = {
        "all_monthly_schemas_matched": True,
        "no_exact_duplicate_order_lines": exact_duplicate_lines == 0,
        "no_negative_quantities": bool(order_lines["商品数量"].ge(0).all()),
        "no_negative_attributed_payments": bool(order_lines["付款金额"].ge(0).all()),
        "payment_never_exceeds_list_amount": payment_over_list == 0,
        "all_order_lines_matched_to_sku_tags": unmatched_lines == 0,
        "no_conflicting_sku_tag_pairs": sku_profile["conflicting_tag_pair_product_ids"] == 0,
        "derived_order_line_key_is_unique": bool(order_lines["order_line_key"].is_unique),
    }
    return {
        "source_files": source_profile,
        "source_month_coverage": coverage,
        "line_table": {
            "row_count": int(len(order_lines)),
            "unique_order_ids": int(order_lines["淘宝订单编号"].nunique()),
            "unique_product_ids": int(order_lines["商品ID"].nunique()),
            "unique_promotion_slots": int(order_lines["推广位ID"].nunique()),
            "date_min": order_lines["点击日期"].min().date().isoformat(),
            "date_max": order_lines["点击日期"].max().date().isoformat(),
            "exact_duplicate_rows": exact_duplicate_lines,
            "duplicate_order_sku_pairs": int((order_sku_counts > 1).sum()),
            "unique_derived_order_line_keys": int(order_lines["order_line_key"].nunique()),
            "zero_payment_rows": int(order_lines["is_zero_payment_line"].sum()),
            "negative_click_to_payment_rows": negative_click_to_payment,
            "payment_exceeds_list_amount_rows": payment_over_list,
            "promotion_ids_with_multiple_names": int((slot_name_counts > 1).sum()),
            "null_rates_percent": null_rates,
        },
        "order_table": {
            "row_count": int(len(orders)),
            "multi_line_orders": int(orders["order_line_count"].gt(1).sum()),
            "multi_sku_orders": int(orders["is_multi_sku_order"].sum()),
            "mixed_status_orders": int(orders["order_status_classification"].eq("mixed_status_order").sum()),
            "invalid_orders": int(orders["order_status_classification"].eq("invalid_order").sum()),
            "non_invalid_orders": int(orders["order_status_classification"].eq("non_invalid_order").sum()),
            "zero_payment_orders": int(orders["is_zero_payment_order"].sum()),
            "orders_spanning_click_months": int(orders["spans_click_months"].sum()),
        },
        "sku_dimension": sku_profile | {"order_line_tag_match_rate_percent": round(100 * (1 - unmatched_lines / len(order_lines)), 2)},
        "checks": check_results,
    }


def render_markdown_report(summary: dict[str, Any]) -> str:
    line = summary["line_table"]
    order = summary["order_table"]
    sku = summary["sku_dimension"]
    check_labels = {
        "all_monthly_schemas_matched": "月度订单文件字段结构一致",
        "no_exact_duplicate_order_lines": "不存在完全重复的商品订单明细",
        "no_negative_quantities": "不存在负商品数量",
        "no_negative_attributed_payments": "不存在负归因付款金额",
        "payment_never_exceeds_list_amount": "付款金额不高于标价金额",
        "all_order_lines_matched_to_sku_tags": "所有订单明细均匹配 SKU 标签",
        "no_conflicting_sku_tag_pairs": "不存在冲突的 SKU 标签组合",
        "derived_order_line_key_is_unique": "衍生技术行键唯一",
    }
    coverage_rows = "\n".join(
        f"| {row['click_month']} | {row['date_min']} | {row['date_max']} | {row['observed_days']} / {row['expected_days']} | {'是' if row['is_complete_month'] else '否'} |"
        for row in summary["source_month_coverage"]
    )
    checks_rows = "\n".join(
        f"| {check_labels[name]} | {'通过' if result else '需复核'} |" for name, result in summary["checks"].items()
    )
    null_rows = "\n".join(
        f"| {field} | {rate:.2f}% |" for field, rate in line["null_rates_percent"].items()
    )
    return f"""# 数据质量报告

本报告由 `src/build_datasets.py` 自动生成，用于描述归因订单提取数据的质量；它不验证源字段的商业含义。

## 数据集与粒度

- 商品订单明细数：**{line['row_count']:,}**
- 去重后的淘宝订单编号数：**{line['unique_order_ids']:,}**
- 商品 ID 数：**{line['unique_product_ids']:,}**
- 推广位数：**{line['unique_promotion_slots']:,}**
- 点击日期范围：**{line['date_min']}** 至 **{line['date_max']}**
- 订单汇总记录数：**{order['row_count']:,}**

原始数据的每一行是一条归因商品订单明细；`orders_clean.csv` 按淘宝订单编号汇总。

## 月度数据覆盖

| 点击月份 | 起始日期 | 结束日期 | 已观测 / 应有天数 | 是否完整月 |
|---|---|---|---:|---|
{coverage_rows}

## 关键质量概况

| 检查项 | 数值 |
|---|---:|
| 完全重复的商品订单明细 | {line['exact_duplicate_rows']:,} |
| 重复的“订单编号 + 商品 ID”组合 | {line['duplicate_order_sku_pairs']:,} |
| 唯一的衍生技术行键 | {line['unique_derived_order_line_keys']:,} |
| 多商品明细订单 | {order['multi_line_orders']:,} |
| 多 SKU 订单 | {order['multi_sku_orders']:,} |
| 混合状态订单 | {order['mixed_status_orders']:,} |
| 完全失效订单 | {order['invalid_orders']:,} |
| 非失效订单 | {order['non_invalid_orders']:,} |
| 零付款商品明细 | {line['zero_payment_rows']:,} |
| 零付款订单 | {order['zero_payment_orders']:,} |
| 点击至付款时长为负的明细 | {line['negative_click_to_payment_rows']:,} |
| 付款金额高于标价金额的明细 | {line['payment_exceeds_list_amount_rows']:,} |
| SKU 标签匹配率 | {sku['order_line_tag_match_rate_percent']:.2f}% |

## 源字段缺失率

| 源字段 | 缺失率 |
|---|---:|
{null_rows}

## 自动检查结果

| 检查项 | 状态 |
|---|---|
{checks_rows}

## 解释边界

- `付款金额`仅作为归因付款金额使用，不代表最终营收、结算收入、利润或佣金。
- 结算和佣金相关字段为空，不能进行结算收入、利润、佣金或 ROI 分析。
- 缺少曝光、完整点击量和投放成本，不能分析点击率、完整转化率或 ROI。
- 不完整月份不能用于普通月度环比。
- 混合状态订单保留为独立类别，不被强行划为成功或失效订单。
- 源数据的淘宝子订单号为空。`order_sku_key` 与 `order_line_key` 仅用于技术定位和复现，不能视为原始子订单号；重复的“订单编号 + 商品 ID”组合不会被删除。
"""


def export_outputs(
    order_lines: pd.DataFrame,
    orders: pd.DataFrame,
    sku_dimension: pd.DataFrame,
    summary: dict[str, Any],
    output_dir: Path,
    quality_dir: Path,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    quality_dir.mkdir(parents=True, exist_ok=True)
    order_lines.to_csv(output_dir / "order_lines_clean.csv", index=False, encoding="utf-8-sig")
    orders.to_csv(output_dir / "orders_clean.csv", index=False, encoding="utf-8-sig")
    sku_dimension.to_csv(output_dir / "sku_dimension.csv", index=False, encoding="utf-8-sig")
    (quality_dir / "data_quality_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (quality_dir / "data_quality_report.md").write_text(render_markdown_report(summary), encoding="utf-8")


def main() -> None:
    args = parse_args()
    order_files, label_file = read_source_files(args.raw_dir.resolve(), args.label_file.resolve())
    raw_orders, source_profile = load_orders(order_files)
    order_lines, coverage, complete_month_map = prepare_order_lines(raw_orders)
    sku_dimension, sku_profile = prepare_sku_dimension(label_file)
    order_lines = order_lines.merge(sku_dimension, on="商品ID", how="left", validate="many_to_one")
    orders = prepare_orders(order_lines, complete_month_map)
    summary = make_quality_summary(order_lines, orders, source_profile, coverage, sku_profile)
    export_outputs(order_lines, orders, sku_dimension, summary, args.output_dir.resolve(), args.quality_dir.resolve())

    print(f"已写入 {len(order_lines):,} 条商品订单明细：{args.output_dir.resolve()}")
    print(f"已写入 {len(orders):,} 条订单汇总记录：{args.output_dir.resolve()}")
    print(f"数据质量报告：{args.quality_dir.resolve() / 'data_quality_report.md'}")


if __name__ == "__main__":
    main()
