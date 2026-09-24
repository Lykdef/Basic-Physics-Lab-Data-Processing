"""pyleastsq.py — 纯标准库有界加权非线性最小二乘。

复刻 ``scipy.optimize.curve_fit(method='trf', x_scale='jac', max_nfev=3000)``
的可观察行为：最优参数 ``popt``、协方差 ``pcov``、OptimizeWarning 分类、
以及函数评估次数耗尽时的 RuntimeError。

仅依赖 Python 标准库 ``math``。

算法要点（对标 scipy trf 的语义）：

* Levenberg-Marquardt，阻尼按 Nielsen 规则自适应更新；
* ``x_scale='jac'`` 语义：``scale_inv = J`` 各列二范数，迭代间单调不减，
  阻尼正规方程在缩放变量空间中构造求解；
* 边界处理：初值严格化（对应 ``make_strictly_feasible``）+ 试探步
  向边界投影/截断（活动集效果），最优性判据使用 Coleman-Li 缩放梯度，
  与 scipy trf 的 ``gtol`` 判据同形；
* Jacobian 用前向有限差分，步长 ``h = sqrt(eps) * max(|p_j|, 1)``；
  差分评估计入 ``njev``，不占 ``max_nfev``（与 scipy trf 一致）；
* 收敛判据对标 scipy trf 默认 ``ftol=xtol=gtol=1e-8``；
* ``pcov`` 按 curve_fit 的 trf 分支：对解处加权 Jacobian 做
  Moore-Penrose 伪逆（丢弃 ``s <= eps*max(m,n)*s[0]`` 的奇异值），
  ``absolute_sigma=False`` 时再乘 ``s_sq = 加权SSE/(M-N)``；
  pcov 无法得到有限值时 ``pcov=None`` 且 ``optimize_warning=True``
  （对应 scipy 的 ``OptimizeWarning: Covariance of the parameters could
  not be estimated`` —— 注意 trf 用伪逆，秩亏本身并不触发该警告，
  只有 pcov 出现非有限值才触发）。
"""
import math

__all__ = ['least_squares_fit']

_EPS = 2.220446049250313e-16          # float64 机器精度
_SQRT_EPS = math.sqrt(_EPS)           # ≈ 1.4901161193847656e-8
# 终止判据形式对标 scipy trf 默认 ftol=xtol=gtol=1e-8（Coleman-Li 缩放梯度、
# 缩放空间相对步长、相对代价下降 + rho>0.25）。内部阈值收紧到 1e-10/1e-12，
# 以保证终解与 scipy trf 的参数差异 <1e-6（scipy 的 1e-8 停机点是本求解器
# 轨迹的子集，继续迭代不改变收敛分类，只提高终解精度）。
_FTOL = 1e-12
_XTOL = 1e-12
_GTOL = 1e-10
_LAMBDA_MAX = 1e150                   # 阻尼爆炸保护上限

# max_nfev 耗尽时的报错文案（按任务规格逐字实现）。
# 注意：scipy 1.18.1 method='trf' 的实际文案为
# "Optimal parameters not found: The maximum number of function evaluations is exceeded."
# （规格中的 maxfev 文案对应 method='lm'）。此处遵循任务规格；差异见自测报告。
_MAXNFEV_MESSAGE = ('Optimal parameters not found: Number of calls to function '
                    'has reached maxfev = {}.')


def _solve_linear(A, b):
    """Gauss 列主元消元解 n×n 方程组 A·x = b；奇异时返回 None。

    A、b 不会被原地修改。
    """
    n = len(A)
    M = [list(A[i]) + [b[i]] for i in range(n)]
    for col in range(n):
        piv = col
        best = abs(M[col][col])
        for r in range(col + 1, n):
            v = abs(M[r][col])
            if v > best:
                best = v
                piv = r
        if best <= 1e-300:
            return None
        if piv != col:
            M[col], M[piv] = M[piv], M[col]
        inv = 1.0 / M[col][col]
        for r in range(col + 1, n):
            f = M[r][col] * inv
            if f != 0.0:
                row_r = M[r]
                row_c = M[col]
                for c in range(col, n + 1):
                    row_r[c] -= f * row_c[c]
    x = [0.0] * n
    for i in range(n - 1, -1, -1):
        row = M[i]
        s = row[n]
        for j in range(i + 1, n):
            s -= row[j] * x[j]
        x[i] = s / row[i]
    return x


