# Tableau 历史探索工作簿

`电商数据分析.twb` 是用户提供的 Tableau 工作簿。它含有 10 个工作表，没有已发布的 Dashboard 对象；工作簿使用合并订单表和 SKU 标签表作为数据源。

## 公开版本的处理

- 仅发布 `.twb` 工作簿定义，不含 `.twbx`、`.hyper` 或原始 Excel 数据。
- 已移除原工作簿中的本机绝对文件路径和 Tableau 机器指纹字段。
- 工作表、字段和原始计算逻辑未被修改。

## 本地打开方式

1. 获取数据授权后，在本地准备 `合并淘宝表格.xlsx` 和 `淘宝sku标签.xlsx`。
2. 在 Tableau Desktop 打开 `电商数据分析.twb`。
3. 对两个 Excel 数据源执行“编辑连接”，替换 `REPLACE_WITH_LOCAL_PATH/...` 占位路径。

## 使用边界

该文件保留早期探索过程，不能替代本项目当前的可复现分析输出。最终使用的指标口径、质量检查、已验证发现和建议分别见：

- [指标口径](../docs/metric_definitions.md)
- [数据质量](../docs/data_quality.md)
- [分析发现](../docs/analysis_findings.md)
- [业务建议](../docs/business_recommendations.md)

尤其是，源数据缺少曝光、总点击量和投放成本，不能据此计算点击率、完整转化率、ROI，或认定推广位产生因果效果。
