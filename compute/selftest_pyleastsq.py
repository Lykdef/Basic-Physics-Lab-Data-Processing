"""selftest_pyleastsq.py — pyleastsq 模块独立自测 + scipy 对等校验。

用法：
    python selftest_pyleastsq.py            # 纯标准库解释器：仅功能自测
    .venv-webview\\Scripts\\python.exe selftest_pyleastsq.py
                                            # venv 神谕：功能自测 + scipy 对等校验

退出码 0 表示全部通过，1 表示存在失败项。
"""
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pyleastsq import least_squares_fit

_CHECKS = [0]
_FAILURES = []


def check(cond, label, detail=''):
    _CHECKS[0] += 1
    if cond:
        print('  PASS  %s' % label)
    else:
        print('  FAIL  %s  %s' % (label, detail))
        _FAILURES.append(label)


def rel_err(a, b):
    return abs(a - b) / max(abs(b), 1e-30)


def linspace(a, b, m):
    if m == 1:
        return [(a + b) / 2.0]
    return [a + (b - a) * i / (m - 1) for i in range(m)]


# ---------------------------------------------------------------- 模型定义
def f_linear(xs, a, b):
    return [a * xv + b for xv in xs]


def f_origin(xs, a):
    return [a * xv for xv in xs]


def make_poly(deg):
    def f(xs, *p):
        out = []
        for xv in xs:
            acc = 0.0
            for c in reversed(p):
                acc = acc * xv + c
            out.append(acc)
        return out
    return f


def f_exp(xs, a, b, c):
    return [a * math.exp(b * xv) + c for xv in xs]


def f_power(xs, a, b):
    return [a * xv ** b for xv in xs]


def f_log(xs, a, b):
    return [a * math.log(xv) + b for xv in xs]


POLY_COEFS = [0.5, -0.4, 0.3, -0.2, 0.15, -0.1, 0.05]


def make_noisy(f, truth, xs, sigma, seed):
    rng = random.Random(seed)
    return [f([xv], *truth)[0] + rng.gauss(0.0, sigma) for xv in xs]


