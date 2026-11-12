# 使用说明

作者：Sheng Yun、Wang Yangrui、Fang Xuedong。

将本文件夹内的内容作为GitHub仓库根目录上传。文件完整性可通过python verify_manifest.py检查，组件列表可通过python run_component.py --list查看。具体命令见README.md及各组件说明。输出目录应使用仓库外的新目录。

本包对应manuscript_binding.json中的五份文稿，包含当前分析与绘图代码、汇总证据及40份逐条报告预测表。论文正文、审稿意见、个人工作路径和大体量原始数据未随包提供。完整事件队列、部分保存拟合与原始GIS数据仍需按组件模板另行配置，不能把现有汇总复算等同于全部模型重新训练。当前配套数据包尚未公开，未编造DOI或下载链接。

数值计算与绘图环境分别记录。已验证范围详见verification_summary.json；未宣称完成全新电脑安装、跨平台验证或所有原始数据的端到端重跑。作者尚未明确当前软件许可，包内没有擅自指定MIT等许可证。准备工作不会自动上传任何内容。

## 2026-11-12 R5 代码整合

当前实际代码版本为 v1.1，含7幅正文图和11幅补充图。
四个第四轮配套脚本已原样放入 components/reporting_signals/round4/，并登记统一运行入口。
命令、外部数据要求和结果建议位置见该目录 README.md；原始说明另存 UPSTREAM_README.md。
年份项补丁只随包提供，未应用到发布模型；本次未完成事件级模型重拟合或新增推断结果。
本次打包验证见 r5_packaging_verification.json。
