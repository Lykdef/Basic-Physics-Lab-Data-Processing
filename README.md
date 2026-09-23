# 物理实验室 · Physical Lab

面向大学物理实验的数据工作台。采用 pywebview（Edge WebView2）+ Vue 3 + TypeScript，已实现数据管理、统计评定、实时拟合与一阶不确定度传播，安装依赖后可离线使用。

## 直接运行（Windows x64）

完整解压 `PhysicalLab-WebView-0.2.0-win-x64.zip`，双击 `PhysicalLab.exe`。该版本内置 Python 与科学计算依赖，不需要 Node.js 或另装 Python；需要系统具备 Microsoft Edge WebView2 Runtime。Windows 10/11 通常已有该组件；缺失时可从 [微软官方下载页](https://developer.microsoft.com/microsoft-edge/webview2/) 安装。

请保留整个解压目录。项目自动保存在 `%LOCALAPPDATA%\PhysicalLab\workspace.json`，浏览器缓存单独保存，不依赖本地服务端口。其他版本或浏览器项目请先导出 JSON，再在桌面版导入。

## 源码启动

前端开发需要 Node.js 22.12+；桌面 Python 建议 3.12 x64。

```sh
npm ci
py -3.12 -m venv .venv-webview
.venv-webview\Scripts\python.exe -m pip install -r desktop/requirements.txt
npm run desktop
```

双击 `启动物理实验室.cmd` 等价于默认桌面启动。`npm run dev` 仍可用于浏览器前端开发；浏览器计算接口使用 `compute/bridge.cjs`，优先复用 `.venv-webview` 环境；也可通过 `PHYSICAL_LAB_PYTHON` 指定其他 Python。

## 已实现

- 多项目、多数据组；项目可直接删除（包括最后一个项目），不保留已删除副本；支持删除数据组与撤销（至少保留一组）；重复测量 / 成对数据类型。
- 可编辑纵向/横向表格，增删行列，变量名称、唯一符号、单位与显示精度。
- Excel 多行多列粘贴，空值为 null，拒绝非法数字，稳定行编号。
- 数据一键排除与恢复；不保存操作历史，保留 80 步会话内撤销重做。
- 五个明确标注的教学模拟示例。
- 完整项目 JSON 导入导出与格式版本校验；浏览器与桌面本机存储自动恢复。
- 仪器信息、按变量保存的误差限 δ、分布假设、B 类标准不确定度与备注；原始数据图形预览。
- 统计页展示原始数据表与最佳估计值 x̄ ± u；不确定度默认只进不舍保留一位有效数字，可选两位；均值对齐末位并四舍六入五凑偶，仅用于显示。
- 三栏响应式界面，键盘保存快捷键。

## 当前边界

支持均值、样本标准差、均值的 A 类标准不确定度、单个误差限的 B 类评定及独立 A/B 合成。B 类缺失时不视为零。Grubbs 双侧检验仅支持 α=0.01、0.05、有效样本数 3–10000，按内置表查询临界值；只标记一个最偏离的疑似点，由用户一键排除，无需理由。近似正态假设可通过折叠直方图辅助观察；反复排除不保持原整体显著性水平。缺失值与排除值不参加当前列计算。成对数据不进行重复测量评定。

暂未实现多来源 B 类合成、偏差修正、蒙特卡洛传播或图像导出。误差限 δ 按变量保存；均匀分布 u_B=δ/√3，三角分布 δ/√6，正态 3σ 为 δ/3，正态 2σ 为 δ/2。旧量程/分辨力仅保留存档，不自动用于计算。修改单位标签不会换算数值。图形支持实时拟合；暂未显示误差棒。统计结果在读取、修改时重算；G、样本标准差等中间量显示 7 位有效数字，A/B 分量显示未修约浮点值，仅最终合成不确定度和报告值按所选规则修约。修约使用十进制整数算法处理临界位数，不影响内部计算与原始数据。

本机自动恢复依赖当前浏览器来源 / 桌面应用存储，建议另存 JSON 作为可移植备份。重新导入同 ID 项目创建副本，避免覆盖。撤销栈不跨项目切换或重启保存。已提供 Windows x64 pywebview 便携包；源码桌面运行使用 .venv-webview 环境，浏览器开发接口可复用同一 Python 环境。

## 验证

```sh
npm run build
npm test
npx playwright install chromium
npm run test:ui
npm run test:desktop
```

验收覆盖 JSON 往返、变量/行标识校验、非法数据、Excel 配对、排除恢复、自动恢复与导出导入。

桌面集成检查使用隐藏窗口与独立测试目录，验证生产构建加载、隔离桥接、临时文件替换、保存覆盖及重新导入。测试包括数据与统计回归、科学计算解析核验、浏览器交互及桌面集成检查。

## 架构

- `src/model.ts`：类型、版本化数据模型、Zod 校验、示例、数字解析与原子粘贴。
- `src/statistics.ts` / `src/StatisticsPanel.vue`：离线统计计算与评定界面，使用内置 Grubbs 临界值表。
- `src/App.vue`：工作台、项目操作、设置与本机恢复。
- `src/style.css`：暖白与深青色视觉规范及响应式布局。
- `desktop/`：pywebview 窗口、受限桌面接口、独立计算进程和原子文件保存。
- `src/desktop.ts`：等待桥接就绪并接入稳定的本机工作区存储。

pywebview 桥接依据官方文档：https://pywebview.flowrl.com/guide/interdomain

## 统计方法与独立核验

- A 类方法：https://physics.nist.gov/cuu/Uncertainty/typea.html
- Grubbs 双侧临界值：https://www.itl.nist.gov/div898/handbook/eda/section3/eda35h1.htm
- 独立分量合成：https://www.nist.gov/pml/nist-technical-note-1297/nist-tn-1297-5-combined-standard-uncertainty

当前统计核心运行在 TypeScript 中，可同时用于浏览器和桌面离线预览。SciPy / SymPy 常驻进程负责拟合与传播；浏览器开发/预览服务器和 pywebview 桌面桥接均使用同一计算核心。验证脚本 `tests/generate-statistics-reference.py` 使用独立 SciPy 生成 `tests/statistics-reference.json`：32 组 Grubbs 临界值和 4 组统计参考样本。常规测试直接使用已保存的参考文件，不需要 Python。重新生成参考文件时可安装 SciPy 并运行该脚本。

横向表格按变量分行、测量次数分列，横向粘贴按视觉方向映射回原始观测，方向设置随数据组保存。统计页的数据表只读，保留排除标识，可横纵切换。

数据设置仅在数据表格标签显示；统计评定顺序为测量数据、Grubbs 双侧检验、统计量与最终最佳估计值。

变量设置逐项显示全部变量；预览可选择任意列作为横、纵轴（横轴也支持测量序号），按稳定列 ID 保存选择，并按原始行配对，任一坐标缺失时跳过该点。


## 实时拟合与不确定度传播

在「数据预览」勾选「曲线拟合」。支持直线、过原点直线、1–6 次多项式、指数、幂函数、对数模型；自动拟合直接回填参数值，可固定参数或切换手动模式调整曲线。使用全部未排除的完整配对点，不设置横轴范围、参数边界或权重；显示参数、R²、RMSE 及残差。统计页在变量选择右侧同步显示最佳估计值，下方完整结果保留。

拟合使用普通最小二乘，不使用测量不确定度进行加权。参数不确定度与协方差不在拟合页显示，仅在引用拟合参数进行传播时内部使用残差估计的局部协方差。非线性优化依赖初值，不保证找到全局最优值。

「不确定度传播」支持安全解析的公式、手动输入、重复测量均值及自动拟合参数来源。重复测量来源要求设置 B 类分量；同一拟合的参数自动使用其协方差，同一来源重复引用按完全相关处理，其他输入默认独立，可填写相关系数。相关矩阵必须半正定。采用一阶偏导数传播，展示灵敏系数、对角及交叉方差贡献、最终 y ± u、相对标准不确定度和扩展不确定度 U = k·u。k 不自动解释为特定置信水平。输入和单位须自行保持一致，不执行单位换算。

设置随项目保存，数据及参数更改后自动重新计算；旧计算响应不会覆盖新结果。中间量不修约，仅最终结果沿用向上取不确定度与均值半偶舍入规则。成对数据沿用项目传播模型；“合成标准不确定度”数据组各自保存独立模型，只显示“不确定度”页面。

科学计算核验：`python tests/test_compute.py`。可通过环境变量 `PHYSICAL_LAB_PYTHON` 指定 Python 可执行文件。

方法参考：[SciPy curve_fit](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.curve_fit.html)、[JCGM 100:2008](https://www.bipm.org/documents/20126/2071204/JCGM_100_2008_E.pdf)。


Grubbs 表文件为 `src/grubbs-table.json`，离线预生成到小数点后 10 位（双侧 α/(2n)，自由度 n−2），运行时不求分位数。使用 `python compute/generate_grubbs_table.py` 可重建。旧文件中的其他显著性水平载入时统一回到 0.05。

添加数据组可选择“合成标准不确定度”，无需录入原始重复观测，直接输入估计值、标准不确定度及测量模型公式。多个合成数据组独立保存，支持现有相关系数、结果修约和预算表。

不再显示操作记录、已删除项目或使用指南。载入本机工作区时清除旧操作历史及已删除项目缓存；导入旧项目时保留当前数据与排除状态，丢弃历史记录。


## 构建与验证 pywebview 便携包

安装上述环境后运行 `npm run package:windows`，输出 `release/PhysicalLab-WebView-0.2.0-win-x64.zip` 及 SHA-256 校验文件。使用 PyInstaller onedir 打包，计算工作进程通过 multiprocessing 管道通信；30 秒超时终止工作进程，下次请求可重启。文件保存采用临时文件原子替换；桌面 API 仅允许当前本地应用页面调用。

```sh
npm run build
npm test
npm run test:ui
npm run test:desktop
.venv-webview\Scripts\python.exe tests/test_webview_backend.py
.venv-webview\Scripts\python.exe tests/test_compute.py
.venv-webview\Scripts\python.exe tests/webview_integration.py release/PhysicalLab-WebView-0.2.0-win-x64/PhysicalLab.exe
```

桌面测试使用隐藏窗口和隔离数据目录，验证中英文错误、拟合、传播、文件打开/保存，以及新进程中的自动恢复。便携版测试会从 PATH 移除 Python 和 Node.js。开发服务器忽略 Python 环境、打包目录和 WebView 缓存，避免监听锁定文件。


Grubbs 表文件为 `src/grubbs-table.json`，预生成后直接查表，仅提供 0.01 与 0.05。合成标准不确定度数据组独立保存模型。操作记录、已删除项目与使用指南不再显示或保存。

项目保留仓库原有 CC0 许可证，第三方组件许可证随便携包提供。
