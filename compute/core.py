"""Offline numerical engine (pure standard library build). JSON-lines on stdin/stdout; no expression eval.

零第三方依赖复刻版：行为逐条对齐原 numpy/scipy/sympy 引擎 compute/core.py。
矩阵运算由 pymatrix 提供，有界加权最小二乘由 pyleastsq 提供（对标
scipy curve_fit(method='trf', x_scale='jac')），符号解析/求导/打印由
pysymbolic 提供（对标 sympy）。模型函数通过 _mul/_add/_exp/_power/_log
复刻 np.errstate(over/invalid/divide='raise') 下 numpy ufunc 的
FloatingPointError 语义。
"""
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import ast  # noqa: F401  (保留原模块的导入面；ast 由 pysymbolic 内部使用)
import json
import math
import re

from pymatrix import eigvalsh as _eigvalsh, singular_values as _singular_values  # noqa: F401
from pyleastsq import least_squares_fit as _least_squares_fit  # noqa: F401
import pysymbolic as _ps  # noqa: F401

# PyInstaller 冻结说明：以上 import 配合本文件顶部的 sys.path 自注入在源码
# 运行（脚本/包两种模式）下均有效；但 PyInstaller 静态分析按 --paths 根目录
# 解析不到 compute/ 目录内的兄弟模块。scripts/package-webview.py 因此通过
# --paths compute 与 --hidden-import 显式收集 pymatrix/pyleastsq/pysymbolic，
# 冻结后由 PyInstaller 的导入器以顶层模块形式提供这些 import。


def finite(value, name='数值'):
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
        raise ValueError(f'{name}必须为有限数值')
    return float(value)


# ---------------------------------------------------------------------------
# numpy ufunc 语义复刻（errstate over/invalid/divide = 'raise' 或默认非严格）
# 严格模式下溢出/非法/除零抛 FloatingPointError，文案与 numpy 一致；
# 非严格模式按 IEEE 754 静默传播 inf/nan（Python float 运算天然如此）。
# ---------------------------------------------------------------------------

def _mul(a, b, strict):
    if (a == 0.0 and math.isinf(b)) or (b == 0.0 and math.isinf(a)):
        if strict:
            raise FloatingPointError('invalid value encountered in multiply')
        return math.nan
    r = a * b
    if not math.isfinite(r):
        if strict:
            if math.isfinite(a) and math.isfinite(b):
                raise FloatingPointError('overflow encountered in multiply')
            if math.isnan(r):
                raise FloatingPointError('invalid value encountered in multiply')
    return r


def _add(a, b, strict):
    r = a + b
    if not math.isfinite(r):
        if strict:
            if math.isfinite(a) and math.isfinite(b):
                raise FloatingPointError('overflow encountered in add')
            if math.isnan(r):
                raise FloatingPointError('invalid value encountered in add')
    return r


def _exp(v, strict):
    if math.isnan(v):
        return math.nan
    if v == math.inf:
        return math.inf
    try:
        return math.exp(v)
    except OverflowError:
        if strict:
            raise FloatingPointError('overflow encountered in exp') from None
        return math.inf


def _power(a, b, strict):
    """numpy power 语义：负底数非整指数 -> nan/invalid；0**负 -> inf/divide；
    溢出 -> inf/overflow。"""
    if math.isnan(a) or math.isnan(b):
        return math.nan
    if a < 0.0 and math.isfinite(b) and b != math.floor(b):
        if strict:
            raise FloatingPointError('invalid value encountered in power')
        return math.nan
    try:
        r = a ** b
    except ZeroDivisionError:
        if strict:
            raise FloatingPointError('divide by zero encountered in power') from None
        odd = b == math.floor(b) and int(abs(b)) % 2 == 1
        return math.copysign(math.inf, a) if odd else math.inf
    except OverflowError:
        if strict:
            raise FloatingPointError('overflow encountered in power') from None
        odd = b == math.floor(b) and int(abs(b)) % 2 == 1
        return -math.inf if (a < 0.0 and odd) else math.inf
    if isinstance(r, complex):
        if strict:
            raise FloatingPointError('invalid value encountered in power')
        return math.nan
    return r


def _log(v, strict):
    if math.isnan(v):
        return math.nan
    if v > 0.0:
        return math.log(v)
    if v == 0.0:
        if strict:
            raise FloatingPointError('divide by zero encountered in log')
        return -math.inf
    if strict:
        raise FloatingPointError('invalid value encountered in log')
    return math.nan


def _polyval(x, coeffs, strict):
    """numpy.polynomial.polynomial.polyval 的 Horner 求值（系数升幂序）。"""
    r = coeffs[-1]
    for c in reversed(coeffs[:-1]):
        r = _add(c, _mul(r, x, strict), strict)
    return r


