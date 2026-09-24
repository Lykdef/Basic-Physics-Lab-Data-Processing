# 物理实验室 · Physical Lab

大学物理实验数据工作台，当前版本 1.0.0。桌面采用 pywebview / WebView2，界面采用 Vue 3 / TypeScript。拟合与不确定度计算由 Python 标准库实现，运行时不依赖 NumPy、SciPy、SymPy。

## 直接运行

解压 `release/PhysicalLab-WebView-1.0.0-win-x64.zip`，双击 `PhysicalLab.exe`。必须保留完整解压目录。无需安装 Python 或 Node.js；Windows 需具备 Microsoft Edge WebView2 Runtime。

项目保存在 `%LOCALAPPDATA%\PhysicalLab\workspace.json`。支持项目 JSON 导入导出，升级不删除已保存的数据。

## 功能

- 多项目、重复测量、成对数据与合成不确定度数据组；横纵表格、粘贴、排除、撤销。
- 重复测量统计、Grubbs 查表检验（0.01 / 0.05）、A/B 类不确定度合成与结果修约。
- 数据预览直接填写原始变量表达式，如 `1/u`、`1/v`、`U^2`；单位自行填写，支持 `cm^{-1}` 等上下标。重复测量横轴固定为测量序号。不存在独立导出量编辑栏目；旧配置兼容读取。
- 线性、多项式、指数、幂函数和对数模型拟合，自动或手动参数；拟合不使用测量不确定度加权。
- 科学计算引用重复测量均值时合成不确定度，引用拟合参数时仅计算结论值。
- 高清 PNG 导出，可选标题、横向原始数据、拟合公式与 R²。

## 计算引擎与适用范围

`compute/pymatrix.py` 提供矩阵运算；`compute/pyleastsq.py` 提供有限差分雅可比、阻尼最小二乘和协方差估计；`compute/pysymbolic.py` 提供白名单公式解析、求值与求导。没有使用动态执行任意代码的公式实现。

迁移检查包含 135 个与原科学计算库引擎的对照案例：132 个满足设定容差，3 个存在已记录差异（两组极小残差、一个不可辨识指数模型的参数）。原始参考输出保存在 `tests/engine-reference.json.gz`，回归测试不再需要旧版源码或科学计算库。已知差异设有界限，不豁免任意大小的偏差。该检查不代表所有数值条件下与 SciPy / SymPy 完全等价；非线性拟合依赖初值，病态或不可辨识数据应结合警告和残差判断。

## 开发

需要 Node.js 22.12+，桌面建议 Python 3.12 x64。

```sh
npm ci
py -3.12 -m venv .venv-webview
.venv-webview\Scripts\python.exe -m pip install -r desktop/requirements.txt
npm run desktop
```

`npm run dev` 启动浏览器开发预览。计算后端优先使用 `.venv-webview`，也可通过 `PHYSICAL_LAB_PYTHON` 指定解释器。计算引擎本身无需安装任何依赖；pywebview、pythonnet 用于桌面窗口，PyInstaller 用于打包。

## 验证

```sh
npm run build
npm test
npx playwright install chromium
npm run test:ui
python -S tests/test_compute.py
python -S tests/parity_engine.py
python -S compute/selftest_pymatrix.py
python -S compute/selftest_pysymbolic.py
python -S compute/selftest_pyleastsq.py
npm run test:desktop
```

`tests/test_webview_backend.py` 使用桌面 Python 环境执行。`tests/generate-statistics-reference.py` 和 `compute/generate_grubbs_table.py` 仅用于重新生成独立参考数据，需要额外安装科学计算库；日常开发、测试和运行不需要运行这些生成器。

## 打包

`npm run package:windows` 生成完整 ZIP 与 SHA-256 文件；输出目录已存在时不会覆盖。构建明确排除 NumPy / SciPy / SymPy / mpmath。

`python scripts/package-installer.py` 可从完整 ZIP 生成小安装器。联网分发需要先将完整包放置到可访问的发布地址；生成安装器不等于发布。当前没有发布在线安装资源。同目录放置完整 ZIP 时可使用本地安装。

仓库使用 CC0 许可证。第三方组件许可证随便携包提供。
