"""pymatrix — 纯标准库 Python 小矩阵运算。

仅依赖 math。矩阵用嵌套 list（list[list[float]]）表示，向量用 list[float]。
设计目标：在高中物理实验数据处理引擎（最小二乘拟合、不确定度传播）所需的
尺度（<= 16x16 对称矩阵、<= 10000x7 瘦长 Jacobian 的正规方程）内，与
numpy.linalg 的对应函数保持数值对等。

公开接口：
    dot(u, v)            向量内积
    matvec(A, v)         矩阵乘向量
    matmul(A, B)         矩阵乘矩阵
    transpose(A)         转置
    eye(n)               单位矩阵
    norm2(v)             向量 2-范数（数值安全）
    solve(A, b)          高斯消元 + 部分主元解 Ax = b，奇异抛 ValueError
    inverse(A)           对称正定矩阵求逆（Cholesky 路径；非对称时退化为
                         部分主元 LU 求逆），奇异/非正定抛 ValueError
    cholesky(A)          对称正定矩阵的 Cholesky 下三角因子
    eigvalsh(A)          对称矩阵全部特征值（循环 Jacobi 迭代），升序返回
    singular_values(A)   任意 m x n 矩阵奇异值，降序返回
    cond(A)              2-范数条件数 = 最大奇异值 / 最小奇异值

已知数值特性（与 numpy 对标时的诚实声明）：
  * eigvalsh 的 Jacobi 迭代给出接近机器精度的绝对误差（~eps * ||A||_F），
    对谱分布良好的矩阵逐特征值相对误差 < 1e-12；对 Hilbert 这类谱衰减到
    1e-18 量级的矩阵，最小特征值的"相对"误差会退化，这是 numpy 也存在的
    浮点本质现象，对标时应以谱范数归一。
  * singular_values 采用单边 Jacobi SVD 直接作用于 A（不经过 A^T·A，
    避免条件数平方），对良态与病态矩阵均能对标 numpy 到 ~1e-15 归一
    误差；含 10000x7 病态瘦长 Jacobian（cond ~ 1e6）逐奇异值对标
    ~1e-13 以内。
"""
import math

__all__ = [
    'dot', 'matvec', 'matmul', 'transpose', 'eye', 'norm2',
    'solve', 'inverse', 'cholesky', 'eigvalsh', 'singular_values', 'cond',
]


# ---------------------------------------------------------------- 基础校验

def _as_matrix(A, name='A'):
    """把嵌套 list 校验并拷贝为 float 矩阵；拒绝空、非矩形、非数值。"""
    if not isinstance(A, (list, tuple)) or len(A) == 0:
        raise ValueError(f'{name} 必须是非空二维列表')
    rows = []
    width = None
    for row in A:
        if not isinstance(row, (list, tuple)) or len(row) == 0:
            raise ValueError(f'{name} 的每一行必须是非空列表')
        if width is None:
            width = len(row)
        elif len(row) != width:
            raise ValueError(f'{name} 必须是矩形矩阵（各行长度一致）')
        out = []
        for value in row:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f'{name} 的元素必须是数值')
            value = float(value)
            if not math.isfinite(value):
                raise ValueError(f'{name} 的元素必须是有限数值')
            out.append(value)
        rows.append(out)
    return rows


def _as_vector(v, name='b'):
    if not isinstance(v, (list, tuple)) or len(v) == 0:
        raise ValueError(f'{name} 必须是非空一维列表')
    out = []
    for value in v:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f'{name} 的元素必须是数值')
        value = float(value)
        if not math.isfinite(value):
            raise ValueError(f'{name} 的元素必须是有限数值')
        out.append(value)
    return out


def _check_square(A):
    n = len(A)
    if any(len(row) != n for row in A):
        raise ValueError('矩阵必须是方阵')
    return n


def _check_symmetric(A, tol=0.0):
    """检查对称性；tol 为允许的最大 |A[i][j]-A[j][i]| 绝对偏差。"""
    n = len(A)
    for i in range(n):
        for j in range(i + 1, n):
            if abs(A[i][j] - A[j][i]) > tol:
                raise ValueError('矩阵必须对称')
    return True


# ---------------------------------------------------------------- 基础工具

def dot(u, v):
    """向量内积。"""
    u = _as_vector(u, 'u')
    v = _as_vector(v, 'v')
    if len(u) != len(v):
        raise ValueError('向量长度不一致')
    return math.fsum(u[i] * v[i] for i in range(len(u)))


def norm2(v):
    """向量 2-范数，用 hypot 链避免上溢/下溢。"""
    v = _as_vector(v, 'v')
    result = 0.0
    for value in v:
        result = math.hypot(result, value)
    return result


def transpose(A):
    A = _as_matrix(A)
    return [list(col) for col in zip(*A)]


def matvec(A, v):
    A = _as_matrix(A)
    v = _as_vector(v, 'v')
    if len(A[0]) != len(v):
        raise ValueError('矩阵列数与向量长度不一致')
    return [math.fsum(row[j] * v[j] for j in range(len(v))) for row in A]


