"""Lightweight reproducibility checks for generated analysis artifacts.

Run after ``build_datasets.py`` and ``analyze_performance.py``. The test does
not require raw workbooks, so a reviewer can inspect aggregate-output integrity
without receiving the source data.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
ANALYSIS_DIR = PROJECT_ROOT / "outputs" / "analysis"
FIGURES_DIR = PROJECT_ROOT / "outputs" / "figures"


def main() -> None:
    lines = pd.read_csv(PROCESSED_DIR / "order_lines_clean.csv", dtype={"淘宝订单编号": "string"})
    orders = pd.read_csv(PROCESSED_DIR / "orders_clean.csv", dtype={"淘宝订单编号": "string"})
    monthly = pd.read_csv(ANALYSIS_DIR / "monthly_performance.csv")
    tags = pd.read_csv(ANALYSIS_DIR / "tag_performance.csv")
    promotions = pd.read_csv(ANALYSIS_DIR / "promotion_performance.csv")
    summary = json.loads((ANALYSIS_DIR / "analysis_summary.json").read_text(encoding="utf-8"))

    assert len(lines) == summary["scope"]["order_line_count"]
    assert len(orders) == summary["scope"]["attributed_order_count"]
    assert round(lines["付款金额"].sum(), 2) == round(orders["attributed_payment_amount"].sum(), 2)
    assert round(lines["付款金额"].sum(), 2) == round(tags["attributed_payment_amount"].sum(), 2)
    assert round(lines["付款金额"].sum(), 2) == round(monthly["attributed_payment_amount"].sum(), 2)
    assert monthly.loc[~monthly["is_complete_month"], "payment_amount_mom"].isna().all()

    eligible = promotions.loc[promotions["is_main_comparison_eligible"]]
    assert eligible["attributed_order_count"].ge(30).all()
    assert eligible["active_days"].ge(7).all()

    for figure in [
        "monthly_attributed_payment_amount.png",
        "tag_scale_risk_matrix.png",
        "promotion_scale_risk_matrix.png",
    ]:
        path = FIGURES_DIR / figure
        assert path.exists() and path.stat().st_size > 0

    print("Pipeline checks passed.")


if __name__ == "__main__":
    main()
