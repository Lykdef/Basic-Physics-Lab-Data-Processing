"""selftest_pymatrix.py — pymatrix 独立自测 + 与 numpy 的神谕对照。

用法：
    python selftest_pymatrix.py            # 纯标准库解释器：内置断言 + 不变量校验
    .venv-webview\\Scripts\\python.exe selftest_pymatrix.py
                                           # 带 numpy 的解释器：额外逐案对照 numpy

退出码：全部通过 0，任一失败 1。numpy 缺失时自动跳过对照段（不算失败）。
"""
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pymatrix as pm

try:
    import numpy as np
except ImportError:
    np = None

FAILURES = []
REPORTS = []


def check(name, condition, detail=''):
    status = 'PASS' if condition else 'FAIL'
    print(f'[{status}] {name}' + (f'  ({detail})' if detail else ''))
    if not condition:
        FAILURES.append(name)


def report(name, detail):
    REPORTS.append((name, detail))
    print(f'[INFO] {name}: {detail}')


def rel_diff(a, b):
    denom = max(abs(b), 1e-300)
    return abs(a - b) / denom


def max_list_rel_diff(mine, oracle):
    return max(rel_diff(a, b) for a, b in zip(mine, oracle)) if oracle else 0.0


def hilbert(n):
    return [[1.0 / (i + j + 1) for j in range(n)] for i in range(n)]


def random_symmetric(n, seed):
    rng = random.Random(seed)
    base = [[rng.uniform(-1, 1) for _ in range(n)] for _ in range(n)]
    return [[base[i][j] + base[j][i] for j in range(n)] for i in range(n)]


def random_matrix(m, n, seed):
    rng = random.Random(seed)
    return [[rng.uniform(-1, 1) for _ in range(n)] for _ in range(m)]


def random_spd(n, seed):
    R = random_matrix(n, n, seed)
    RtR = pm.matmul(pm.transpose(R), R)
    return [[RtR[i][j] + (n if i == j else 0.0) for j in range(n)] for i in range(n)]


def expect_raises(name, exc, fn, *args):
    try:
        fn(*args)
    except exc:
        check(name, True)
    except Exception as error:  # noqa: BLE001
        check(name, False, f'抛错类型不对: {type(error).__name__}: {error}')
    else:
        check(name, False, '未抛出预期异常')


# ---------------------------------------------------------------- 1. 基础工具

def test_basics():
    check('transpose', pm.transpose([[1, 2, 3], [4, 5, 6]]) == [[1, 4], [2, 5], [3, 6]])
    check('dot', pm.dot([1, 2, 3], [4, 5, 6]) == 32.0)
    check('matvec', pm.matvec([[1, 2], [3, 4]], [5, 6]) == [17.0, 39.0])
    check('matmul', pm.matmul([[1, 2], [3, 4]], [[5, 6], [7, 8]]) == [[19.0, 22.0], [43.0, 50.0]])
    check('norm2 防溢出', rel_diff(pm.norm2([3e200, 4e200]), 5e200) < 1e-15)
    check('eye', pm.eye(2) == [[1.0, 0.0], [0.0, 1.0]])
    expect_raises('transpose 非矩形', ValueError, pm.transpose, [[1, 2], [3]])
    expect_raises('matmul 维度不匹配', ValueError, pm.matmul, [[1, 2]], [[1, 2]])


# ---------------------------------------------------------------- 2. solve

