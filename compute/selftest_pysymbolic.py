"""Standard-library symbolic regression against frozen independent reference results.
Run: python -S compute/selftest_pysymbolic.py
"""
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import pysymbolic as ps

SYMBOL_NAMES = ['x', 'y', 'z', 't', 'm', 'g', 'v', 'L', 'T', 'a', 'b', 'c',
                'u', 'w', 'alpha', 'v0']

# ---------------------------------------------------------------- corpus

CORPUS = [
    # atoms & numbers
    'x', '2', '0', '0.5', '0.1', '1e-5', '2.5e3', 'pi', 'e', '1.5', '100',
    '1e100', '0.000001', '3.14159', '-2.5', '0.0001', '123.456', '1e-7',
    # Add ordering
    'x+y', 'x+1', '1+x', '1-x', 'x-1', 'y-x', 'x-y', '-x', '-x-y', '-(x+y)',
    'x+2*y', '2.5-0.5*x', 'x+y+z', 'x+y+z+t', 'a+b+c', 'x+pi', 'pi-x',
    'e-x', 'x+e', '-(x-y)', '1-x-y', 'x-y+y', '(x-y)+(y-x)', 'x+x',
    '2*x+3*x', 'x+2*x', 'x*y+y*x', 'x+0', 'x-x',
    # Mul ordering & forms
    'x*y', 'y*x', '2*x*y', 'x*sin(y)', '2*sin(x)*cos(x)', 'pi*x', 'e*x',
    'x/y', 'x/(y*z)', 'x*y/z', '1/x', '1/sin(x)', 'sin(x)/x', '-x/y',
    'g*m', 'm*g', 'x*y*z*t', 'x*y/(z*t)', '1/(x*y)', 'x*(-1)', '-(x*y)',
    '-sin(x)', '-sqrt(x)', 'sin(x)*cos(x)*2', 'pi*pi', 'pi^2*pi',
    # Pow
    'x^2', 'x^0', 'x^1', 'x^(-2)', 'x^2.5', '(x+1)^2', '(x*y)^2', 'x^(2*y)',
    'sin(x)^2', 'sqrt(x)^2', '0^x', 'x^x', 'x*x', 'x*x*x', 'x^2.0*x',
    'x/x', 'x^2/x', 'x^2/x^3', 'x^2*x^3', '(x^2)^3', 'x^(2.0)*x^(3.0)',
    '0.5*x^2', 'x^-1', 'x^(-1.0)', '0.5^x', '2^x', 'x^y', 'x^12',
    '(x*y)^-1', '(x*y)^-2', 'x^-1*y^-1', '(x*y)^x', 'x^2*y^2',
    '(2*x)^2', '(2.0*x)^2', '(-x)^2', '(-x)^2.0', 'pi^2', 'e^2', '2^2',
    'sqrt(x)^3', 'sqrt(x)^2.0', '(sqrt(x))^4', 'sqrt(x*y)^2',
    '2^x*3^x', '2^x*2^x', '3^x*3^x', '2^x*2^y', '2^(2*x)*2^x', '4^x*2^x',
    '2^x*3^y', '2*2^x', 'pi^2*pi^3', 'x**2',
    # numeric folding & functions on constants
    'sin(0.5)', 'cos(0)', 'sqrt(4)', 'sqrt(4.0)', 'sqrt(2)', 'exp(0)',
    'log(e)', 'ln(2)', 'tan(0.25)', 'asin(0.5)', 'atan(1)', 'tan(0)',
    'log(1)', 'asin(1)', 'acos(0)', 'atan(0.5)', 'log(2)', 'sqrt(2)*sqrt(2)',
    'sin(-2.5)', 'cos(-0.5)', 'atan(-0.5)', 'acos(-1)', 'asin(-1)', 'exp(1)',
    'log(e^2)',
    # trig of pi multiples
    'sin(pi)', 'sin(pi/2)', 'sin(2*pi)', 'cos(pi)', 'tan(pi/4)',
    'sin(0.5*pi)', 'sin(1.5*pi)', 'sin(-pi)', 'cos(2*pi)', 'sin(3*pi)',
    'sin(pi/4)', 'cos(pi/4)', 'sin(0.25*pi)', 'cos(0.5*pi)', 'tan(0.25*pi)',
    'sin(pi/6)', 'sin(pi/3)', 'tan(pi/6)', 'sin(pi*x)',
    # function parity & inverses
    'sin(-x)', 'cos(-x)', 'tan(-x)', 'asin(-x)', 'acos(-x)', 'atan(-x)',
    'log(-x)', 'sqrt(-x)', 'sin(-x*y)', 'sin(x*y)', 'exp(-x)',
    'asin(sin(x))', 'sin(asin(x))', 'atan(tan(x))',
    'log(exp(x))', 'exp(log(x))', 'exp(x)^y',
    # products of sums / distribution
    '2*(x+1)', '2.0*(x+1.0)', '(x+y)*(x-y)', '(x+1)*(x-1)', 'x*(y+z)',
    '2.0*x*(y+z)', '(x+1)/2', 'x/2', '(x+y)/2', '3*(x+y)', '-1*(x+y)',
    '(x+y)*(x+y)', '(x+y)^2*(x+y)',
    # composite / physics formulas
    'sin(2*pi*x)', '2*pi*sqrt(L/g)', '0.5*m*v^2', '4*pi^2*L/T^2',
    'sqrt(x^2+y^2)', 'sqrt(1-x^2)', 'u*x^2+v*x+w', '(x+1)^3',
    'sqrt(x^2+y^2+z^2)', 'sqrt(8*x^2)', 'sqrt(x^2)', 'exp(x)^2',
    'sin(x)^2+cos(x)^2', 'log(x*y)', 'sqrt(x*y)', 'log(x^2)',
    'sin(x+y)', 'sin(sin(x))', 'sqrt(sqrt(x))', 'asin(x)+acos(y)',
    'e^(x^2)', 'x/(y+z)', '(x+y)/(x-y)', 'sin(x)*sin(x)', 'cos(x)*cos(x)',
    'sin(x)/cos(x)', 'log(x^2.0)^2', 'sin(x)^0', 'sin(x)^1',
    'atan(x)+atan(y)', 'log(x)+log(y)', 'exp(x)*exp(y)', 'exp(x)/exp(y)',
    'sqrt(x)/x', '1/sqrt(x)', 'log(1/x)', 'exp(x)*sin(y)', 'alpha*v0*t',
]