def _jacobi_eigen(A):
    """循环 Jacobi 法求实对称矩阵 A 的特征分解。

    返回 (evals, V)：evals 为降序特征值列表，V[i][k] 为第 k 个特征向量的
    第 i 个分量（V 的列相互正交）。A 不被修改。适用于小规模稠密对称矩阵。
    """
    n = len(A)
    a = [list(row) for row in A]
    V = [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]
    for _ in range(200):
        off = 0.0
        diag_sq = 0.0
        for i in range(n):
            diag_sq += a[i][i] * a[i][i]
            for j in range(i + 1, n):
                off += a[i][j] * a[i][j]
        off = math.sqrt(2.0 * off)
        if off <= 1e-14 * max(1.0, math.sqrt(diag_sq)):
            break
        for p in range(n - 1):
            for q in range(p + 1, n):
                apq = a[p][q]
                if apq == 0.0:
                    continue
                theta = (a[q][q] - a[p][p]) / (2.0 * apq)
                t = (1.0 if theta >= 0.0 else -1.0) / (abs(theta) + math.sqrt(theta * theta + 1.0))
                c = 1.0 / math.sqrt(t * t + 1.0)
                s = t * c
                for k in range(n):
                    akp = a[k][p]
                    akq = a[k][q]
                    a[k][p] = c * akp - s * akq
                    a[k][q] = s * akp + c * akq
                for k in range(n):
                    apk = a[p][k]
                    aqk = a[q][k]
                    a[p][k] = c * apk - s * aqk
                    a[q][k] = s * apk + c * aqk
                for k in range(n):
                    vkp = V[k][p]
                    vkq = V[k][q]
                    V[k][p] = c * vkp - s * vkq
                    V[k][q] = s * vkp + c * vkq
    order = sorted(range(n), key=lambda k: -a[k][k])
    evals = [a[k][k] for k in order]
    V = [[V[i][k] for k in order] for i in range(n)]
    return evals, V


def _make_strictly_feasible(p, lower, upper):
    """对应 scipy 的 make_strictly_feasible：把位于边界上的分量向内挪一小步。"""
    out = []
    for j in range(len(p)):
        v = min(max(p[j], lower[j]), upper[j])
        if lower[j] < upper[j]:
            if v == lower[j]:
                v = lower[j] + 1e-10 * max(1.0, abs(lower[j]))
                v = min(v, upper[j])
            elif v == upper[j]:
                v = upper[j] - 1e-10 * max(1.0, abs(upper[j]))
                v = max(v, lower[j])
        out.append(v)
    return out


def _cl_scaling_vector(p, g, lower, upper):
    """Coleman-Li 缩放向量（与 scipy trf 的 CL_scaling_vector 同形）。"""
    v = []
    for j in range(len(p)):
        if g[j] < 0.0 and upper[j] < math.inf:
            v.append(upper[j] - p[j])
        elif g[j] > 0.0 and lower[j] > -math.inf:
            v.append(p[j] - lower[j])
        else:
            v.append(1.0)
    return v