# ---------------------------------------------------------------- 第一部分
# 纯标准库功能自测（两个解释器都运行）
def pure_tests():
    print('== 第一部分：纯标准库功能自测 ==')

    # 1. 无噪声线性：精确复原参数
    xs = linspace(-2.0, 3.0, 20)
    ys = [2.5 * xv - 1.0 for xv in xs]
    res = least_squares_fit(f_linear, xs, ys, [1.0, 0.0])
    check(rel_err(res['popt'][0], 2.5) < 1e-9 and rel_err(res['popt'][1], -1.0) < 1e-9,
          'pure/linear-exact-popt', str(res['popt']))
    check(res['optimize_warning'] is False and res['pcov'] is not None,
          'pure/linear-exact-classification')
    check(all(abs(res['pcov'][i][j]) < 1e-20 for i in range(2) for j in range(2)),
          'pure/linear-exact-pcov-zero', str(res['pcov']))

    # 2. 加权线性回归：与解析解比较（absolute_sigma=True）
    xs = linspace(0.0, 4.0, 9)
    sig = [0.1 + 0.05 * i for i in range(9)]
    ys = [1.2 * xv + 0.7 + (0.03 if i % 2 else -0.02) for i, xv in enumerate(xs)]
    res = least_squares_fit(f_linear, xs, ys, [1.0, 0.0], sigma=sig, absolute_sigma=True)
    # 解析加权最小二乘
    w = [1.0 / s ** 2 for s in sig]
    S = sum(w); Sx = sum(w[i] * xs[i] for i in range(9))
    Sy = sum(w[i] * ys[i] for i in range(9))
    Sxx = sum(w[i] * xs[i] ** 2 for i in range(9))
    Sxy = sum(w[i] * xs[i] * ys[i] for i in range(9))
    D = S * Sxx - Sx * Sx
    a_ref = (S * Sxy - Sx * Sy) / D
    b_ref = (Sxx * Sy - Sx * Sxy) / D
    cov_ref = [[S / D, -Sx / D], [-Sx / D, Sxx / D]]
    check(rel_err(res['popt'][0], a_ref) < 1e-7 and rel_err(res['popt'][1], b_ref) < 1e-7,
          'pure/weighted-linear-popt', '%s vs %s' % (res['popt'], [a_ref, b_ref]))
    pcov_err = max(rel_err(res['pcov'][i][j], cov_ref[i][j]) for i in range(2) for j in range(2))
    check(pcov_err < 1e-6, 'pure/weighted-linear-pcov', 'rel_err=%g' % pcov_err)

    # 3. absolute_sigma 缩放不变性：sigma 乘 k，popt 不变；
    #    absolute_sigma=True 时 pcov 乘 k^2；False 时 pcov 不变
    xs = linspace(0.0, 4.0, 30)
    ys = make_noisy(f_linear, [2.0, -0.5], xs, 0.05, 7)
    sig1 = [0.05] * 30
    sig2 = [0.5] * 30
    r1a = least_squares_fit(f_linear, xs, ys, [1.0, 0.0], sigma=sig1, absolute_sigma=True)
    r2a = least_squares_fit(f_linear, xs, ys, [1.0, 0.0], sigma=sig2, absolute_sigma=True)
    r1r = least_squares_fit(f_linear, xs, ys, [1.0, 0.0], sigma=sig1, absolute_sigma=False)
    r2r = least_squares_fit(f_linear, xs, ys, [1.0, 0.0], sigma=sig2, absolute_sigma=False)
    # 注：gtol 按加权梯度判定，sigma 缩放后终止迭代点略有不同，容差放宽到 1e-6
    check(all(rel_err(r1a['popt'][j], r2a['popt'][j]) < 1e-6 for j in range(2)),
          'pure/sigma-scale-popt-invariant')
    ratio = r2a['pcov'][0][0] / r1a['pcov'][0][0]
    check(abs(ratio - 100.0) / 100.0 < 1e-8, 'pure/sigma-scale-pcov-abs', 'ratio=%g' % ratio)
    check(rel_err(r1r['pcov'][0][0], r2r['pcov'][0][0]) < 1e-6,
          'pure/sigma-scale-pcov-rel-invariant')

    # 4. 边界激活：真值 a=2.0 在界外，上界 1.5 → 解钉在 1.5
    xs = linspace(-1.0, 2.0, 30)
    ys = make_noisy(f_linear, [2.0, 0.3], xs, 0.02, 11)
    res = least_squares_fit(f_linear, xs, ys, [1.0, 0.0],
                            bounds=([-math.inf, -math.inf], [1.5, math.inf]))
    check(abs(res['popt'][0] - 1.5) < 1e-9, 'pure/bound-clamped', str(res['popt']))
    check(all(-math.inf <= res['popt'][j] <= math.inf for j in range(2))
          and res['popt'][0] <= 1.5, 'pure/bound-respected')

    # 5. 边界真值恰在界上：a 上界 = 2.0 = 真值
    res = least_squares_fit(f_linear, xs, ys, [1.0, 0.0],
                            bounds=([-math.inf, -math.inf], [2.0, math.inf]))
    check(res['popt'][0] <= 2.0 + 1e-12 and abs(res['popt'][0] - 2.0) < 1e-4,
          'pure/bound-at-truth', str(res['popt']))
    check(res['optimize_warning'] is False and res['pcov'] is not None,
          'pure/bound-at-truth-classification')

    # 6. 秩亏分类（对标 scipy trf 的可观察行为：伪逆不报警、pcov 有限）
    #    常数数据 + 指数模型初值 a=0 → b 不可辨识
    xs = linspace(0.1, 2.0, 20)
    ys = [3.0] * 20
    res = least_squares_fit(f_exp, xs, ys, [0.0, 1.0, 3.0])
    check(res['optimize_warning'] is False and res['pcov'] is not None,
          'pure/rankdef-pseudoinverse-classification')
    check(all(math.isfinite(res['pcov'][i][j]) for i in range(3) for j in range(3)),
          'pure/rankdef-pcov-finite')

    # 7. max_nfev 耗尽 → RuntimeError，文案逐字匹配任务规格
    xs = linspace(0.0, 2.0, 50)
    ys = make_noisy(f_exp, [1.5, 0.8, -0.5], xs, 0.01, 13)
    try:
        least_squares_fit(f_exp, xs, ys, [3.0, -2.0, 5.0], max_nfev=1)
        check(False, 'pure/maxnfev-raises')
    except RuntimeError as e:
        check(str(e) == 'Optimal parameters not found: Number of calls to function '
                        'has reached maxfev = 1.',
              'pure/maxnfev-message', repr(str(e)))

    # 8. 指数模型收敛（无噪声）
    xs = linspace(0.0, 2.0, 50)
    ys = [1.5 * math.exp(0.8 * xv) - 0.5 for xv in xs]
    res = least_squares_fit(f_exp, xs, ys, [1.0, 0.5, 0.0])
    err = max(rel_err(res['popt'][j], [1.5, 0.8, -0.5][j]) for j in range(3))
    check(err < 1e-7, 'pure/exp-exact-popt', 'rel_err=%g' % err)

    # 9. pcov = (J^T W J)^-1 语义：无权重、absolute_sigma=True 时
    #    与解析公式一致（已在 #2 覆盖加权情形，这里验证 sigma=None）
    xs = linspace(0.0, 4.0, 9)
    ys = [1.2 * xv + 0.7 + (0.03 if i % 2 else -0.02) for i, xv in enumerate(xs)]
    res = least_squares_fit(f_linear, xs, ys, [1.0, 0.0], absolute_sigma=True)
    S = 9.0; Sx = sum(xs); Sxx = sum(v * v for v in xs)
    D = S * Sxx - Sx * Sx
    cov_ref = [[S / D, -Sx / D], [-Sx / D, Sxx / D]]
    pcov_err = max(rel_err(res['pcov'][i][j], cov_ref[i][j]) for i in range(2) for j in range(2))
    check(pcov_err < 1e-6, 'pure/unweighted-pcov-absolute', 'rel_err=%g' % pcov_err)