def _model_eval(model, xs, params, strict):
    """六种拟合模型的逐点求值；params 为完整参数序列（含固定参数）。"""
    if model == 'linear':
        a, b = params
        return [_add(_mul(a, v, strict), b, strict) for v in xs]
    if model == 'origin':
        (a,) = params
        return [_mul(a, v, strict) for v in xs]
    if model == 'polynomial':
        return [_polyval(v, params, strict) for v in xs]
    if model == 'exponential':
        a, b, c = params
        return [_add(_mul(a, _exp(_mul(b, v, strict), strict), strict), c, strict) for v in xs]
    if model == 'power':
        a, b = params
        return [_mul(a, _power(v, b, strict), strict) for v in xs]
    if model == 'logarithmic':
        a, b = params
        return [_add(_mul(a, _log(v, strict), strict), b, strict) for v in xs]
    raise ValueError('不支持的拟合模型')


def _norm2_loose(v):
    """2-范数（hypot 链），允许 inf/nan 传播，不校验有限性。"""
    r = 0.0
    for value in v:
        r = math.hypot(r, value)
    return r


def fit(request):
    points = request.get('points', [])
    if not 1 <= len(points) <= 10000:
        raise ValueError('需要 1–10000 个有效配对点')
    x = [finite(p['x']) for p in points]
    y = [finite(p['y']) for p in points]
    config = request['config']
    model = config['model']
    degree = int(config.get('degree', 2))
    if model == 'linear':
        names = ['a', 'b']
    elif model == 'origin':
        names = ['a']
    elif model == 'polynomial':
        if not 1 <= degree <= 6:
            raise ValueError('多项式次数须为 1–6')
        names = [f'a{i}' for i in range(degree + 1)]
    elif model == 'exponential':
        names = ['a', 'b', 'c']
    elif model == 'power':
        names = ['a', 'b']
    elif model == 'logarithmic':
        names = ['a', 'b']
    else:
        raise ValueError('不支持的拟合模型')
    if model in ('power', 'logarithmic') and any(v <= 0 for v in x):
        raise ValueError('幂函数和对数模型要求横坐标 > 0')
    if max(x) - min(x) == 0:
        raise ValueError('横坐标无变化，无法拟合关系')
    settings = config['parameters']
    if len(settings) != len(names):
        raise ValueError('参数数量与模型不一致')
    params = [finite(p['value'], '参数') for p in settings]
    free = [i for i, p in enumerate(settings) if not p.get('fixed', False)]
    lower = [-math.inf if p.get('min') is None else finite(p['min'], '下界') for p in settings]
    upper = [math.inf if p.get('max') is None else finite(p['max'], '上界') for p in settings]
    for i in range(len(params)):
        if lower[i] >= upper[i]:
            raise ValueError(f'{names[i]} 的下界必须小于上界')
        if not lower[i] <= params[i] <= upper[i]:
            raise ValueError(f'{names[i]} 的初值超出边界')
    mode = config.get('weighting', 'ordinary')
    sigma = None
    if mode != 'ordinary':
        if mode not in ('absolute', 'relative'):
            raise ValueError('未知加权方式')
        sigma = [finite(p.get('sigma'), '纵坐标标准不确定度') for p in points]
        if any(s <= 0 for s in sigma):
            raise ValueError('加权拟合要求每个有效点的纵坐标标准不确定度 > 0')
    covariance = None
    errors = None
    warning = None
    manual = config.get('mode') == 'manual'
    if not manual:
        if len(x) <= len(free):
            raise ValueError('有效点数必须大于待拟合参数个数')
        if not free:
            raise ValueError('自动拟合至少需要一个未固定参数')

        def wrapped(xs, *v):
            p = list(params)
            for index, value in zip(free, v):
                p[index] = value
            return _model_eval(model, xs, p, True)

        try:
            fitted_result = _least_squares_fit(
                wrapped, x, y, [params[i] for i in free],
                sigma=sigma, absolute_sigma=mode == 'absolute',
                bounds=([lower[i] for i in free], [upper[i] for i in free]),
                max_nfev=3000)
        except RuntimeError as exc:
            if 'maxfev' in str(exc):
                # scipy curve_fit 对 trf 的 max_nfev 耗尽实际抛出的文案
                raise RuntimeError('Optimal parameters not found: The maximum '
                                   'number of function evaluations is exceeded.') from None
            raise
        for index, value in zip(free, fitted_result['popt']):
            params[index] = value
        # Check identifiability separately: an exact fit may have zero covariance.
        columns = []
        for i in free:
            step = 1e-6 * max(1, abs(params[i]))
            plus = list(params)
            minus = list(params)
            plus[i] += step
            minus[i] -= step
            fp = _model_eval(model, x, plus, False)
            fm = _model_eval(model, x, minus, False)
            column = [(fp[r] - fm[r]) / (2 * step) for r in range(len(x))]
            if sigma is not None:
                column = [column[r] / sigma[r] for r in range(len(x))]
            columns.append(column)
        norms = [_norm2_loose(col) for col in columns]
        identifiable = bool(all(n > 0 for n in norms))
        if identifiable:
            if any(not math.isfinite(n) for n in norms):
                # np.linalg.cond 对含 inf 的矩阵抛 LinAlgError('SVD did not converge')
                raise ValueError('SVD did not converge')
            normalized = [[columns[j][r] / max(norms[j], 1e-300)
                           for j in range(len(columns))] for r in range(len(x))]
            svs = _singular_values(normalized)
            smallest = svs[-1]
            cond = math.inf if smallest == 0.0 else svs[0] / smallest
            identifiable = bool(cond < 1e7)
        if fitted_result['pcov'] is not None and identifiable and not fitted_result['optimize_warning']:
            covariance = [[0.0] * len(params) for _ in range(len(params))]
            for a_i, i in enumerate(free):
                for b_j, j in enumerate(free):
                    covariance[i][j] = fitted_result['pcov'][a_i][b_j]
            errors = [math.sqrt(max(covariance[i][i], 0)) for i in range(len(params))]
        else:
            warning = '参数协方差不可可靠估计，请检查模型、范围与参数相关性'
        if any(abs(params[i] - lower[i]) < 1e-7 * max(1, abs(params[i]))
               or abs(params[i] - upper[i]) < 1e-7 * max(1, abs(params[i])) for i in free):
            warning = '部分参数位于边界，协方差仅为局部近似'
    predicted = _model_eval(model, x, params, True)
    x_min = min(x)
    x_max = max(x)
    step = (x_max - x_min) / 240
    cx = [i * step + x_min for i in range(240)] + [x_max]
    cy = _model_eval(model, cx, params, True)
    if not all(map(math.isfinite, predicted)) or not all(map(math.isfinite, cy)):
        raise ValueError('模型结果超出数值范围，请调整参数')
    residual = [y[i] - predicted[i] for i in range(len(x))]
    sse = float(math.fsum(r * r for r in residual))
    mean = math.fsum(y) / len(y)
    sst = float(math.fsum((v - mean) * (v - mean) for v in y))
    return dict(names=names, parameters=[float(p) for p in params], standard_errors=errors,
                covariance=covariance,
                curve=[[cx[i], cy[i]] for i in range(241)],
                residuals=[dict(id=p['id'], x=float(x[i]), residual=float(residual[i]))
                           for i, p in enumerate(points)],
                rmse=float(math.sqrt(sse / len(x))),
                r2=None if sst <= 1e-28 else 1 - sse / sst,
                n=len(x), manual=manual, warning=warning)


