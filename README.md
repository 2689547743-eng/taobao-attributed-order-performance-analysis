# Taobao Attributed Order Performance Analysis

Portfolio project that turns seven monthly Taobao attributed-order extracts and a SKU-tag reference table into reproducible product, promotion-slot, and order-risk analysis.

## Business question

How can attributed order-line data be used to prioritize product-tag and promotion-slot reviews while keeping order failures and data limitations visible?

## Scope and definitions

| Item | Verified value |
|---|---:|
| Order lines | 31,036 |
| Distinct Taobao order IDs | 27,521 |
| SKU IDs | 65 |
| Promotion slots | 253 |
| Click-date range | 2020-11-14 to 2021-05-31 |
| Attributed payment amount | 4,072,492.00 |
| Primary invalid-order rate | 6.86% |
| Zero-payment line rate | 8.02% |

Each source row is an attributed **product order line**, not an independent order. `付款金额` is referred to throughout as **attributed payment amount**; it is not revenue, settlement income, commission, profit, or ROI.

November 2020 and March 2021 are incomplete months and are excluded from ordinary month-over-month comparisons.

## Verified findings

- Probiotic-tagged lines account for 2.52M in attributed payment amount (61.8% of the total) with a 5.72% invalid-order rate. Sleep-tagged lines account for 1.14M (28.0%) with a 7.56% invalid-order rate and a 17.34% zero-payment line rate.
- April and May 2021 are both complete months. Attributed payment amount decreased 11.4% in May, while the zero-payment line rate rose from 4.0% to 23.7%. This is a diagnostic signal, not evidence of a demand change or a causal effect.
- Among promotion slots meeting the minimum comparison rule (at least 30 attributed orders and 7 active days), `VesleepI1`, `VsleepI31`, and `TsleepI6` have large attributed-payment scale and invalid-order rates above the overall 6.86% benchmark. They are review candidates, not budget recommendations.

See the Chinese [analysis findings](docs/analysis_findings.md), [business recommendations](docs/business_recommendations.md), and [validation report](docs/analysis_validation.md) for evidence and caveats.

![Monthly attributed payment amount](outputs/figures/monthly_attributed_payment_amount.png)

![Tag scale-risk matrix](outputs/figures/tag_scale_risk_matrix.png)

![Promotion scale-risk matrix](outputs/figures/promotion_scale_risk_matrix.png)

## Repository structure

```text
├── data/
│   ├── raw/                 # Local-only source-data instructions
│   └── processed/           # Local-only generated analysis tables
├── docs/                    # Metric definitions, quality notes, findings, validation
├── notebooks/               # Reproducible preparation and analysis walkthroughs
├── outputs/
│   ├── analysis/            # Aggregate CSV outputs and summary JSON
│   ├── data_quality/        # Generated quality report and summary
│   └── figures/             # Aggregate charts
├── src/
│   ├── build_datasets.py    # Builds three clean local analysis tables
│   └── analyze_performance.py
├── tests/
└── requirements.txt
```

## Reproduce locally

Raw workbooks are intentionally excluded from this public repository because redistribution permission has not been established. Place the seven monthly source files in a local `淘宝订单数据by点击日期` directory and keep `淘宝sku标签.xlsx` locally available.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

python src\build_datasets.py `
  --raw-dir "..\淘宝订单数据by点击日期" `
  --label-file "..\淘宝sku标签.xlsx"

python src\analyze_performance.py
python tests\test_pipeline.py
```

The preparation script creates the following local files:

- `data/processed/order_lines_clean.csv`
- `data/processed/orders_clean.csv`
- `data/processed/sku_dimension.csv`

## Important limitations

- Settlement time, settlement amount, commission amount, and Taobao sub-order ID are 100% missing in the source files. The project does not calculate settlement, commission, profit, or ROI.
- Exposure, total clicks, and advertising cost are not available. The project does not calculate click-through rate, full conversion rate, advertising efficiency, or causal promotion impact.
- User IDs are unavailable. Retention, repeat purchase, RFM, and user profiles are out of scope.
- “Non-invalid” does not mean a completed transaction; mixed-status orders are displayed separately and excluded from the primary invalid-order-rate denominator.

## 工程中文摘要

本项目以归因商品订单明细为事实来源，先完成数据质量检查和订单级状态分类，再输出商品标签、推广位和失效风险的聚合结果。公开仓库不包含原始 Excel 或处理后明细数据；所有业务建议均为排查或测试方向，不宣称已实现的提升效果。

## Tools

Python, Pandas, Matplotlib, Jupyter, Tableau (legacy exploratory workbook).