DIFFS = [
    ('sin(x)^2', 'x'), ('sin(x)^2.0', 'x'), ('(x+y)^3', 'x'),
    ('log(x^2.0)', 'x'), ('exp(x^2.0)', 'x'), ('1/x', 'x'),
    ('atan(x*y)', 'x'), ('asin(x)', 'x'), ('acos(x)', 'x'), ('tan(x)', 'x'),
    ('sqrt(x)', 'x'), ('x^0.5', 'x'), ('x*y*z', 'x'),
    ('sqrt(x^2+y^2)', 'x'), ('sqrt(x^2+y^2)', 'y'),
    ('x', 'x'), ('y', 'x'), ('x+y', 'x'), ('x*y', 'x'), ('sin(x)', 'x'),
    ('cos(x)', 'x'), ('exp(x)', 'x'), ('log(x)', 'x'), ('x^3', 'x'),
    ('x^y', 'x'), ('x^y', 'y'), ('2^x', 'x'), ('sin(x*y)', 'x'),
    ('sin(x)*cos(y)', 'x'), ('x*sin(x)', 'x'), ('x/x', 'x'),
    ('sqrt(x*y)', 'x'), ('atan(x/y)', 'x'), ('asin(x*y)', 'y'),
    ('acos(x^2)', 'x'), ('tan(x*y)', 'y'), ('log(x*y)', 'x'),
    ('exp(x)*sin(y)', 'x'), ('(x+1)^2.5', 'x'), ('sqrt(sqrt(x))', 'x'),
    ('log(sin(x))', 'x'), ('exp(log(x))', 'x'), ('x^2+y^2', 'x'),
    ('pi*x', 'x'), ('e^x', 'x'), ('0.5*m*v^2', 'm'), ('0.5*m*v^2', 'v'),
    ('4*pi^2*L/T^2', 'T'), ('sin(2*pi*x)', 'x'), ('x*y*z', 'y'),
    ('tan(x)', 'y'), ('sqrt(x)', 'y'), ('a*x^2+b*x+c', 'x'),
    ('x^3*y^2', 'x'), ('x^3*y^2', 'y'), ('log(x)/x', 'x'),
    ('sin(x)*cos(x)', 'x'), ('exp(x*y)', 'x'),
]