FUNCTIONS = ('sin', 'cos', 'tan', 'exp', 'log', 'ln', 'sqrt', 'asin', 'acos', 'atan')


def expression(text, symbols):
    """符号公式解析（pysymbolic；symbols: dict name -> Sym）。"""
    return _ps.parse(text, symbols)


def _correlation_matrix(request, n):
    """复刻 np.array(request.get('correlation', eye(n)), dtype=float) 的可观察行为。"""
    sentinel = object()
    raw = request.get('correlation', sentinel)
    if raw is sentinel:
        return [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]
    if not isinstance(raw, (list, tuple)):
        if isinstance(raw, bool) or not isinstance(raw, (int, float, str)) or raw is None:
            # np.array(None, dtype=float) -> 0 维 nan 数组，形状不匹配
            raise ValueError('相关矩阵维数错误或含非法数值')
        float(raw)  # 触发与 numpy 一致的转换报错（如字符串）
        raise ValueError('相关矩阵维数错误或含非法数值')
    if any(not isinstance(row, (list, tuple)) for row in raw):
        for value in raw:
            float(value)  # 转换错误文案与 numpy 一致
        raise ValueError('相关矩阵维数错误或含非法数值')
    widths = {len(row) for row in raw}
    if len(widths) > 1:
        raise ValueError('setting an array element with a sequence. The requested array '
                         f'has an inhomogeneous shape after 1 dimensions. The detected '
                         f'shape was ({len(raw)},) + inhomogeneous part.')
    matrix = [[float(value) for value in row] for row in raw]
    return matrix