def test_solve():
    x = pm.solve([[2, 1], [1, 3]], [1, 2])
    check('solve 2x2', abs(x[0] - 0.2) < 1e-15 and abs(x[1] - 0.6) < 1e-15, str(x))

    # Hilbert 8x8，真解全 1：残差校验（解本身因病态有误差，残差必须小）
    n = 8
    H = hilbert(n)
    b = [math.fsum(row) for row in H]
    x = pm.solve(H, b)
    residual = pm.norm2([pm.dot(H[i], x) - b[i] for i in range(n)])
    check('solve hilbert8 残差', residual < 1e-8, f'残差={residual:.3e}')
    err = max(abs(v - 1.0) for v in x)
    report('solve hilbert8 解误差(病态预期)', f'max|x-1|={err:.3e}')

    expect_raises('solve 奇异矩阵', ValueError, pm.solve, [[1, 2], [2, 4]], [1, 2])
    expect_raises('solve 非方阵', ValueError, pm.solve, [[1, 2, 3], [4, 5, 6]], [1, 2])


# ---------------------------------------------------------------- 3. inverse

def test_inverse():
    inv = pm.inverse([[4, 2], [2, 3]])
    expect = [[3 / 8, -2 / 8], [-2 / 8, 4 / 8]]
    err = max(abs(inv[i][j] - expect[i][j]) for i in range(2) for j in range(2))
    check('inverse 2x2 SPD', err < 1e-15, f'err={err:.3e}')

    A = random_spd(10, seed=7)
    Ainv = pm.inverse(A)
    product = pm.matmul(A, Ainv)
    err = max(abs(product[i][j] - (1.0 if i == j else 0.0))
              for i in range(10) for j in range(10))
    check('inverse 随机 SPD 10x10 乘积≈I', err < 1e-10, f'err={err:.3e}')

    expect_raises('inverse 非正定对称矩阵', ValueError, pm.inverse, [[1, 2], [2, 1]])
    expect_raises('inverse 奇异矩阵(非对称路径)', ValueError, pm.inverse, [[1, 2], [3, 6]])


# ---------------------------------------------------------------- 4. eigvalsh

def test_eigvalsh():
    check('eigvalsh [[2,1],[1,2]]',
          pm.eigvalsh([[2, 1], [1, 2]]) == [1.0, 3.0])
    eigs = pm.eigvalsh([[2, 0, 0], [0, 3, 1], [0, 1, 3]])
    check('eigvalsh 块对角 3x3',
          all(abs(a - b) < 1e-14 for a, b in zip(eigs, [2.0, 2.0, 4.0])), str(eigs))
    check('eigvalsh 零矩阵', pm.eigvalsh([[0, 0], [0, 0]]) == [0.0, 0.0])

    # 16x16 随机对称：谱不变量校验（无 numpy 也能验）
    A = random_symmetric(16, seed=42)
    eigs = pm.eigvalsh(A)
    check('eigvalsh 升序', all(eigs[i] <= eigs[i + 1] for i in range(15)))
    trace = math.fsum(A[i][i] for i in range(16))
    fro2 = math.fsum(v * v for row in A for v in row)
    check('eigvalsh 迹不变量', abs(math.fsum(eigs) - trace) < 1e-12 * max(1, abs(trace)))
    check('eigvalsh 谱能量不变量',
          abs(math.fsum(e * e for e in eigs) - fro2) < 1e-12 * fro2)

    expect_raises('eigvalsh 非对称', ValueError, pm.eigvalsh, [[1, 2], [0, 1]])


# ---------------------------------------------------------------- 5. singular_values / cond

def test_svd_cond():
    check('sv 对角阵', pm.singular_values([[3, 0, 0], [0, 1, 0], [0, 0, 4]]) == [4.0, 3.0, 1.0])
    sv = pm.singular_values([[3.0, 0.0, 0.0], [0.0, 0.0, 0.0]])  # 2x3 宽矩阵
    check('sv 宽矩阵含零', sv == [3.0, 0.0], str(sv))
    check('cond 对角阵', pm.cond([[1, 0], [0, 1e-8]]) == 1e8)
    check('cond 奇异=inf', pm.cond([[1, 2], [2, 4]]) == math.inf)

    # 10000x7 瘦长 Jacobian 病态情形：列尺度 10^0..10^6 → cond(A)~1e6
    rng = random.Random(123)
    m, n = 10000, 7
    J = [[rng.uniform(-1, 1) * (10.0 ** j) for j in range(n)] for _ in range(m)]
    sv = pm.singular_values(J)
    check('瘦长 Jacobian 奇异值数量', len(sv) == n)
    check('瘦长 Jacobian 奇异值降序且非负',
          all(sv[i] >= sv[i + 1] >= 0.0 for i in range(n - 1)))
    c = pm.cond(J)
    report('瘦长 Jacobian cond(A^T·A 路径)', f'cond={c:.6e}')
    check('瘦长 Jacobian cond 量级', 1e5 < c < 1e8, f'cond={c:.3e}')