ERROR_CASES = [
    ('x^12.5', '常数指数的绝对值不得超过 12'),
    ('x^(-13)', '常数指数的绝对值不得超过 12'),
    ('foo', '未声明变量：foo'),
    ('x+bar', '未声明变量：bar'),
    ('sec(x)', '公式仅允许数字、变量、四则运算、乘方及白名单数学函数'),
    ('sin(x, y)', '公式仅允许数字、变量、四则运算、乘方及白名单数学函数'),
    ('x % 2', '公式仅允许数字、变量、四则运算、乘方及白名单数学函数'),
    ('x & y', '公式仅允许数字、变量、四则运算、乘方及白名单数学函数'),
    ('x if y else z', '公式仅允许数字、变量、四则运算、乘方及白名单数学函数'),
    ('1e101', '公式常数过大'),
    ('1e100*10', None),  # allowed at parse (evaluated to inf? see run)
    ('sin()', '公式仅允许数字、变量、四则运算、乘方及白名单数学函数'),
]

EVAL_CASES = [
    ('x^2+2*x+1', {'x': 3.0}),
    ('sin(x)+cos(y)', {'x': 0.7, 'y': -1.2}),
    ('sqrt(x^2+y^2)', {'x': 3.0, 'y': 4.0}),
    ('0.5*m*v^2', {'m': 2.5, 'v': -3.0}),
    ('4*pi^2*L/T^2', {'L': 1.0, 'T': 2.0}),
    ('2*pi*sqrt(L/g)', {'L': 0.5, 'g': 9.8}),
    ('exp(x*y)', {'x': 0.5, 'y': -2.0}),
    ('log(x*y)', {'x': 2.0, 'y': 3.5}),
    ('atan(x/y)', {'x': 1.0, 'y': 2.0}),
    ('asin(x)', {'x': 0.5}),
    ('acos(x)', {'x': -0.5}),
    ('tan(x)', {'x': 1.1}),
    ('x^y', {'x': 2.5, 'y': -1.5}),
    ('(-2)^2.0*x', {'x': 1.5}),
    ('e^x', {'x': 2.0}),
    ('pi*x', {'x': 2.0}),
    ('-x/y', {'x': 3.0, 'y': 7.0}),
    ('(x+y)/(x-y)', {'x': 5.0, 'y': 2.0}),
]

EVAL_ERROR_CASES = [
    ('log(x)', {'x': -1.0}),
    ('sqrt(x)', {'x': -4.0}),
    ('1/x', {'x': 0.0}),
    ('asin(x)', {'x': 2.0}),
    ('exp(x)', {'x': 1000.0}),
    ('(-2)^0.5*x', {'x': 1.0}),
    ('x/y', {'x': 1.0, 'y': 0.0}),
]

# Embedded expectations, frozen from the original sympy engine (see header).
EXPECTED = None  # replaced by the frozen JSON dict below
EXPECTED_EMBEDDED = {}

# 离线 golden：compute/selftest_pysymbolic_golden.json（由 venv 神谕固化，
# 纯标准库 python 的 standalone 模式据此比对；golden 模式仍在线对照原引擎）。
_GOLDEN_JSON = HERE / 'selftest_pysymbolic_golden.json'
if not EXPECTED_EMBEDDED and _GOLDEN_JSON.exists():
    with _GOLDEN_JSON.open(encoding='utf-8') as _f:
        _frozen = json.load(_f)
    EXPECTED_EMBEDDED = {tuple(k): v for k, v in _frozen['entries']}