def propagate(request):
    variables = request['variables']
    if not 1 <= len(variables) <= 16:
        raise ValueError('模型需要 1–16 个输入变量')
    names = [v['symbol'] for v in variables]
    if len(set(names)) != len(names) or any(
            not re.fullmatch('[A-Za-z][A-Za-z0-9_]{0,30}', n)
            or n in FUNCTIONS or n in ('pi', 'e') for n in names):
        raise ValueError('变量名重复、不合法或与数学函数冲突')
    symbols = {n: _ps.Symbol(n) for n in names}
    expr = expression(request['expression'], symbols)
    vals = [finite(v['value'], n) for v, n in zip(variables, names)]
    substitutions = {n: v for n, v in zip(names, vals)}
    if request.get('values_only'):
        try:
            result = _ps.evaluate(expr, substitutions)
        except (ArithmeticError, ValueError):
            raise ValueError('公式在当前输入处无定义') from None
        return dict(value=finite(result, '公式结果'))
    u = [finite(v['uncertainty'], f'u({n})') for v, n in zip(variables, names)]
    if any(value < 0 for value in u):
        raise ValueError('标准不确定度不得为负')
    corr = _correlation_matrix(request, len(names))
    if (len(corr) != len(names) or any(len(row) != len(names) for row in corr)
            or any(not math.isfinite(value) for row in corr for value in row)):
        raise ValueError('相关矩阵维数错误或含非法数值')
    if (any(abs(corr[i][j] - corr[j][i]) > 1e-12 for i in range(len(names)) for j in range(len(names)))
            or any(abs(corr[i][i] - 1) > 1e-12 for i in range(len(names)))
            or any(abs(value) > 1 for row in corr for value in row)):
        raise ValueError('相关矩阵须对称、对角线为 1，且系数在 [-1,1]')
    symmetric = [[(corr[i][j] + corr[j][i]) / 2 for j in range(len(names))] for i in range(len(names))]
    if min(_eigvalsh(symmetric)) < -1e-10:
        raise ValueError('相关矩阵不是半正定矩阵')

    def number(e):
        try:
            v = _ps.evaluate(e, substitutions)
        except ValueError as exc:
            if isinstance(exc, ArithmeticError):
                # sympy evalf 对 0**负指数抛裸露 ZeroDivisionError（str 为空，
                # __main__ 以类型名 'ZeroDivisionError' 回应）
                raise ZeroDivisionError from None
            raise ValueError('公式或偏导数在当前输入处无定义') from None
        except ArithmeticError:
            raise ValueError('公式或偏导数在当前输入处无定义') from None
        return finite(v, '公式结果')

    y = number(expr)
    derivatives = [expr.diff(symbols[n]) for n in names]
    c = [number(d) for d in derivatives]
    scaled = [c[i] * u[i] for i in range(len(names))]
    # variance = scaled @ corr @ scaled（先左乘，再与 scaled 点积）
    blended = [math.fsum(scaled[i] * corr[i][j] for i in range(len(names))) for j in range(len(names))]
    variance = float(math.fsum(blended[j] * scaled[j] for j in range(len(names))))
    if not math.isfinite(variance):
        raise ValueError('传播计算超出数值范围')
    variance = max(variance, 0)
    uc = math.sqrt(variance)
    k = finite(request.get('k', 2), '包含因子')
    if k <= 0:
        raise ValueError('包含因子须 > 0')
    budget = [dict(symbol=n, derivative=_ps.to_string(d), sensitivity=float(c[i]),
                   uncertainty=float(u[i]), contribution=float(scaled[i] ** 2))
              for i, (n, d) in enumerate(zip(names, derivatives))]
    cross = [dict(left=names[i], right=names[j], correlation=float(corr[i][j]),
                  contribution=float(2 * scaled[i] * scaled[j] * corr[i][j]))
             for i in range(len(names)) for j in range(i + 1, len(names)) if corr[i][j] != 0]
    near_zero = abs(y) <= 1e-12 * max(1, sum(abs(c[i] * vals[i]) for i in range(len(names))))
    return dict(value=y, uncertainty=uc, relative=None if near_zero else uc / abs(y),
                expanded=k * uc, budget=budget, cross=cross, expression=_ps.to_string(expr))


def calculate(request):
    if request.get('operation') == 'fit':
        return fit(request)
    if request.get('operation') == 'propagate':
        return propagate(request)
    raise ValueError('未知计算请求')


if __name__ == '__main__':
    for line in sys.stdin:
        request = {}
        try:
            if len(line) > 2_000_000:
                raise ValueError('请求过大')
            request = json.loads(line)
            result = calculate(request['payload'])
            response = dict(id=request['id'], result=result)
            print(json.dumps(response, ensure_ascii=False, allow_nan=False), flush=True)
        except Exception as error:
            print(json.dumps(dict(id=request.get('id'), error=str(error) or type(error).__name__),
                             ensure_ascii=False), flush=True)
