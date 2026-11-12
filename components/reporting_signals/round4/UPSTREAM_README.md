# 08_round4_tasks — 第四轮意见中需作者完成事项的配套脚本

对应文档：`07_notes/修改稿第四轮意见_需作者完成事项.docx`。这里的脚本**未在真实数据上运行**（所需文件不在本包内），
只在模拟数据或本包仓库副本上测试过；结果未写入稿件。

| 脚本 | 对应意见 | 需要的外部文件 | 输出 |
|---|---|---|---|
| annual_calibration_check.py | I1 全国逐年校准 | geographic_predictions_1..5.parquet（= fit_references.py 的 spatial_1..5_glmm_EBL_predictions.parquet）；可选 temporal_predictions.parquet | annual_calibration.csv、annual_calibration_summary.json |
| apply_year_spec_patch.py | D1 年份项设定 | 无（修改仓库中 6 份 model_core.py）；重拟合需要 analysis_events.parquet | 打补丁后的仓库；环境变量 BIRDSTRIKE_YEAR_SPEC = linear / period / categorical |
| log_scale_subtype_intervals.py | I2 对数尺度亚型区间；m1 零抽样核实 | extent_joint_draws.csv.gz（analyze_partition.py 输出） | extent_simultaneous_intervals_log.csv、natural_vs_log_comparison.csv、zero_draw_counts.csv |
| regenerate_manifests.py | 所有新增结果入库 | 无 | 重写根目录及指定组件的 manifest_sha256.csv，并同步 components.json 中的清单哈希与文件数 |

## 外部文件建议放置位置（不进入公开仓库）
```
<工作目录>/
├─ airport-landscape-damage-model-v1.1/        # 03_code_repository 中的仓库
├─ DATA/
│  ├─ analysis_events.parquet                   # D1 重拟合
│  ├─ geo/geographic_predictions_1..5.parquet   # I1
│  └─ temporal_predictions.parquet              # I1（可选）
└─ OUT/                                         # 所有新输出，每次用新子目录
```
需要按组件配置运行时（documentation_partition、report_volume_calibration、coding_transfer），把外部文件放到
该组件 `inputs.example.json` 登记的 `data/...` 路径，复制为 `inputs.json` 后运行；文件 SHA256 会被核对。

## 新结果入库位置（建议）
| 结果 | 放到仓库中的位置 |
|---|---|
| annual_calibration.csv | supporting_data/national_performance/ |
| 年份设定敏感性汇总表 | supporting_data/year_specification/（新建） |
| extent_simultaneous_intervals_log.csv、zero_draw_counts.csv | supporting_data/extent_partition/ |
| 第四轮脚本本身 | components/reporting_signals/round4/（或新建组件，并登记到 components.json） |

入库后运行：
```
python -B 08_round4_tasks/regenerate_manifests.py 03_code_repository/airport-landscape-damage-model-v1.1 --components <改动的组件>
cd 03_code_repository/airport-landscape-damage-model-v1.1 && python -B verify_manifest.py
```
在本包仓库副本上测试：对未改动的仓库运行该脚本，25 个组件清单、根清单和 components.json 逐字节不变；新增文件后 verify_manifest 通过、run_component 正常运行。