# ------------------------------------------------------------- golden mode

def _load_original_engine():
    # Reference outputs are frozen; no legacy checkout is required.
    return None


def main():
    symbols = {n: ps.Symbol(n) for n in SYMBOL_NAMES}
    core = _load_original_engine()
    golden = core is not None
    if golden:
        import sympy as sp
        sp_syms = {n: sp.Symbol(n, real=True) for n in SYMBOL_NAMES}

    failures = []
    total = 0

    def check(tag, got, want):
        nonlocal total
        total += 1
        if got != want:
            failures.append((tag, got, want))

    # ---- expression printing corpus ----
    for text in CORPUS:
        try:
            got = ps.to_string(ps.parse(text, symbols))
        except Exception as exc:
            got = 'ERR:%s:%s' % (type(exc).__name__, exc)
        if golden:
            try:
                want = str(core.expression(text, sp_syms))
            except Exception as exc:
                want = 'ERR:%s:%s' % (type(exc).__name__, exc)
        else:
            want = EXPECTED_EMBEDDED.get(('expr', text), '<missing>')
        check('expr ' + text, got, want)

    # ---- diff corpus ----
    for text, var in DIFFS:
        try:
            got = ps.to_string(ps.parse(text, symbols).diff(ps.Symbol(var)))
        except Exception as exc:
            got = 'ERR:%s:%s' % (type(exc).__name__, exc)
        if golden:
            try:
                want = str(sp.diff(core.expression(text, sp_syms), sp_syms[var]))
            except Exception as exc:
                want = 'ERR:%s:%s' % (type(exc).__name__, exc)
        else:
            want = EXPECTED_EMBEDDED.get(('diff', text, var), '<missing>')
        check('diff %s wrt %s' % (text, var), got, want)

    # ---- error cases ----
    for text, msg in ERROR_CASES:
        try:
            ps.parse(text, symbols)
            got = 'NO-ERROR'
        except ValueError as exc:
            got = str(exc)
        except Exception as exc:
            got = 'ERR:%s:%s' % (type(exc).__name__, exc)
        if golden:
            try:
                core.expression(text, sp_syms)
                want = 'NO-ERROR'
            except Exception as exc:
                want = str(exc)
        else:
            want = EXPECTED_EMBEDDED.get(('error', text), '<missing>')
        check('error ' + text, got, want)

    # ---- numeric evaluation ----
    for text, subs in EVAL_CASES:
        try:
            got = ps.evaluate(ps.parse(text, symbols), subs)
        except Exception as exc:
            got = 'ERR:%s:%s' % (type(exc).__name__, exc)
        if golden:
            try:
                e = core.expression(text, sp_syms)
                r = e.evalf(subs={sp_syms[k]: v for k, v in subs.items()})
                want = float(r)
            except Exception as exc:
                want = 'ERR:%s:%s' % (type(exc).__name__, exc)
        else:
            want = EXPECTED_EMBEDDED.get(('eval', text, json.dumps(subs, sort_keys=True)),
                                         '<missing>')
        if isinstance(got, float) and isinstance(want, float):
            ok = math.isclose(got, want, rel_tol=1e-12, abs_tol=1e-300)
            total += 1
            if not ok:
                failures.append(('eval ' + text, got, want))
        else:
            check('eval ' + text, repr(got), repr(want))

    for text, subs in EVAL_ERROR_CASES:
        try:
            v = ps.evaluate(ps.parse(text, symbols), subs)
            got = 'NO-ERROR:%r' % v
        except ValueError:
            got = 'ValueError'
        except Exception as exc:
            got = 'ERR:%s' % type(exc).__name__
        check('evalerr ' + text, got, 'ValueError')

    # ---- report ----
    print('mode: %s' % ('golden (original sympy engine)' if golden
                        else 'standalone (embedded expectations)'))
    print('total checks: %d, failures: %d' % (total, len(failures)))
    for tag, got, want in failures:
        print('FAIL %s' % tag)
        print('  got : %r' % got)
        print('  want: %r' % want)
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
