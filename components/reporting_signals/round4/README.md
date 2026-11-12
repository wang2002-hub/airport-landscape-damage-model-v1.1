# 第四轮配套分析脚本

本目录将 R5 投稿包 08_round4_tasks 中的四个 Python 脚本原样纳入代码仓库。
UPSTREAM_README.md 保存随包原始说明；其 08_round4_tasks 路径指原始投稿包。
下列命令以当前代码仓库根目录为工作目录。代码已登记到 reporting_signals 组件。

本次只整合代码及运行文档，不应用年份设定补丁，不重拟合模型，不把模拟测试结果作为论文结果。
逐年校准与对数尺度同时区间仍需原说明中列出的外部预测和联合抽样数据。
现有 supporting_data、图件、分析输入及已保存模型结果保持不变。

## 环境

使用仓库说明的 Python 3.12 分析环境。依赖为 numpy、pandas、scipy 和读取 Parquet 的 pyarrow；
本目录 requirements.txt 沿用根目录分析环境版本。绘图环境按根目录说明分开配置。

## I1 全国逐年校准

```bash
python -B run_component.py --component reporting_signals --entry round4/annual_calibration_check.py -- --geo ../DATA/geo --output ../OUT/annual_calibration
```

geo 目录须含 geographic_predictions_1.parquet 至 geographic_predictions_5.parquet。
可用 --temporal ../DATA/temporal_predictions.parquet 增加时间验证。
文件含 event_id、airport_id、year、damage_binary、p_calibrated、dataset，按 model/family 筛选。
默认 2000 次机场聚类重抽样；输出逐年 O/E、区间和校准截距。
核对真实数据输出后，将 annual_calibration.csv 放入 supporting_data/national_performance/。

## D1 年份项设定补丁

先在独立的仓库副本上应用补丁；它会修改六个组件的 model_core.py。
打包本脚本不代表补丁已经应用，也不代表完成年份敏感性重拟合。

```bash
python -B run_component.py --component reporting_signals --entry round4/apply_year_spec_patch.py -- ../airport-model-year-spec-copy
```

BIRDSTRIKE_YEAR_SPEC 可取 linear（默认原设定）、period（线性项加编码时期）、categorical（逐年类别）。
categorical 仅用于地理验证：时间验证训练集未见未来年份，不能直接使用该选项。
真实重拟合须提供 analysis_events.parquet；核对后的汇总放入 supporting_data/year_specification/。
这个脚本采用位置参数，不支持 --help；它不会主动重建被修改组件的校验清单。

## I2 对数尺度亚型同时区间和 m1 零抽样计数

```bash
python -B run_component.py --component reporting_signals --entry round4/log_scale_subtype_intervals.py -- --draws ../OUT/partition/extent_joint_draws.csv.gz --points supporting_data/extent_partition/extent_decomposition_points.csv --natural supporting_data/extent_partition/extent_simultaneous_intervals.csv --output ../OUT/extent_log
```

需原分析产生的 9960 组对齐联合抽样、8 个机场和2个亚型；连续性校正默认 c=0.5。
--natural 可选。核对后将 extent_simultaneous_intervals_log.csv、zero_draw_counts.csv
及需要公开的比较表放入 supporting_data/extent_partition/。
脚本按参数读取数据，原有实现没有自动校验外部输入哈希；应先对照提供方的校验值确认文件。

## 更新清单

```bash
python -B run_component.py --component reporting_signals --entry round4/regenerate_manifests.py -- . --components reporting_signals
python -B verify_manifest.py
```

若应用了年份补丁，--components 后需列出所有实际修改的组件，而不只是 reporting_signals。
输出目录必须使用仓库外不存在的新目录。不要将事件级数据、稿件或模拟测试结果放入公开代码包。
所有本次测试范围及限制见根目录 r5_packaging_verification.json。
