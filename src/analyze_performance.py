"""Generate reproducible aggregate analyses for Taobao attributed-order data.

The script reads only the processed datasets produced by ``build_datasets.py``.
It writes aggregate tables and figures; it does not edit raw workbooks or infer
actual revenue, settlement, profit, advertising cost, ROI, or causal effects.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable

import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter, PercentFormatter


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT_DIR = PROJECT_ROOT / "data" / "processed"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "outputs" / "analysis"
DEFAULT_FIGURES_DIR = PROJECT_ROOT / "outputs" / "figures"
ID_DTYPES = {"商品ID": "string", "淘宝订单编号": "string", "推广位ID": "string"}
NON_INVALID_STATUS = "non_invalid_order"
INVALID_STATUS = "invalid_order"
MIXED_STATUS = "mixed_status_order"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="生成商品、推广位和订单风险的聚合分析结果。")
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--figures-dir", type=Path, default=DEFAULT_FIGURES_DIR)
    return parser.parse_args()


def safe_divide(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    return numerator.div(denominator).where(denominator.ne(0))


def load_inputs(input_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    line_path = input_dir / "order_lines_clean.csv"
    order_path = input_dir / "orders_clean.csv"
    if not line_path.exists() or not order_path.exists():
        raise FileNotFoundError("缺少处理后数据。请先运行 src/build_datasets.py。")

    lines = pd.read_csv(line_path, dtype=ID_DTYPES, parse_dates=["点击日期", "点击时间", "付款时间"])
    orders = pd.read_csv(order_path, dtype={"淘宝订单编号": "string"})
    orders["order_first_click_time"] = pd.to_datetime(orders["order_first_click_time"])
    return lines, orders


def add_order_status(lines: pd.DataFrame, orders: pd.DataFrame) -> pd.DataFrame:
    status = orders[["淘宝订单编号", "order_status_classification"]]
    enriched = lines.merge(status, on="淘宝订单编号", how="left", validate="many_to_one")
    if enriched["order_status_classification"].isna().any():
        raise ValueError("存在无法匹配订单状态分类的商品订单明细。")
    return enriched


def summarize_group(frame: pd.DataFrame, dimensions: list[str]) -> pd.DataFrame:
    """Summarize a dimension at line grain while calculating order risk at order grain."""
    grouped = frame.groupby(dimensions, dropna=False)
    result = grouped.agg(
        order_line_count=("order_line_key", "size"),
        attributed_order_count=("淘宝订单编号", "nunique"),
        sku_count=("商品ID", "nunique"),
        item_quantity=("商品数量", "sum"),
        attributed_payment_amount=("付款金额", "sum"),
        zero_payment_line_count=("is_zero_payment_line", "sum"),
        active_days=("点击日期", "nunique"),
    )

    status_orders = (
        frame.groupby(dimensions + ["order_status_classification"], dropna=False)["淘宝订单编号"]
        .nunique()
        .unstack(fill_value=0)
    )
    for status in [INVALID_STATUS, NON_INVALID_STATUS, MIXED_STATUS]:
        if status not in status_orders:
            status_orders[status] = 0
    status_orders = status_orders[[INVALID_STATUS, NON_INVALID_STATUS, MIXED_STATUS]].rename(
        columns={
            INVALID_STATUS: "invalid_order_count",
            NON_INVALID_STATUS: "non_invalid_order_count",
            MIXED_STATUS: "mixed_status_order_count",
        }
    )
    result = result.join(status_orders).reset_index()
    result["classified_order_count"] = (
        result["invalid_order_count"] + result["non_invalid_order_count"]
    )
    result["invalid_order_rate"] = safe_divide(
        result["invalid_order_count"], result["classified_order_count"]
    )
    result["zero_payment_line_rate"] = safe_divide(
        result["zero_payment_line_count"], result["order_line_count"]
    )
    result["attributed_payment_amount_per_active_day"] = safe_divide(
        result["attributed_payment_amount"], result["active_days"]
    )
    return result


def add_scale_risk_matrix(
    frame: pd.DataFrame,
    amount_column: str = "attributed_payment_amount",
    risk_column: str = "invalid_order_rate",
    risk_threshold: float | None = None,
) -> pd.DataFrame:
    result = frame.copy()
    amount_threshold = result[amount_column].median()
    risk_threshold = result[risk_column].median() if risk_threshold is None else risk_threshold
    result["scale_threshold_amount"] = amount_threshold
    result["risk_threshold_rate"] = risk_threshold
    result["scale_risk_quadrant"] = "low_scale_low_risk"
    result.loc[(result[amount_column] >= amount_threshold) & (result[risk_column] >= risk_threshold), "scale_risk_quadrant"] = "high_scale_high_risk"
    result.loc[(result[amount_column] >= amount_threshold) & (result[risk_column] < risk_threshold), "scale_risk_quadrant"] = "high_scale_low_risk"
    result.loc[(result[amount_column] < amount_threshold) & (result[risk_column] >= risk_threshold), "scale_risk_quadrant"] = "low_scale_high_risk"
    return result


def create_monthly_performance(lines: pd.DataFrame, orders: pd.DataFrame) -> pd.DataFrame:
    line_month = (
        lines.groupby(["click_month", "is_complete_month"], dropna=False)
        .agg(
            order_line_count=("order_line_key", "size"),
            item_quantity=("商品数量", "sum"),
            attributed_payment_amount=("付款金额", "sum"),
            zero_payment_line_count=("is_zero_payment_line", "sum"),
        )
        .reset_index()
    )
    order_month = orders.groupby(["order_click_month", "is_complete_month"], dropna=False).agg(
        attributed_order_count=("淘宝订单编号", "nunique"),
        invalid_order_count=("order_status_classification", lambda value: int(value.eq(INVALID_STATUS).sum())),
        non_invalid_order_count=("order_status_classification", lambda value: int(value.eq(NON_INVALID_STATUS).sum())),
        mixed_status_order_count=("order_status_classification", lambda value: int(value.eq(MIXED_STATUS).sum())),
    ).reset_index().rename(columns={"order_click_month": "click_month"})
    monthly = line_month.merge(
        order_month.drop(columns="is_complete_month"), on="click_month", how="left", validate="one_to_one"
    ).sort_values("click_month").reset_index(drop=True)
    monthly["classified_order_count"] = monthly["invalid_order_count"] + monthly["non_invalid_order_count"]
    monthly["invalid_order_rate"] = safe_divide(monthly["invalid_order_count"], monthly["classified_order_count"])
    monthly["zero_payment_line_rate"] = safe_divide(monthly["zero_payment_line_count"], monthly["order_line_count"])
    monthly["payment_amount_mom"] = pd.NA
    for index in range(1, len(monthly)):
        is_valid_comparison = bool(monthly.loc[index, "is_complete_month"]) and bool(
            monthly.loc[index - 1, "is_complete_month"]
        )
        if is_valid_comparison:
            monthly.loc[index, "payment_amount_mom"] = (
                monthly.loc[index, "attributed_payment_amount"]
                / monthly.loc[index - 1, "attributed_payment_amount"]
                - 1
            )
    return monthly


def format_figure_defaults() -> None:
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["figure.dpi"] = 150


def save_monthly_figure(monthly: pd.DataFrame, figures_dir: Path) -> None:
    fig, axis = plt.subplots(figsize=(10, 5.5))
    colors = ["#4E79A7" if complete else "#B7B7B7" for complete in monthly["is_complete_month"]]
    bars = axis.bar(monthly["click_month"], monthly["attributed_payment_amount"], color=colors)
    for bar, complete in zip(bars, monthly["is_complete_month"], strict=True):
        if not complete:
            bar.set_hatch("//")
    axis.yaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{value / 1_000_000:.1f}M"))
    axis.set_title("Monthly attributed payment amount by click month")
    axis.set_ylabel("Attributed payment amount")
    axis.set_xlabel("Click month")
    axis.grid(axis="y", alpha=0.25)
    axis.text(
        0.01,
        -0.22,
        "Hatched bars are incomplete months and are excluded from ordinary month-over-month comparisons.",
        transform=axis.transAxes,
        fontsize=9,
    )
    fig.tight_layout()
    fig.savefig(figures_dir / "monthly_attributed_payment_amount.png", bbox_inches="tight")
    plt.close(fig)


def save_scale_risk_figure(
    frame: pd.DataFrame,
    label_column: str,
    title: str,
    filename: str,
    figures_dir: Path,
    annotate_count: int = 10,
) -> None:
    fig, axis = plt.subplots(figsize=(10, 6.2))
    color_map = {
        "high_scale_high_risk": "#E15759",
        "high_scale_low_risk": "#59A14F",
        "low_scale_high_risk": "#F28E2B",
        "low_scale_low_risk": "#4E79A7",
    }
    for quadrant, subset in frame.groupby("scale_risk_quadrant"):
        axis.scatter(
            subset["attributed_payment_amount"],
            subset["invalid_order_rate"],
            s=subset["attributed_order_count"].clip(lower=1).pow(0.5) * 10,
            alpha=0.72,
            color=color_map[quadrant],
            label=quadrant,
            edgecolors="white",
            linewidths=0.7,
        )
    axis.axvline(frame["scale_threshold_amount"].iloc[0], color="#7F7F7F", linestyle="--", linewidth=1)
    axis.axhline(frame["risk_threshold_rate"].iloc[0], color="#7F7F7F", linestyle="--", linewidth=1)
    labels = frame.nlargest(annotate_count, "attributed_payment_amount")
    for _, row in labels.iterrows():
        axis.annotate(
            str(row[label_column]),
            (row["attributed_payment_amount"], row["invalid_order_rate"]),
            xytext=(4, 4),
            textcoords="offset points",
            fontsize=8,
        )
    axis.xaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{value / 1_000_000:.1f}M"))
    axis.yaxis.set_major_formatter(PercentFormatter(1, decimals=0))
    axis.set_title(title)
    axis.set_xlabel("Attributed payment amount")
    axis.set_ylabel("Invalid order rate (classified orders only)")
    axis.grid(alpha=0.2)
    axis.legend(title="Scale-risk quadrant", fontsize=8)
    fig.tight_layout()
    fig.savefig(figures_dir / filename, bbox_inches="tight")
    plt.close(fig)


def to_records(frame: pd.DataFrame, columns: Iterable[str], limit: int) -> list[dict[str, object]]:
    subset = frame.loc[:, list(columns)].head(limit).copy()
    for column in subset.select_dtypes(include="number"):
        subset[column] = subset[column].round(4)
    return subset.to_dict(orient="records")


def main() -> None:
    args = parse_args()
    lines, orders = load_inputs(args.input_dir.resolve())
    lines = add_order_status(lines, orders)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.figures_dir.mkdir(parents=True, exist_ok=True)
    format_figure_defaults()

    monthly = create_monthly_performance(lines, orders)
    primary_invalid_rate = (
        orders["order_status_classification"].eq(INVALID_STATUS).sum()
        / orders["order_status_classification"].isin([INVALID_STATUS, NON_INVALID_STATUS]).sum()
    )
    tags = summarize_group(lines, ["一级标签", "二级标签"])
    tags["attributed_payment_amount_share"] = safe_divide(
        tags["attributed_payment_amount"], pd.Series(tags["attributed_payment_amount"].sum(), index=tags.index)
    )
    tags = add_scale_risk_matrix(tags, risk_threshold=primary_invalid_rate).sort_values(
        "attributed_payment_amount", ascending=False
    )

    sku = summarize_group(lines, ["商品ID", "label_reference_title", "一级标签", "二级标签"])
    sku["attributed_payment_amount_share"] = safe_divide(
        sku["attributed_payment_amount"], pd.Series(sku["attributed_payment_amount"].sum(), index=sku.index)
    )
    sku = add_scale_risk_matrix(sku, risk_threshold=primary_invalid_rate).sort_values(
        "attributed_payment_amount", ascending=False
    )

    promotions = summarize_group(lines, ["推广位ID", "推广位名称"])
    promotions["attributed_payment_amount_share"] = safe_divide(
        promotions["attributed_payment_amount"], pd.Series(promotions["attributed_payment_amount"].sum(), index=promotions.index)
    )
    promotions["is_main_comparison_eligible"] = (
        promotions["attributed_order_count"].ge(30) & promotions["active_days"].ge(7)
    )
    eligible_promotions = promotions.loc[promotions["is_main_comparison_eligible"]].copy()
    eligible_promotions = add_scale_risk_matrix(
        eligible_promotions, risk_threshold=primary_invalid_rate
    )
    promotions = promotions.merge(
        eligible_promotions[["推广位ID", "scale_threshold_amount", "risk_threshold_rate", "scale_risk_quadrant"]],
        on="推广位ID",
        how="left",
        validate="one_to_one",
    ).sort_values("attributed_payment_amount", ascending=False)

    monthly.to_csv(args.output_dir / "monthly_performance.csv", index=False, encoding="utf-8-sig")
    tags.to_csv(args.output_dir / "tag_performance.csv", index=False, encoding="utf-8-sig")
    sku.to_csv(args.output_dir / "sku_performance.csv", index=False, encoding="utf-8-sig")
    promotions.to_csv(args.output_dir / "promotion_performance.csv", index=False, encoding="utf-8-sig")

    save_monthly_figure(monthly, args.figures_dir)
    save_scale_risk_figure(
        tags,
        "一级标签",
        "Tag scale and invalid-order risk (all months, attributed-order data)",
        "tag_scale_risk_matrix.png",
        args.figures_dir,
        annotate_count=5,
    )
    save_scale_risk_figure(
        eligible_promotions,
        "推广位名称",
        "Promotion scale and invalid-order risk (eligible promotions only)",
        "promotion_scale_risk_matrix.png",
        args.figures_dir,
    )

    summary = {
        "scope": {
            "order_line_count": int(len(lines)),
            "attributed_order_count": int(orders["淘宝订单编号"].nunique()),
            "attributed_payment_amount": round(float(lines["付款金额"].sum()), 2),
            "item_quantity": int(lines["商品数量"].sum()),
            "complete_months": monthly.loc[monthly["is_complete_month"], "click_month"].tolist(),
            "incomplete_months": monthly.loc[~monthly["is_complete_month"], "click_month"].tolist(),
        },
        "risk": {
            "primary_invalid_order_rate": round(float(primary_invalid_rate), 4),
            "zero_payment_line_rate": round(float(lines["is_zero_payment_line"].mean()), 4),
            "mixed_status_order_count": int(orders["order_status_classification"].eq(MIXED_STATUS).sum()),
        },
        "top_tags_by_attributed_payment_amount": to_records(
            tags,
            ["一级标签", "二级标签", "attributed_payment_amount", "attributed_order_count", "invalid_order_rate", "zero_payment_line_rate"],
            10,
        ),
        "top_promotions_by_attributed_payment_amount": to_records(
            promotions,
            ["推广位ID", "推广位名称", "attributed_payment_amount", "attributed_order_count", "active_days", "invalid_order_rate", "is_main_comparison_eligible"],
            10,
        ),
        "high_scale_high_risk_tags": to_records(
            tags.loc[tags["scale_risk_quadrant"].eq("high_scale_high_risk")].sort_values("attributed_payment_amount", ascending=False),
            ["一级标签", "二级标签", "attributed_payment_amount", "attributed_order_count", "invalid_order_rate"],
            10,
        ),
        "high_scale_high_risk_eligible_promotions": to_records(
            promotions.loc[promotions["scale_risk_quadrant"].eq("high_scale_high_risk")].sort_values("attributed_payment_amount", ascending=False),
            ["推广位ID", "推广位名称", "attributed_payment_amount", "attributed_order_count", "active_days", "invalid_order_rate"],
            10,
        ),
    }
    (args.output_dir / "analysis_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"已写入聚合结果：{args.output_dir.resolve()}")
    print(f"已写入图表：{args.figures_dir.resolve()}")


if __name__ == "__main__":
    main()