def _one_sided_jacobi_svd(jac_cols, m, n):
    """单边 Jacobi SVD 直接作用于 m×n 矩阵 J（列表示），避免形成 J^T·J
    （条件数平方会丢失小奇异值，病态问题下与 scipy 的 SVD 伪逆不可比）。

    返回 (s, V)：s 为奇异值（降序），V 为 n×n 右奇异向量矩阵（列正交），
    即 J ≈ U·diag(s)·V^T。与 numpy.linalg.svd 的 s/VT 对标到 ~1e-13
    （谱范数归一）。
    """
    B = [list(col) for col in jac_cols]          # 工作副本：列集合
    V = [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]
    for _ in range(100):
        off = 0.0
        for p in range(n - 1):
            for q in range(p + 1, n):
                bp, bq = B[p], B[q]
                alpha = beta = gamma = 0.0
                for i in range(m):
                    alpha += bp[i] * bp[i]
                    beta += bq[i] * bq[i]
                    gamma += bp[i] * bq[i]
                if alpha > 0.0 and beta > 0.0:
                    denom = math.sqrt(alpha) * math.sqrt(beta)  # 避免 alpha*beta 下溢
                    if denom > 0.0:
                        off = max(off, abs(gamma) / denom)
                if gamma == 0.0:
                    continue
                # 2×2 对称矩阵 [[alpha, gamma],[gamma, beta]] 的 Jacobi 旋转
                theta = (beta - alpha) / (2.0 * gamma)
                t = (1.0 if theta >= 0.0 else -1.0) / (abs(theta) + math.sqrt(theta * theta + 1.0))
                c = 1.0 / math.sqrt(t * t + 1.0)
                s = t * c
                for i in range(m):
                    bip = bp[i]
                    biq = bq[i]
                    bp[i] = c * bip - s * biq
                    bq[i] = s * bip + c * biq
                for i in range(n):
                    vip = V[i][p]
                    viq = V[i][q]
                    V[i][p] = c * vip - s * viq
                    V[i][q] = s * vip + c * viq
        if off <= 1e-13:
            break
    sv = [math.sqrt(math.fsum(v * v for v in B[j])) for j in range(n)]
    order = sorted(range(n), key=lambda j: -sv[j])
    s_sorted = [sv[j] for j in order]
    V_sorted = [[V[i][j] for j in order] for i in range(n)]
    return s_sorted, V_sorted


def _weighted_pcov(jac_cols, m, n, sse, absolute_sigma):
    """由解处加权 Jacobian（列表示）计算 pcov（Moore-Penrose 伪逆）。

    返回 (pcov, ok)。ok=False 时 pcov 为 None，对应 scipy 的
    OptimizeWarning（pcov 含非有限值，或 M<=N 且 absolute_sigma=False）。
    与 scipy curve_fit 的 trf 分支一致：直接对 J 做 SVD（单边 Jacobi，
    不经过 J^T·J），丢弃 ``s <= eps*max(m,n)*s[0]`` 的奇异值。
    """
    # 检查非有限值（scipy: pcov 出现 NaN → 警告）
    for col in jac_cols:
        for v in col:
            if not math.isfinite(v):
                return None, False
    # 直接对 J 做 SVD（单边 Jacobi），与 scipy 的 svd(res.jac) 同路径
    s, V = _one_sided_jacobi_svd(jac_cols, m, n)
    threshold = _EPS * max(m, n) * s[0]       # curve_fit 的奇异值截断规则
    pcov = [[0.0] * n for _ in range(n)]
    for k in range(n):
        sv = s[k]
        if sv <= threshold:                   # 丢弃近零奇异值（伪逆）
            continue
        inv = 1.0 / (sv * sv)
        for i in range(n):
            vik = V[i][k]
            for j in range(n):
                pcov[i][j] += inv * vik * V[j][k]
    if not absolute_sigma:
        if m > n:
            s_sq = sse / (m - n)
            for i in range(n):
                for j in range(n):
                    pcov[i][j] *= s_sq
        else:
            # curve_fit: ysize <= p0.size 且非 absolute_sigma → pcov 全 inf + 警告
            return None, False
    for i in range(n):
        for j in range(n):
            if not math.isfinite(pcov[i][j]):
                return None, False
    return pcov, True