# ---------------------------------------------------------------- 6. numpy 神谕对照

def test_oracle():
    if np is None:
        print('[SKIP] numpy 不可用，跳过神谕对照段')
        return

    # --- solve vs numpy.linalg.solve ---
    for n, seed in [(8, 1), (16, 2)]:
        A = random_symmetric(n, seed)
        for i in range(n):
            A[i][i] += n  # 保证良态
        b = [float(i) + 1.0 for i in range(n)]
        mine = pm.solve(A, b)
        oracle = np.linalg.solve(np.array(A), np.array(b))
        err = max_list_rel_diff(mine, oracle.tolist())
        check(f'oracle solve {n}x{n}', err < 1e-12, f'最大相对误差={err:.3e}')

    # Hilbert solve 对照（病态，仅报告）
    n = 8
    H = hilbert(n)
    b = [math.fsum(row) for row in H]
    mine = pm.solve(H, b)
    oracle = np.linalg.solve(np.array(H), np.array(b))
    report('oracle solve hilbert8', f'最大相对误差={max_list_rel_diff(mine, oracle.tolist()):.3e}')

    # --- inverse vs numpy.linalg.inv ---
    A = random_spd(12, seed=3)
    mine = pm.inverse(A)
    oracle = np.linalg.inv(np.array(A)).tolist()
    err = max(rel_diff(mine[i][j], oracle[i][j]) for i in range(12) for j in range(12))
    check('oracle inverse SPD 12x12', err < 1e-10, f'最大相对误差={err:.3e}')

    # --- eigvalsh vs numpy.linalg.eigvalsh ---
    # 良态随机对称：逐特征值严格相对误差 < 1e-12
    for n, seed in [(4, 10), (8, 11), (16, 12)]:
        A = random_symmetric(n, seed)
        mine = pm.eigvalsh(A)
        oracle = np.linalg.eigvalsh(np.array(A)).tolist()
        err = max_list_rel_diff(mine, oracle)
        check(f'oracle eigvalsh 随机对称 {n}x{n}', err < 1e-12, f'最大相对误差={err:.3e}')
    # Hilbert：最小特征值达 ~1e-18，以谱范数归一比较
    for n in (8, 12, 16):
        A = hilbert(n)
        mine = pm.eigvalsh(A)
        oracle = np.linalg.eigvalsh(np.array(A)).tolist()
        norm = max(abs(e) for e in oracle)
        err = max(abs(a - b) for a, b in zip(mine, oracle)) / norm
        check(f'oracle eigvalsh hilbert {n} (谱范数归一)', err < 1e-12, f'归一误差={err:.3e}')
        small_rel = rel_diff(mine[0], oracle[0])
        report(f'oracle eigvalsh hilbert{n} 最小特征值相对误差', f'{small_rel:.3e}')

    # 近奇异对称矩阵（相关矩阵边界：一个特征值贴 0）
    rng = np.random.RandomState(5)
    Q, _ = np.linalg.qr(rng.randn(8, 8))
    D = np.diag([1.0, 0.5, 0.1, 1e-2, 1e-4, 1e-6, 1e-8, 1e-11])
    M = Q @ D @ Q.T
    M = (M + M.T) / 2.0  # 消除浮点非对称尾巴，满足 eigvalsh 的严格对称输入约定
    A = M.tolist()
    mine = pm.eigvalsh(A)
    oracle = np.linalg.eigvalsh(np.array(A)).tolist()
    err = max(abs(a - b) for a, b in zip(mine, oracle)) / max(abs(e) for e in oracle)
    check('oracle eigvalsh 近奇异对称(谱范数归一)', err < 1e-12, f'归一误差={err:.3e}')

    # --- singular_values vs numpy.linalg.svd ---
    cases = [
        ('随机 20x6', random_matrix(20, 6, seed=21)),
        ('随机 6x20', random_matrix(6, 20, seed=22)),
        ('hilbert 8', hilbert(8)),
    ]
    for label, A in cases:
        mine = pm.singular_values(A)
        oracle = np.linalg.svd(np.array(A), compute_uv=False).tolist()
        scale = max(oracle)
        err = max(abs(a - b) for a, b in zip(mine, oracle)) / scale
        check(f'oracle svd {label} (谱范数归一)', err < 1e-12, f'归一误差={err:.3e}')

    # 近奇异矩阵：列近线性相关
    base = random_matrix(10, 4, seed=23)
    for row in base:
        row[3] = row[0] + 1e-9 * row[1]  # 第 4 列 ≈ 第 1 列
    mine = pm.singular_values(base)
    oracle = np.linalg.svd(np.array(base), compute_uv=False).tolist()
    scale = max(oracle)
    err = max(abs(a - b) for a, b in zip(mine, oracle)) / scale
    check('oracle svd 近奇异(谱范数归一)', err < 1e-12, f'归一误差={err:.3e}')
    report('oracle svd 近奇异 最小奇异值相对误差',
           f'{rel_diff(mine[-1], oracle[-1]):.3e}')

    # --- cond vs numpy.linalg.cond ---
    for label, A in [('随机 8x8', random_matrix(8, 8, seed=31)),
                     ('hilbert 6', hilbert(6))]:
        mine = pm.cond(A)
        oracle = float(np.linalg.cond(np.array(A)))
        err = rel_diff(mine, oracle)
        check(f'oracle cond {label}', err < 1e-9, f'相对误差={err:.3e}')

    # --- 10000x7 瘦长 Jacobian 病态情形 ---
    rng = random.Random(123)
    m, n = 10000, 7
    J = [[rng.uniform(-1, 1) * (10.0 ** j) for j in range(n)] for _ in range(m)]
    mine = pm.singular_values(J)
    oracle = np.linalg.svd(np.array(J), compute_uv=False).tolist()
    errs = [rel_diff(a, b) for a, b in zip(mine, oracle)]
    report('瘦长 Jacobian 奇异值相对误差(逐值)', ' '.join(f'{e:.2e}' for e in errs))
    # 单边 Jacobi 对病态矩阵仍保持高精度：全部奇异值相对误差 < 1e-10
    check('瘦长 Jacobian 全部奇异值对标', max(errs) < 1e-10,
          f'最大相对误差={max(errs):.3e}')
    cond_mine = pm.cond(J)
    cond_oracle = float(np.linalg.cond(np.array(J)))
    report('瘦长 Jacobian cond 对照',
           f'pymatrix={cond_mine:.6e} numpy={cond_oracle:.6e} '
           f'相对误差={rel_diff(cond_mine, cond_oracle):.3e}')


def main():
    print(f'解释器: {sys.executable}')
    print(f'numpy: {"可用 " + np.__version__ if np is not None else "不可用（纯标准库模式）"}')
    print('-' * 70)
    test_basics()
    test_solve()
    test_inverse()
    test_eigvalsh()
    test_svd_cond()
    test_oracle()
    print('-' * 70)
    if FAILURES:
        print(f'失败 {len(FAILURES)} 项: {FAILURES}')
        return 1
    print('全部通过。')
    return 0


if __name__ == '__main__':
    sys.exit(main())