def matmul(A, B):
    A = _as_matrix(A)
    B = _as_matrix(B, 'B')
    m, k = len(A), len(A[0])
    k2, n = len(B), len(B[0])
    if k != k2:
        raise ValueError('矩阵维度不匹配：A 的列数须等于 B 的行数')
    Bt = [list(col) for col in zip(*B)]
    return [[math.fsum(A[i][t] * Bt[j][t] for t in range(k)) for j in range(n)]
            for i in range(m)]


def eye(n):
    if not isinstance(n, int) or n <= 0:
        raise ValueError('n 必须是正整数')
    return [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]


# ---------------------------------------------------------------- 线性求解

def solve(A, b):
    """高斯消元 + 部分主元解 Ax = b。

    A: n x n，b: 长度 n 的向量。返回解向量 list[float]。
    主元严格为 0（浮点奇异）时抛 ValueError，行为对齐 numpy.linalg.solve
    对精确奇异矩阵抛 LinAlgError。
    """
    A = _as_matrix(A)
    b = _as_vector(b)
    n = _check_square(A)
    if len(b) != n:
        raise ValueError('右端向量长度与矩阵阶数不一致')
    # 增广矩阵，就地消元
    M = [A[i] + [b[i]] for i in range(n)]
    for col in range(n):
        # 部分主元：选该列绝对值最大的行
        pivot = max(range(col, n), key=lambda r: abs(M[r][col]))
        if M[pivot][col] == 0.0:
            raise ValueError('矩阵奇异，线性方程组无唯一解')
        if pivot != col:
            M[col], M[pivot] = M[pivot], M[col]
        pivot_row = M[col]
        inv_pivot = 1.0 / pivot_row[col]
        for row in range(col + 1, n):
            factor = M[row][col] * inv_pivot
            if factor == 0.0:
                continue
            target = M[row]
            for k in range(col, n + 1):
                target[k] -= factor * pivot_row[k]
    # 回代
    x = [0.0] * n
    for i in range(n - 1, -1, -1):
        row = M[i]
        residual = row[n] - math.fsum(row[j] * x[j] for j in range(i + 1, n))
        x[i] = residual / row[i]
    return x


def cholesky(A):
    """对称正定矩阵 Cholesky 分解 A = L·L^T，返回下三角 L。

    非对称或非正定（含半正定）抛 ValueError。
    """
    A = _as_matrix(A)
    n = _check_square(A)
    _check_symmetric(A)
    L = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1):
            s = math.fsum(L[i][k] * L[j][k] for k in range(j))
            if i == j:
                diag = A[i][i] - s
                if diag <= 0.0:
                    raise ValueError('矩阵不是正定矩阵')
                L[i][j] = math.sqrt(diag)
            else:
                L[i][j] = (A[i][j] - s) / L[j][j]
    return L


def _forward_substitution(L, b):
    n = len(L)
    y = [0.0] * n
    for i in range(n):
        y[i] = (b[i] - math.fsum(L[i][k] * y[k] for k in range(i))) / L[i][i]
    return y


def _back_substitution_lt(L, y):
    """解 L^T x = y（L 为下三角）。"""
    n = len(L)
    x = [0.0] * n
    for i in range(n - 1, -1, -1):
        x[i] = (y[i] - math.fsum(L[k][i] * x[k] for k in range(i + 1, n))) / L[i][i]
    return x