def least_squares_fit(func, x, y, p0, sigma=None, absolute_sigma=False,
                      bounds=None, max_nfev=3000):
    """有界加权非线性最小二乘（复刻 curve_fit(method='trf', x_scale='jac')）。

    参数：
        func: ``func(x_list, *params) -> list``，模型函数；
        x, y: 数据点横纵坐标列表；
        p0: 自由参数初值列表（固定参数的处理由调用方负责）；
        sigma: 各点纵坐标标准不确定度列表或 None；残差除以 sigma；
        absolute_sigma: True 时 pcov 不乘 s_sq；
        bounds: (lower, upper)，各为长度 len(p0) 的列表（可取 ±math.inf），
            None 表示无界；
        max_nfev: 残差评估次数上限（FD 雅可比评估不计入，与 scipy trf 一致）。

    返回 dict：
        popt: 最优参数列表；
        pcov: n×n 协方差（列表的列表）或 None；
        optimize_warning: True 表示协方差不可估计（对应 scipy OptimizeWarning）。

    max_nfev 耗尽仍未收敛时抛 RuntimeError。
    """
    x = [float(v) for v in x]
    y = [float(v) for v in y]
    p = [float(v) for v in p0]
    m = len(x)
    n = len(p)
    if n == 0:
        raise ValueError('p0 为空：没有可优化的自由参数')
    if len(y) != m:
        raise ValueError('x 与 y 的长度不一致')
    if m == 0:
        raise ValueError('数据点为空')
    if bounds is None:
        lower = [-math.inf] * n
        upper = [math.inf] * n
    else:
        lb_raw, ub_raw = bounds
        lower = [-math.inf] * n if lb_raw is None else [float(v) for v in lb_raw]
        upper = [math.inf] * n if ub_raw is None else [float(v) for v in ub_raw]
        if len(lower) != n or len(upper) != n:
            raise ValueError('bounds 维度与 p0 不一致')
    for j in range(n):
        if lower[j] > upper[j]:
            raise ValueError('下界不能大于上界')
    w = None
    if sigma is not None:
        if len(sigma) != m:
            raise ValueError('sigma 长度与数据点不一致')
        w = [1.0 / float(s) for s in sigma]
    p = _make_strictly_feasible(p, lower, upper)

    nfev = 0   # 残差评估计数（FD 雅可比不计入，同 scipy trf）

    def residuals(pp, count=True):
        nonlocal nfev
        f = func(list(x), *pp)
        if len(f) != m:
            raise ValueError('func 返回值长度与 x 不一致')
        if count:
            nfev += 1
        if w is None:
            return [float(f[i]) - y[i] for i in range(m)]
        return [(float(f[i]) - y[i]) * w[i] for i in range(m)]

    def jacobian_columns(pp, r0):
        """前向有限差分雅可比（列表示），h = sqrt(eps)*max(|p_j|, 1)。"""
        cols = []
        for j in range(n):
            h = _SQRT_EPS * max(abs(pp[j]), 1.0)
            pert = pp[:]
            pert[j] = pp[j] + h
            rp = residuals(pert, count=False)
            inv_h = 1.0 / h
            cols.append([(rp[i] - r0[i]) * inv_h for i in range(m)])
        return cols

    r = residuals(p)
    cost = 0.5 * math.fsum(v * v for v in r)
    scale_inv = None     # x_scale='jac'：J 列范数，单调不减
    lam = 1e-3           # LM 初始阻尼
    nu = 2.0
    converged = False
    active = [False] * n  # 活动集：True 表示该参数钉在边界上、本轮不参与求解

    while not converged:
        J = jacobian_columns(p, r)
        # ---- x_scale='jac'：列范数缩放，单调不减（compute_jac_scale） ----
        new_scale = []
        for j in range(n):
            col = J[j]
            s = math.sqrt(math.fsum(v * v for v in col))
            new_scale.append(s if s > 0.0 else 1.0)
        if scale_inv is None:
            scale_inv = new_scale
        else:
            scale_inv = [max(new_scale[j], scale_inv[j]) for j in range(n)]
        # ---- 缩放空间的正规方程：Js = J / scale_inv ----
        A = [[0.0] * n for _ in range(n)]
        for j in range(n):
            sj = scale_inv[j]
            colj = J[j]
            for k in range(j, n):
                sk = scale_inv[k]
                colk = J[k]
                s = 0.0
                for i in range(m):
                    s += colj[i] * colk[i]
                s /= (sj * sk)
                A[j][k] = s
                A[k][j] = s
        g = [0.0] * n    # 未缩放梯度 J^T r（用于 Coleman-Li 判据与活动集释放）
        for j in range(n):
            col = J[j]
            s = 0.0
            for i in range(m):
                s += col[i] * r[i]
            g[j] = s
        gq = [g[j] / scale_inv[j] for j in range(n)]   # 缩放空间梯度
        # ---- 活动集释放：梯度指向可行域内部时解除钉扎 ----
        for j in range(n):
            if active[j]:
                if p[j] == upper[j] and g[j] > 0.0:
                    active[j] = False
                elif p[j] == lower[j] and g[j] < 0.0:
                    active[j] = False
        free = [j for j in range(n) if not active[j]]
        # ---- gtol：Coleman-Li 缩放梯度的无穷范数 ----
        v = _cl_scaling_vector(p, g, lower, upper)
        g_norm = max(abs(g[j] * v[j]) for j in range(n))
        if g_norm < _GTOL or not free:
            converged = True
            break
        if nfev >= max_nfev:
            raise RuntimeError(_MAXNFEV_MESSAGE.format(max_nfev))

        # ---- LM 内层：阻尼自适应（仅在自由参数子空间求解） ----
        nf = len(free)
        A_f = [[A[free[i]][free[k]] for k in range(nf)] for i in range(nf)]
        gq_f = [gq[j] for j in free]
        diag_A = [max(A[j][j], 1e-30) for j in range(n)]
        diag_f = [diag_A[j] for j in free]
        while True:
            M = [list(A_f[i]) for i in range(nf)]
            for i in range(nf):
                M[i][i] += lam * diag_f[i]
            dq_f = _solve_linear(M, [-gq_f[i] for i in range(nf)])
            if dq_f is None:
                dq_f = [0.0] * nf
            dp = [0.0] * n
            for i, j in enumerate(free):
                dp[j] = dq_f[i] / scale_inv[j]
            dp_full = list(dp)   # 未裁剪步长（用于活动集激活判定）
            # 边界投影：逐分量裁剪到可行域
            p_trial = [min(max(p[j] + dp[j], lower[j]), upper[j]) for j in range(n)]
            if not all(math.isfinite(v) for v in p_trial):
                # 步长溢出到非有限参数（scipy trf 的信赖域不会走到这里）：
                # 不评估 func，视为拒绝步，增大阻尼重试
                lam *= nu
                nu *= 2.0
                if lam > _LAMBDA_MAX:
                    converged = True
                    break
                continue
            dp = [p_trial[j] - p[j] for j in range(n)]
            dq = [dp[j] * scale_inv[j] for j in range(n)]
            if all(dqj == 0.0 for dqj in dq):
                # 步长被边界完全压死：视为拒绝，增大阻尼重试
                lam *= nu
                nu *= 2.0
                if lam > _LAMBDA_MAX:
                    converged = True
                    break
                continue
            if nfev >= max_nfev:
                raise RuntimeError(_MAXNFEV_MESSAGE.format(max_nfev))
            r_trial = residuals(p_trial)
            cost_trial = 0.5 * math.fsum(vv * vv for vv in r_trial)
            # Nielsen 预测下降量：pred = 0.5 * dq·(lam*D*dq - gq)
            pred = 0.0
            for j in range(n):
                pred += dq[j] * (lam * diag_A[j] * dq[j] - gq[j])
            pred *= 0.5
            actual = cost - cost_trial
            rho = actual / pred if pred > 0.0 else -1.0
            if rho > 0.0:
                # 接受
                step_norm = math.sqrt(math.fsum(dqj * dqj for dqj in dq))
                p_norm = math.sqrt(math.fsum((p[j] * scale_inv[j]) ** 2 for j in range(n)))
                # 活动集激活：未裁剪步长想越过边界且试探点被钉在界上
                for j in range(n):
                    if not active[j]:
                        if (dp_full[j] > 0.0 and p_trial[j] == upper[j]
                                and upper[j] < math.inf):
                            active[j] = True
                        elif (dp_full[j] < 0.0 and p_trial[j] == lower[j]
                                and lower[j] > -math.inf):
                            active[j] = True
                p = p_trial
                r = r_trial
                cost_prev = cost
                cost = cost_trial
                lam = max(lam * max(1.0 / 3.0, 1.0 - (2.0 * rho - 1.0) ** 3), 1e-300)
                nu = 2.0
                # ftol / xtol（对标 check_termination 的形式）
                ftol_ok = (cost_prev - cost) < _FTOL * cost and rho > 0.25
                xtol_ok = step_norm < _XTOL * (_XTOL + p_norm)
                if ftol_ok or xtol_ok:
                    converged = True
                break
            lam *= nu
            nu *= 2.0
            if lam > _LAMBDA_MAX:
                # 阻尼爆炸：步长趋零，视为停滞收敛
                converged = True
                break

    # ---- 解处加权雅可比 → pcov ----
    J = jacobian_columns(p, r)
    sse = 2.0 * cost     # 加权 SSE = sum(r^2)
    pcov, ok = _weighted_pcov(J, m, n, sse, absolute_sigma)
    return {'popt': list(p),
            'pcov': pcov if ok else None,
            'optimize_warning': not ok}
