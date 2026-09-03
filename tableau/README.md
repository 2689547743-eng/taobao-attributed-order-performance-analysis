# Tableau 工作簿

`电商数据分析.twb` 是本项目的原始 Tableau 工作簿，含 10 个工作表，没有已发布的 Dashboard 对象。

## 本地打开

1. 在本地准备 `合并淘宝表格.xlsx` 和 `淘宝sku标签.xlsx`。
2. 在 Tableau Desktop 打开 `电商数据分析.twb`。
3. 对两个 Excel 数据源执行“编辑连接”，将 `REPLACE_WITH_LOCAL_PATH/...` 替换为本地文件路径。

## 公开版本说明

- 工作簿的工作表、字段、计算逻辑和图表定义均保留。
- 仅移除了本机绝对路径和 Tableau 机器标识。
- 原始 Excel 数据不包含在此仓库中。
- `../outputs/tableau_worksheets/` 保存了该工作簿 10 个工作表的原始截图。