# ---------------------------------------------------------------- 第二部分
# scipy 对等校验（仅当 numpy/scipy 可用时运行）
def oracle_tests():
    try:
        import warnings
        import numpy as np
        from scipy.optimize import curve_fit, OptimizeWarning
    except ImportError:
        print('== 第二部分：scipy 对等校验 ==  SKIPPED（当前解释器无 numpy/scipy）')
        return
    print('== 第二部分：scipy 对等校验（venv 神谕）==')

    np_models = {
        'linear': (lambda x, a, b: a * x + b),
        'origin': (lambda x, a: a * x),
        'exponential': (lambda x, a, b, c: a * np.exp(b * x) + c),
        'power': (lambda x, a, b: a * np.power(x, b)),
        'logarithmic': (lambda x, a, b: a * np.log(x) + b),
    }
    for d in range(1, 7):
        np_models['poly%d' % d] = (
            lambda x, *p, _d=d: np.polynomial.polynomial.polyval(x, p))
    py_models = {
        'linear': f_linear, 'origin': f_origin, 'exponential': f_exp,
        'power': f_power, 'logarithmic': f_log,
    }
    for d in range(1, 7):
        py_models['poly%d' % d] = make_poly(d)

    truths = {
        'linear': [2.0, -1.0], 'origin': [1.5],
        'exponential': [1.5, 0.8, -0.5], 'power': [2.0, 1.5], 'logarithmic': [1.2, 0.3],
    }
    for d in range(1, 7):
        truths['poly%d' % d] = POLY_COEFS[:d + 1]
    xranges = {
        'linear': (-2.0, 3.0), 'origin': (-2.0, 3.0),
        'exponential': (0.0, 2.0), 'power': (0.5, 4.0), 'logarithmic': (0.2, 5.0),
    }
    for d in range(1, 7):
        xranges['poly%d' % d] = (-1.5, 1.5)

    def run_pair(label, name, xs, ys, sigma, absolute_sigma, bounds_py, bounds_np,
                 compare_params=True, compare_pcov=True, max_nfev=3000):
        f_np = np_models[name]
        f_py = py_models[name]
        truth = truths[name]
        # 初值扰动真值并夹入边界（引擎调用前会校验可行性，此处对齐该约定）
        p0 = [min(max(t * 0.6 + 0.2, bounds_py[0][j]), bounds_py[1][j])
              for j, t in enumerate(truth)]
        xa = np.asarray(xs, dtype=float)
        ya = np.asarray(ys, dtype=float)
        sa = None if sigma is None else np.asarray(sigma, dtype=float)
        sp_err = None
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            try:
                popt_s, pcov_s = curve_fit(f_np, xa, ya, p0=list(p0), sigma=sa,
                                           absolute_sigma=absolute_sigma,
                                           bounds=bounds_np, method='trf',
                                           max_nfev=max_nfev, x_scale='jac')
            except RuntimeError as e:
                sp_err = str(e)
                popt_s = pcov_s = None
        sp_warned = any(issubclass(c.category, OptimizeWarning) for c in caught)
        py_err = None
        try:
            res = least_squares_fit(f_py, list(xs), list(ys), list(p0), sigma=sigma,
                                    absolute_sigma=absolute_sigma, bounds=bounds_py,
                                    max_nfev=max_nfev)
        except RuntimeError as e:
            py_err = str(e)
            res = None
        # 报错分类一致
        check((sp_err is None) == (py_err is None),
              label + '/error-classification', 'scipy=%r pure=%r' % (sp_err, py_err))
        if sp_err is not None or py_err is not None:
            return
        # 警告 / pcov 可估计性分类一致
        check(sp_warned == res['optimize_warning'],
              label + '/warning-classification',
              'scipy_warned=%s pure=%s' % (sp_warned, res['optimize_warning']))
        sp_cov_ok = (pcov_s is not None) and bool(np.all(np.isfinite(pcov_s)))
        check(sp_cov_ok == (res['pcov'] is not None),
              label + '/pcov-none-classification',
              'scipy_finite=%s pure_None=%s' % (sp_cov_ok, res['pcov'] is None))
        # 参数相对误差
        if compare_params:
            err = max(rel_err(res['popt'][j], float(popt_s[j])) for j in range(len(p0)))
            check(err < 1e-6, label + '/popt-rel-err<1e-6', 'rel_err=%.3g' % err)
        # pcov 相对误差（良态且双方可估计时；矩阵尺度：max|A-B|/max|B|，
        # 避免近零的非对角元素使逐元素相对误差失真）
        if compare_pcov and sp_cov_ok and res['pcov'] is not None and not sp_warned:
            scale = max(abs(float(pcov_s[i][j])) for i in range(len(p0))
                        for j in range(len(p0)))
            scale = max(scale, 1e-300)
            err = max(abs(res['pcov'][i][j] - float(pcov_s[i][j]))
                      for i in range(len(p0)) for j in range(len(p0))) / scale
            check(err < 1e-4, label + '/pcov-rel-err<1e-4', 'rel_err=%.3g' % err)

    # ---- 主套件：模型 × 规模 ----
    sizes = [5, 20, 100, 10000]
    noise = 0.05
    case_no = 0
    for name in ['linear', 'origin'] + ['poly%d' % d for d in range(1, 7)] + \
                ['exponential', 'power', 'logarithmic']:
        n_par = len(truths[name])
        for m in sizes:
            case_no += 1
            label = 'oracle/%s@m%d' % (name, m)
            lo, hi = xranges[name]
            xs = linspace(lo, hi, m)
            ys = make_noisy(py_models[name], truths[name], xs, noise, 1000 + case_no)
            if m <= n_par:
                # m <= n：scipy（非 absolute_sigma）pcov=inf+警告；欠定时参数不比较
                run_pair(label, name, xs, ys, None, False,
                         ([-math.inf] * n_par, [math.inf] * n_par),
                         (np.full(n_par, -np.inf), np.full(n_par, np.inf)),
                         compare_params=(m == n_par), compare_pcov=False)
            else:
                run_pair(label, name, xs, ys, None, False,
                         ([-math.inf] * n_par, [math.inf] * n_par),
                         (np.full(n_par, -np.inf), np.full(n_par, np.inf)))

    # ---- 加权套件 ----
    for name, m, abs_sig in [('linear', 100, True), ('linear', 10000, False),
                             ('exponential', 100, True), ('poly3', 20, False),
                             ('power', 100, True), ('logarithmic', 20, False)]:
        label = 'oracle/weighted-%s@m%d-abs%s' % (name, m, abs_sig)
        lo, hi = xranges[name]
        xs = linspace(lo, hi, m)
        sigma = [noise * (1.0 + (i % 7) * 0.15) for i in range(m)]
        rng = random.Random(555)
        ys = [py_models[name]([xv], *truths[name])[0] + rng.gauss(0.0, sigma[i])
              for i, xv in enumerate(xs)]
        n_par = len(truths[name])
        run_pair(label, name, xs, ys, sigma, abs_sig,
                 ([-math.inf] * n_par, [math.inf] * n_par),
                 (np.full(n_par, -np.inf), np.full(n_par, np.inf)))

    # ---- 边界激活情形 ----
    # B1：真值恰在界上（a 上界 = 真值 2.0）
    xs = linspace(-1.0, 2.0, 30)
    ys = make_noisy(f_linear, [2.0, 0.3], xs, 0.02, 21)
    run_pair('oracle/bound-true-on-bound', 'linear', xs, ys, None, False,
             ([-math.inf, -math.inf], [2.0, math.inf]),
             (np.array([-np.inf, -np.inf]), np.array([2.0, np.inf])))
    # B2：界比无约束最优更紧（指数 c 上界 -1.0 < 真值 -0.5）
    xs = linspace(0.0, 2.0, 100)
    ys = make_noisy(f_exp, [1.5, 0.8, -0.5], xs, 0.02, 22)
    run_pair('oracle/bound-tight-exp', 'exponential', xs, ys, None, False,
             ([-math.inf, -math.inf, -math.inf], [math.inf, math.inf, -1.0]),
             (np.full(3, -np.inf), np.array([np.inf, np.inf, -1.0])))
    # B3：加权 + 边界
    xs = linspace(0.5, 4.0, 50)
    sigma = [0.05] * 50
    rng = random.Random(23)
    ys = [2.0 * xv ** 1.5 + rng.gauss(0.0, 0.05) for xv in xs]
    run_pair('oracle/bound-weighted-power', 'power', xs, ys, sigma, True,
             ([-math.inf, -math.inf], [2.0, math.inf]),
             (np.array([-np.inf, -np.inf]), np.array([2.0, np.inf])))

    # ---- 秩亏 / 精确拟合分类 ----
    # R1：无噪声精确落在模型上（良态）→ 双方均应无警告、pcov 有限（≈0）
    xs = linspace(0.0, 3.0, 20)
    ys = [2.5 * xv + 1.0 for xv in xs]
    run_pair('oracle/exact-fit', 'linear', xs, ys, None, False,
             ([-math.inf] * 2, [math.inf] * 2),
             (np.full(2, -np.inf), np.full(2, np.inf)), compare_pcov=False)
    # R2：秩亏（常数数据 + 指数模型 a=0，b 不可辨识）
    xs = linspace(0.1, 2.0, 20)
    ys = [3.0] * 20
    run_pair('oracle/rankdef-const-exp', 'exponential', xs, ys, None, False,
             ([-math.inf] * 3, [math.inf] * 3),
             (np.full(3, -np.inf), np.full(3, np.inf)),
             compare_params=False, compare_pcov=False)
    # R3：m == n（poly4 @ m=5，非 absolute_sigma）→ 双方均应警告 + pcov 不可用
    xs = linspace(-1.5, 1.5, 5)
    ys = make_noisy(py_models['poly4'], truths['poly4'], xs, 0.02, 31)
    run_pair('oracle/square-system-poly4', 'poly4', xs, ys, None, False,
             ([-math.inf] * 5, [math.inf] * 5),
             (np.full(5, -np.inf), np.full(5, np.inf)), compare_pcov=False)

    # ---- max_nfev 耗尽：双方都应抛 RuntimeError ----
    xs = linspace(0.0, 2.0, 50)
    ys = make_noisy(f_exp, [1.5, 0.8, -0.5], xs, 0.01, 41)
    xa = np.asarray(xs); ya = np.asarray(ys)
    sp_msg = None
    try:
        curve_fit(np_models['exponential'], xa, ya, p0=[3.0, -2.0, 5.0],
                  method='trf', max_nfev=1, x_scale='jac')
    except RuntimeError as e:
        sp_msg = str(e)
    py_msg = None
    try:
        least_squares_fit(f_exp, xs, ys, [3.0, -2.0, 5.0], max_nfev=1)
    except RuntimeError as e:
        py_msg = str(e)
    check(sp_msg is not None and py_msg is not None, 'oracle/maxnfev-both-raise',
          'scipy=%r pure=%r' % (sp_msg, py_msg))
    check(py_msg == 'Optimal parameters not found: Number of calls to function '
                    'has reached maxfev = 1.',
          'oracle/maxnfev-pure-message-spec', repr(py_msg))
    print('  NOTE  scipy 1.18.1 trf 实际文案: %r' % sp_msg)
    print('  NOTE  本模块文案按任务规格:      %r' % py_msg)


def main():
    pure_tests()
    oracle_tests()
    print()
    print('共 %d 项检查，失败 %d 项' % (_CHECKS[0], len(_FAILURES)))
    if _FAILURES:
        print('失败项：')
        for f in _FAILURES:
            print('  - %s' % f)
        return 1
    print('RESULT: ALL PASS')
    return 0


if __name__ == '__main__':
    sys.exit(main())
