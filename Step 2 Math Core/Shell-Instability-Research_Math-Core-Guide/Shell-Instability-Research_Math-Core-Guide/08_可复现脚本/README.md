# 可复现脚本说明

本目录保存工作区脚本的副本：

- `generate_plate_shell_buckling_pdf.py`：生成 19 页线性板壳屈曲前置讲义；
- `generate_shell_instability_research_pdf.py`：生成 30 页壳体失稳主讲义。

脚本当前的 `ROOT` 和输出路径按原工作区结构编写。若从本目录直接运行，可能仍把结果写到工作区 `output/pdf`，且依赖工作区字体、ReportLab、matplotlib、PyPDF 等环境。后续 AI 不应为了“整理资料”直接重跑并覆盖成品；只有在修改讲义正文并计划重新渲染、逐页核验时才运行。

本次资料包新增的模态交互、验证题和 8-12 周计划位于 Markdown 文件中，尚未合并进 30 页 PDF 脚本。因此：

- PDF 是已核验的主讲义；
- Markdown 是本次新增的研究补充层；
- 不能只重跑旧脚本后声称已包含新增多模态章节。