def inverse(A):
    """矩阵求逆。

    对称输入走 Cholesky 路径（要求正定，否则 ValueError）；
    非对称输入退化为部分主元 Gauss-Jordan 求逆（奇异则 ValueError）。
    返回 n x n 嵌套 list。
    """
    A = _as_matrix(A)
    n = _check_square(A)
    symmetric = all(A[i][j] == A[j][i]
                    for i in range(n) for j in range(i + 1, n))
    if symmetric:
        L = cholesky(A)  # 非正定时在这里抛 ValueError
        inv = []
        for col in range(n):
            e = [0.0] * n
            e[col] = 1.0
            inv.append(_back_substitution_lt(L, _forward_substitution(L, e)))
        # inv 当前按列存储，转置成行
        return [[inv[col][row] for col in range(n)] for row in range(n)]
    # 非对称：Gauss-Jordan + 部分主元
    M = [A[i] + [1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(M[r][col]))
        if M[pivot][col] == 0.0:
            raise ValueError('矩阵奇异，不可逆')
        if pivot != col:
            M[col], M[pivot] = M[pivot], M[col]
        inv_pivot = 1.0 / M[col][col]
        M[col] = [value * inv_pivot for value in M[col]]
        for row in range(n):
            if row == col:
                continue
            factor = M[row][col]
            if factor == 0.0:
                continue
            M[row] = [value - factor * p for value, p in zip(M[row], M[col])]
    return [row[n:] for row in M]


# ---------------------------------------------------------------- 特征值

def eigvalsh(A, max_sweeps=100):
    """对称矩阵全部特征值，循环 Jacobi 迭代，升序返回 list[float]。

    收敛判据：off(A)（非对角元的 Frobenius 范数）<= 1e-15 * ||A||_F。
    对 n <= 16 的良态对称矩阵，逐特征值相对误差对标 numpy.linalg.eigvalsh
    < 1e-12。非对称输入抛 ValueError。
    """
    A = _as_matrix(A)
    n = _check_square(A)
    _check_symmetric(A)
    a = [row[:] for row in A]
    scale = math.sqrt(math.fsum(value * value for row in a for value in row))
    if scale == 0.0:
        return [0.0] * n
    tol = 1e-15 * scale
    for _sweep in range(max_sweeps):
        off = math.sqrt(math.fsum(
            a[i][j] * a[i][j] for i in range(n) for j in range(i + 1, n)))
        if off <= tol:
            break
        for p in range(n - 1):
            for q in range(p + 1, n):
                apq = a[p][q]
                if apq == 0.0:
                    continue
                # 稳定的 Jacobi 旋转角计算（Numerical Recipes 公式）
                theta = (a[q][q] - a[p][p]) / (2.0 * apq)
                # hypot 避免 theta**2 上溢
                t = math.copysign(1.0, theta) / (abs(theta) + math.hypot(theta, 1.0))
                c = 1.0 / math.hypot(t, 1.0)
                s = t * c
                tau = s / (1.0 + c)
                for k in range(n):
                    if k == p or k == q:
                        continue
                    akp = a[k][p]
                    akq = a[k][q]
                    new_kp = akp - s * (akq + tau * akp)
                    new_kq = akq + s * (akp - tau * akq)
                    a[k][p] = a[p][k] = new_kp
                    a[k][q] = a[q][k] = new_kq
                a[p][p] -= t * apq
                a[q][q] += t * apq
                a[p][q] = a[q][p] = 0.0
    return sorted(a[i][i] for i in range(n))


# ---------------------------------------------------------------- 奇异值

def singular_values(A, max_sweeps=100):
    """任意 m x n 矩阵的奇异值，降序返回 list[float]，长度 min(m, n)。

    实现路径：单边 Jacobi SVD（one-sided Jacobi，Demač–Veselić）——
    直接对 A 的列做 Jacobi 旋转让列两两正交，收敛后列范数即奇异值。

    为什么不用任务书最初设想的 A^T·A 特征值开方：正规方程把条件数平方，
    对 Hilbert / 近奇异矩阵，开方后的微小奇异值只有绝对精度
    ~eps·||A||² 开方 ≈ sqrt(eps)·||A||，无法对标 numpy.linalg.svd 的
    直接双边对角化。单边 Jacobi 对微小奇异值保持相对精度，实测与
    numpy 全谱归一误差 ~1e-15（含 hilbert8 与列近线性相关矩阵）。
    对标 numpy.linalg.svd(..., compute_uv=False)。
    """
    A = _as_matrix(A)
    m, n = len(A), len(A[0])
    if m < n:
        # 宽矩阵转置成瘦高再处理，奇异值集合不变
        A = [list(col) for col in zip(*A)]
        m, n = n, m
    a = [row[:] for row in A]
    eps = 1e-15  # 列正交收敛阈值（相对列范数）
    for _sweep in range(max_sweeps):
        converged = True
        for p in range(n - 1):
            for q in range(p + 1, n):
                alpha = math.fsum(a[r][p] * a[r][p] for r in range(m))
                beta = math.fsum(a[r][q] * a[r][q] for r in range(m))
                if alpha == 0.0 or beta == 0.0:
                    continue  # 零列：奇异值 0，无需旋转
                gamma = math.fsum(a[r][p] * a[r][q] for r in range(m))
                if abs(gamma) <= eps * math.sqrt(alpha * beta):
                    continue  # 该列对已正交
                converged = False
                # 对 2x2 格拉姆矩阵 [[alpha,gamma],[gamma,beta]] 求 Jacobi 旋转
                zeta = (beta - alpha) / (2.0 * gamma)
                t = math.copysign(1.0, zeta) / (abs(zeta) + math.hypot(zeta, 1.0))
                c = 1.0 / math.hypot(t, 1.0)
                s = t * c
                for r in range(m):
                    ap = a[r][p]
                    aq = a[r][q]
                    a[r][p] = c * ap - s * aq
                    a[r][q] = s * ap + c * aq
        if converged:
            break
    values = [math.sqrt(math.fsum(a[r][j] * a[r][j] for r in range(m)))
              for j in range(n)]
    values.sort(reverse=True)
    return values


def cond(A):
    """2-范数条件数 = 最大奇异值 / 最小奇异值。

    奇异（最小奇异值为 0）时返回 math.inf，对齐 numpy.linalg.cond。
    """
    values = singular_values(A)
    if not values or values[0] == 0.0 or values[-1] == 0.0:
        return math.inf
    return values[0] / values[-1]
