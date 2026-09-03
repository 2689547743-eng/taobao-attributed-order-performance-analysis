# Tableau 工作表分析记录

本文只整理 Tableau 工作表中展示的字段、图表和说明文字，不新增计算、结论或图表。

## 1. 品类排行

截图：[01_category_ranking.png](../outputs/tableau_worksheets/01_category_ranking.png)

- 行：一级标签。
- 列：付款金额、商品数量。
- 颜色：点击月份。
- 工作表说明：**“益生菌产品销量和销售金额遥遥领先，是最受欢迎的产品。”**

## 2. 近两个月付费排行

截图：[02_recent_two_months_payment_ranking.png](../outputs/tableau_worksheets/02_recent_two_months_payment_ranking.png)

- 行：推广位名称。
- 列：付款金额、商品数量。
- 过滤：点击月份为四月、五月。
- 工作表说明：**“应该重点关注一下推广位：vprol526，vprol524，vprol525，vprol555，vprol54，vprol522，vprol529，vprol556。”**

## 3. 商品 1500 秒决策时间与付款金额

| 工作表 | 截图 | Tableau 展示内容 |
|---|---|---|
| 商品1500秒决策排名 | [09](../outputs/tableau_worksheets/09_product_1500_second_ranking.png) | 按一级标签展示平均值“点击-创建（不包含负值）”与付款金额，并按点击月份着色。 |
| 商品1500秒决策时间和付款金额 | [10](../outputs/tableau_worksheets/10_product_time_and_payment.png) | 按点击月份展示一级标签的平均点击-创建时间与付款金额。 |
| 商品1500秒决策时间和付款金额散点图 | [03](../outputs/tableau_worksheets/03_product_1500_second_scatter.png) | 横轴为付款金额，纵轴为平均点击-创建（不包含负值），按一级标签着色。工作表显示 116 的参考线。 |

散点图中的工作表说明：**“点击到创建的时间最好控制在116左右，可能会让增加商品销量。”**

## 4. 推广位 1500 秒决策排名

截图：[08_promotion_1500_second_ranking.png](../outputs/tableau_worksheets/08_promotion_1500_second_ranking.png)

- 行：推广位名称。
- 列：平均值“点击-创建（不包含负值）”、付款金额。
- 颜色：点击月份为四月、五月。

## 5. 用户成交时间分布

截图：[04_transaction_time_distribution.png](../outputs/tableau_worksheets/04_transaction_time_distribution.png)

- 列：小时（点击时间）。
- 行：一级标签、平均点击-创建（不包含负值）、付款金额。
- 图中对比睡眠和益生菌两类标签。
- 工作表说明：**“益生菌的主要成交时间在19点到早上两点，应该在这个时间段加强投放。”**
- 工作表说明：**“睡眠产品的主要成交时间在23点到早上5点，应该在这个时间段加强投送。”**

## 6. 时间差数据桶

| 工作表 | 截图 | Tableau 展示内容 |
|---|---|---|
| 点击c-创建时间表 | [05](../outputs/tableau_worksheets/05_click_to_create_distribution.png) | 点击-创建（不包含负值）的数据桶与计数。 |
| 创建-付款 | [06](../outputs/tableau_worksheets/06_create_to_payment_distribution.png) | 创建-付款数据桶与计数。 |
| 点击-创建 | [07](../outputs/tableau_worksheets/07_click_to_payment_distribution.png) | 截图的列架使用“点击-付款（数据桶）”，行架使用对应计数。 |
