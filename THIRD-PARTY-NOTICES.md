# 第三方组件

发布包中包含以下第三方组件，它们按各自的许可证发布，版权归原作者所有。各组件的许可证文本随组件一起位于 `_internal` 文件夹中（如 `*.dist-info` 目录）。

| 组件 | 用途 | 许可证 |
|---|---|---|
| Python 3.12 | 运行环境 | PSF License |
| Qt 6 / PySide6 | 图形界面 | LGPL v3（以独立动态库形式提供，可替换） |
| NumPy | 数值计算 | BSD 3-Clause |
| Numba、llvmlite | 计算内核编译 | BSD 2-Clause |
| pandas | 数据读取 | BSD 3-Clause |
| pyqtgraph | 二维 / 三维图形 | MIT |
| PyOpenGL | 三维显示 | BSD 类 |
| Matplotlib | 报告插图 | Matplotlib License（PSF 类） |
| python-docx、lxml | Word 报告 | MIT / BSD |
| openpyxl | Excel 导出 | MIT |
| latex2mathml | 报告公式 | MIT |
| PyInstaller（引导程序） | 打包 | GPL v2 附例外条款（允许发布打包后的程序） |
| Noto Sans SC | 界面备用字体 | SIL Open Font License 1.1 |

Qt / PySide6 按 LGPL v3 使用：程序以动态链接方式调用 Qt 库，Qt 的库文件在 `_internal\PySide6` 中，用户可以用兼容版本替换。
