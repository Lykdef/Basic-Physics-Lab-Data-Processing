"""Pure-Python symbolic engine replicating the sympy-based behaviour of
the original compute/core.py expression() parser, printer and diff.

Only Python standard library is used (ast, math, fractions).

Public API:
    Symbol(name)                     -> symbolic variable (real)
    parse(text, symbols_dict)        -> Expr   (verbatim port of core.py expression())
    expr.diff(sym)                   -> Expr   (symbolic derivative)
    evaluate(expr, subs_dict)        -> float  (numeric evaluation, math library)
    to_string(expr)                  -> str    (sympy StrPrinter replica)

Internal number model (mirrors sympy's Number hierarchy):
    int      -> Integer   (arises from exponent/term merging, e.g. x*x -> x**2)
    Fraction -> Rational  (arises from sqrt, e.g. x**(1/2))
    float    -> Float     (every literal from the parser, printed with 15 digits)
"""
import ast
import math
from fractions import Fraction

__all__ = ['Symbol', 'parse', 'evaluate', 'to_string', 'Expr',
           'Num', 'Sym', 'Const', 'Zoo', 'Add', 'Mul', 'Pow', 'Func',
           'EvalZeroDivision']


class EvalZeroDivision(ValueError, ArithmeticError):
    """0**负指数的求值错误：对外是 ValueError（evaluate 合约不变），
    同时携带 ArithmeticError 身份，供上层复刻 sympy evalf 在此情形下
    抛裸露 ZeroDivisionError 的可观察行为。"""

# ----------------------------------------------------------------------
# Expression nodes (raw, immutable, structural equality)
# ----------------------------------------------------------------------

class Expr:
    __slots__ = ()
    def diff(self, sym):
        return diff(self, sym if isinstance(sym, Sym) else Sym(sym))
    def __repr__(self):
        return to_string(self)

class Num(Expr):
    """Numeric atom. v is int (Integer), Fraction (Rational) or float (Float)."""
    __slots__ = ('v',)
    def __init__(self, v):
        if isinstance(v, Fraction) and v.denominator == 1:
            v = v.numerator
        self.v = v
    def __eq__(self, o):
        return isinstance(o, Num) and type(self.v) is type(o.v) and self.v == o.v
    def __hash__(self):
        return hash(('Num', type(self.v).__name__, self.v))

class Sym(Expr):
    __slots__ = ('name',)
    def __init__(self, name):
        self.name = name
    def __eq__(self, o):
        return isinstance(o, Sym) and self.name == o.name
    def __hash__(self):
        return hash(('Sym', self.name))

class Const(Expr):
    """NumberSymbol: pi or E."""
    __slots__ = ('name',)
    def __init__(self, name):
        self.name = name  # 'pi' or 'E'
    def __eq__(self, o):
        return isinstance(o, Const) and self.name == o.name
    def __hash__(self):
        return hash(('Const', self.name))

class Zoo(Expr):
    """ComplexInfinity (zoo)."""
    __slots__ = ()
    def __eq__(self, o):
        return isinstance(o, Zoo)
    def __hash__(self):
        return hash('Zoo')

ZOO = Zoo()

class Add(Expr):
    __slots__ = ('terms',)
    def __init__(self, terms):  # terms: tuple, canonically sorted
        self.terms = tuple(terms)
    def __eq__(self, o):
        return isinstance(o, Add) and self.terms == o.terms
    def __hash__(self):
        return hash(('Add', self.terms))

class Mul(Expr):
    __slots__ = ('factors',)
    def __init__(self, factors):  # factors: tuple, canonically sorted
        self.factors = tuple(factors)
    def __eq__(self, o):
        return isinstance(o, Mul) and self.factors == o.factors
    def __hash__(self):
        return hash(('Mul', self.factors))

class Pow(Expr):
    __slots__ = ('b', 'e')
    def __init__(self, b, e):
        self.b = b
        self.e = e
    def __eq__(self, o):
        return isinstance(o, Pow) and self.b == o.b and self.e == o.e
    def __hash__(self):
        return hash(('Pow', self.b, self.e))

class Func(Expr):
    __slots__ = ('name', 'arg')
    def __init__(self, name, arg):
        self.name = name  # sin cos tan asin acos atan log exp
        self.arg = arg
    def __eq__(self, o):
        return isinstance(o, Func) and self.name == o.name and self.arg == o.arg
    def __hash__(self):
        return hash(('Func', self.name, self.arg))

def Symbol(name):
    return Sym(name)

# ----------------------------------------------------------------------
# Numeric helpers (sympy type promotion: float wins, else Fraction, else int)
# ----------------------------------------------------------------------

def _is_float(v):
    return isinstance(v, float)

def nadd(a, b):
    if _is_float(a) or _is_float(b):
        return float(a) + float(b)
    return a + b  # int/Fraction exact

def nmul(a, b):
    if _is_float(a) or _is_float(b):
        return float(a) * float(b)
    return a * b

def nneg(a):
    return -a

def _iroot_extract(n, q):
    """Return (m, r) with n = r * m**q and r q-th-power-free (n>0, q>=2)."""
    m = 1
    r = n
    i = 2
    while i ** q <= r:
        while r % (i ** q) == 0:
            r //= i ** q
            m *= i
        i += 1
    return m, r

def _extract_int_pow(n, p, q):
    """Exact n**(p/q) for integer n>0. Returns (kind, ...) where kind is
    'num' (pure numeric value) or 'rem' (coeff, base_rem, exp_rem_Fraction)."""
    if n == 1:
        return ('num', 1)
    if q == 1:
        return ('num', Fraction(n) ** p if p < 0 else n ** p)
    m, r = _iroot_extract(n, q)
    if p < 0:
        a = -p
        k = -(-a // q)          # ceil(a/q)
        newp = k * q - a        # 1 <= newp <= q
        coeff = Fraction(m) ** p / (r ** k)   # m**p is Fraction (p<0)
        if newp % q == 0:
            return ('num', coeff * r ** (newp // q))
        return ('rem', coeff, r, Fraction(newp, q))
    # p > 0
    whole, pp = divmod(p, q)
    coeff = (m ** p) if m != 1 else 1
    if whole:
        coeff *= r ** whole
    if pp == 0:
        return ('num', coeff)
    return ('rem', coeff, r, Fraction(pp, q))

def npow(a, b):
    """Numeric exponentiation with sympy semantics.
    Returns ('num', value) | ('rem', coeff, base, exp) | ('zoo',) | ('sym',)."""
    if _is_float(a) or _is_float(b):
        fa, fb = float(a), float(b)
        try:
            r = fa ** fb
        except ZeroDivisionError:
            return ('zoo',)
        except (ValueError, OverflowError):
            return ('sym',)   # complex or out of float range: keep symbolic
        if isinstance(r, complex):
            return ('sym',)
        return ('num', r)
    # exact: int/Fraction mix
    if isinstance(b, int):
        if b >= 0:
            return ('num', a ** b)
        if a == 0:
            return ('zoo',)
        return ('num', Fraction(1, 1) / (a ** (-b)))
    # b is Fraction
    p, q = b.numerator, b.denominator
    if isinstance(a, int):
        if a == 0:
            return ('num', 0) if b > 0 else ('zoo',)
        if a < 0:
            return ('sym',)  # complex; deviation
        return _extract_int_pow(a, p, q)
    # a is Fraction: numerator/denominator separately
    rn = npow(a.numerator, b)
    rd = npow(a.denominator, Fraction(-p, q))
    if rn[0] == 'num' and rd[0] == 'num':
        return ('num', rn[1] * rd[1])
    # combine remainders
    coeff = 1
    rems = []
    for part in (rn, rd):
        if part[0] == 'num':
            coeff *= part[1]
        elif part[0] == 'rem':
            coeff *= part[1]
            rems.append((part[2], part[3]))
        else:
            return ('sym',)
    if not rems:
        return ('num', coeff)
    if len(rems) == 2 and rems[0][1] == rems[1][1]:
        rems = [(rems[0][0] * rems[1][0], rems[0][1])]
    if len(rems) == 1:
        return ('rem', coeff, rems[0][0], rems[0][1])
    return ('sym',)

# ----------------------------------------------------------------------
# as_coeff_Mul replica
# ----------------------------------------------------------------------

def as_coeff_mul(x):
    """Return (numeric_value, rest_expr or None)."""
    if isinstance(x, Num):
        return x.v, None
    if isinstance(x, Mul) and x.factors and isinstance(x.factors[0], Num):
        rest = x.factors[1:]
        if not rest:
            return x.factors[0].v, None
        if len(rest) == 1:
            return x.factors[0].v, rest[0]
        return x.factors[0].v, Mul(rest)
    return 1, x

def _is_negative(x):
    return as_coeff_mul(x)[0] < 0

def _is_positive_num(x):
    if isinstance(x, Num):
        return x.v > 0
    if isinstance(x, Const):
        return True
    return False

# ----------------------------------------------------------------------
# sort_key replica (sympy Expr.sort_key / Number.sort_key)
# ----------------------------------------------------------------------

_FUNC_KEY = {'exp': 10, 'log': 11, 'sin': 20, 'cos': 21, 'tan': 22}

def _class_key(x):
    if isinstance(x, Num):
        return (1, 0, 'Number')
    if isinstance(x, Sym):
        return (2, 0, 'Symbol')
    if isinstance(x, Const):
        return (2, 0, 'Pi' if x.name == 'pi' else 'Exp1')
    if isinstance(x, Mul):
        return (3, 0, 'Mul')
    if isinstance(x, Add):
        return (3, 1, 'Add')
    if isinstance(x, Pow):
        return (3, 2, 'Pow')
    if isinstance(x, Func):
        return (4, _FUNC_KEY.get(x.name, 10000), x.name)
    return (3, 9, 'Zoo')

def _mpf_key(v):
    """mpmath mpf 四元组（sympy Float._hashable_content）：(sign, man, exp, bc)，
    man 去除尾零（奇数化）。sympy Add/Mul args 排序用 Basic.compare，Float 按此
    元组比较——注意其语义：正数（sign=0）全部排在负数（sign=1）之前。"""
    if v == 0.0:
        return (0, 0, 0, 0)
    m, e = math.frexp(abs(v))
    man = int(m * (1 << 53))
    exp = e - 53
    while man & 1 == 0:
        man >>= 1
        exp += 1
    return (1 if v < 0 else 0, man, exp, man.bit_length())


def _num_order(v):
    """sympy Number._hashable_content 序：Integer -> (p, 1)，Rational -> (p, q)，
    Float -> mpf 四元组。"""
    if isinstance(v, float):
        return _mpf_key(v)
    if isinstance(v, Fraction):
        return (v.numerator, v.denominator)
    return (v, 1)


def _plain_num_order(v):
    """default_sort_key 的数值序：Python 原生比较（打印序用）。"""
    return v


def sort_key(x, num_order=_num_order):
    """sympy 排序键复刻。num_order=_num_order（默认）：Basic.compare 语义
    （args 存储序，Float 按 mpf 元组——正数在前负数在后）；
    num_order=_plain_num_order：default_sort_key 语义（as_ordered_factors
    打印序、as_terms 的 gens 排序，数值按 Python 原生序）。"""
    if isinstance(x, Num):
        return ((1, 0, 'Number'), (0, ()), (), num_order(x.v))
    coeff, rest = as_coeff_mul(x)
    if rest is None:
        rest = Num(coeff)
        coeff = 1
    if isinstance(rest, Pow):
        base, exp = rest.b, rest.e
        expr = base
    else:
        expr, exp = rest, Num(1)
    if isinstance(expr, Sym):
        args = (expr.name,)
    elif isinstance(expr, Const):
        args = ('pi' if expr.name == 'pi' else 'E',)
    elif isinstance(expr, Add):
        args = tuple(sort_key(t, num_order) for t in ordered_terms(expr))
    elif isinstance(expr, Mul):
        args = tuple(sort_key(f, num_order) for f in expr.factors)
    elif isinstance(expr, Func):
        args = (sort_key(expr.arg, num_order),)
    elif isinstance(expr, Pow):
        args = (sort_key(expr.b, num_order), sort_key(expr.e, num_order))
    else:
        args = ()
    return (_class_key(expr), (len(args), tuple(args)), sort_key(exp, num_order),
            num_order(coeff))


def default_sort_key(x):
    """sympy default_sort_key 复刻（数值用 Python 原生序）。"""
    return sort_key(x, _plain_num_order)

# ----------------------------------------------------------------------
# ordered_terms replica (Add printing/order: as_ordered_terms with 'lex')
# ----------------------------------------------------------------------

def _decompose_power(f):
    """exprtools.decompose_power replica -> (base, int_exp)."""
    if isinstance(f, Func) and f.name == 'exp':
        f = Pow(Const('E'), f.arg)
    if isinstance(f, Pow):
        b, e = f.b, f.e
        if isinstance(e, Num):
            if isinstance(e.v, Fraction):
                return pow_(b, Num(Fraction(1, e.v.denominator))), e.v.numerator
            if isinstance(e.v, int):
                return b, e.v
            return f, 1  # Float exponent
        c, r = as_coeff_mul(e)
        if isinstance(c, (int, Fraction)) and not isinstance(c, float) and r is not None:
            return pow_(b, r), int(c)
        return f, 1
    return f, 1

def _num_value(x):
    try:
        return _eval(x, {})
    except Exception:
        return float('nan')

def ordered_terms(expr):
    """as_ordered_terms(order=None) replica for an Add."""
    args = list(expr.terms)
    # special case: Add(Number(+), Mul(Number(-), expr)) -> number first
    numlike = lambda t: isinstance(t, (Num, Const))
    add_args = sorted(args, key=lambda t: 0 if numlike(t) else 1)
    if (len(add_args) == 2 and numlike(add_args[0])
            and isinstance(add_args[1], Mul)):
        mul_args = sorted(add_args[1].factors,
                          key=lambda t: 0 if isinstance(t, Num) else 1)
        if (len(mul_args) == 2 and isinstance(mul_args[0], Num)
                and _is_positive_num(add_args[0]) and mul_args[0].v < 0):
            return add_args
    # general path: as_terms + lex monomial ordering
    gens = []
    entries = []
    for t in args:
        c, rest = as_coeff_mul(t)
        cval = float(c)
        cpart = {}
        if rest is not None:
            fs = rest.factors if isinstance(rest, Mul) else [rest]
            for f in fs:
                if _is_number(f):  # Number/NumberSymbol/numeric-valued subtrees
                    cval *= _num_value(f)
                else:
                    base, ex = _decompose_power(f)
                    cpart[base] = ex
                    if base not in gens:
                        gens.append(base)
        entries.append((t, cval, cpart))
    gens.sort(key=default_sort_key)   # sympy as_terms: gens 用 default_sort_key
    idx = {g: i for i, g in enumerate(gens)}

    def key(entry):
        _, cval, cpart = entry
        monom = tuple(-(cpart.get(g, 0)) for g in gens)
        return (monom, ((False, 0.0), (cval, 0.0)))
    entries.sort(key=key)
    return [t for t, _, _ in entries]

# ----------------------------------------------------------------------
# Smart constructors with sympy-style automatic evaluation
# ----------------------------------------------------------------------

def add(*terms):
    flat = []
    for t in terms:
        if isinstance(t, Add):
            flat.extend(t.terms)
        else:
            flat.append(t)
    const = 0
    like = {}
    order = []
    for t in flat:
        c, r = as_coeff_mul(t)
        if r is None:
            const = nadd(const, c)
        else:
            if r not in like:
                like[r] = 0
                order.append(r)
            like[r] = nadd(like[r], c)
    out = []
    for r in order:
        c = like[r]
        if c == 0:
            continue
        if isinstance(c, int) and c == 1:
            out.append(r)
        else:
            out.append(mul(Num(c), r))
    if const != 0:
        out.append(Num(const))
    if not out:
        return Num(0)
    if len(out) == 1:
        return out[0]
    out.sort(key=sort_key)
    return Add(tuple(out))

def _gather_exps(pairs):
    """_gather replica: same base -> exponents grouped by as_coeff_Mul rest."""
    common = {}
    border = []
    for b, e in pairs:
        if b not in common:
            common[b] = {}
            border.append(b)
        c, r = as_coeff_mul(e)
        key = r if r is not None else Num(1)
        common[b].setdefault(key, []).append(c)
    merged = []
    for b in border:
        for r, cs in common[b].items():
            s = 0
            for c in cs:
                s = nadd(s, c)
            if s == 0:
                continue
            e = Num(s) if isinstance(r, Num) and r.v == 1 else mul(Num(s), r)
            merged.append((b, e))
    return merged

def _base_exp(f):
    """as_base_exp replica: exp(u) counts as E**u."""
    if isinstance(f, Pow):
        return f.b, f.e
    if isinstance(f, Func) and f.name == 'exp':
        return Const('E'), f.arg
    return f, Num(1)

def mul(*factors):
    flat = []
    for f in factors:
        if isinstance(f, Mul):
            flat.extend(f.factors)
        else:
            flat.append(f)
    coeff = 1
    rest = []
    for f in flat:
        if isinstance(f, Num):
            coeff = nmul(coeff, f.v)
        else:
            rest.append(f)
    if coeff == 0:
        return Num(0)
    # split into (base, exp) pairs; exp(u) participates as base E
    pnum = []      # (positive-int/Fraction base, positive Fraction exp)
    numexp = []    # (positive Num base, symbolic exp)
    general = []   # everything else
    for f in rest:
        b, e = _base_exp(f)
        if isinstance(b, Num) and isinstance(e, Num):
            # numeric powers are normally evaluated inside pow_; a leftover
            # symbolic one is e.g. 2**(1/3) (Rational exp, non-perfect base)
            if isinstance(e.v, Fraction) and b.v > 0:
                pnum.append((b.v, e.v))
                continue
            # Float base with Float exp should have been evaluated; keep general
        if isinstance(b, Num) and not isinstance(e, Num):
            if b.v > 0:
                numexp.append((b, e))
                continue
        general.append((b, e))
    # pnum: group by summed rational exponent, multiply bases (sqrt(2)*sqrt(3)->sqrt(6))
    pieces = []
    if pnum:
        by_exp = {}
        exp_order = []
        for bv, ev in pnum:
            if ev not in by_exp:
                by_exp[ev] = 1
                exp_order.append(ev)
            by_exp[ev] = by_exp[ev] * bv
        for ev in exp_order:
            # npow directly: bases are extraction results, avoid re-entry loops
            r = npow(by_exp[ev], ev)
            if r[0] == 'num':
                coeff = nmul(coeff, r[1])
            elif r[0] == 'rem':
                coeff = nmul(coeff, r[1])
                pieces.append(Pow(Num(r[2]), Num(r[3])))
            else:
                pieces.append(Pow(Num(by_exp[ev]), Num(ev)))
    # numexp: gather same base, then multiply bases sharing equal exponent (2^x*3^x -> 6^x)
    if numexp:
        merged = _gather_exps(numexp)
        by_exp = {}
        exp_order = []
        for b, e in merged:
            if e not in by_exp:
                by_exp[e] = []
                exp_order.append(e)
            by_exp[e].append(b)
        for e in exp_order:
            bs = by_exp[e]
            if len(bs) == 1:
                pieces.append(pow_(bs[0], e))
            else:
                prod = bs[0].v
                for b in bs[1:]:
                    prod = nmul(prod, b.v)
                pieces.append(pow_(Num(prod), e))
    # general: gather same base with summed exponents
    if general:
        merged = _gather_exps(general)
        pieces.extend(pow_(b, e) for b, e in merged)
    # fold numeric pieces into coeff, flatten produced Muls
    factors = []
    for p in pieces:
        if isinstance(p, Num):
            coeff = nmul(coeff, p.v)
        elif isinstance(p, Mul):
            for f in p.factors:
                if isinstance(f, Num):
                    coeff = nmul(coeff, f.v)
                else:
                    factors.append(f)
        else:
            factors.append(p)
    if coeff == 0:
        return Num(0)
    if not factors:
        return Num(coeff)
    # distribution: Number * Add (exactly two parts); Float 1.0 also distributes
    if len(factors) == 1 and isinstance(factors[0], Add) and \
            (coeff != 1 or isinstance(coeff, float)):
        return add(*(mul(Num(coeff), t) for t in factors[0].terms))
    if coeff != 1 or isinstance(coeff, float):
        head = [Num(coeff)]
    else:
        head = []
    allf = head + factors
    if len(allf) == 1:
        return allf[0]
    allf_sorted = sorted(allf, key=sort_key)
    return Mul(tuple(allf_sorted))

def pow_(b, e):
    # Integer exponent folds
    if isinstance(e, Num) and isinstance(e.v, int):
        if e.v == 0:
            return Num(1)
        if e.v == 1:
            return b
    # numeric base
    if isinstance(b, Num):
        if b.v == 1 and isinstance(b.v, int):
            return Num(1)  # only Integer 1 folds; Float 1.0**x stays symbolic
        if isinstance(e, Num):
            r = npow(b.v, e.v)
            if r[0] == 'num':
                return Num(r[1])
            if r[0] == 'zoo':
                return ZOO
            if r[0] == 'rem':
                return mul(Num(r[1]), Pow(Num(r[2]), Num(r[3])))
            return Pow(b, e)  # symbolic deviation (complex etc.)
        return Pow(b, e)
    # E base -> exp function
    if isinstance(b, Const) and b.name == 'E':
        return func('exp', e)
    # exp function base: exp(u)**e -> exp(e*u) (E is positive, always combines)
    if isinstance(b, Func) and b.name == 'exp':
        return func('exp', mul(e, b.arg))
    # Pow base: combine exponents in the safe cases sympy does
    if isinstance(b, Pow):
        e1 = b.e
        combine = False
        if isinstance(e, Num) and isinstance(e.v, int):
            combine = True
        elif isinstance(e1, Num) and isinstance(e1.v, Fraction):
            combine = True
        elif isinstance(b.b, Num) and b.b.v > 0:
            combine = True  # positive numeric base always combines
        if combine:
            if isinstance(e1, Num) and isinstance(e, Num):
                return pow_(b.b, Num(nmul(e1.v, e.v)))
            return pow_(b.b, mul(e1, e))
        return Pow(b, e)
    # Mul base with numeric exponent: extract positive coefficient / distribute Integer
    if isinstance(b, Mul) and isinstance(e, Num):
        if isinstance(e.v, int):
            return mul(*(pow_(f, e) for f in b.factors))
        fs = b.factors
        if fs and isinstance(fs[0], Num) and fs[0].v > 0:
            c = pow_(fs[0], e)
            if len(fs) == 2:
                return mul(c, pow_(fs[1], e))
            return mul(c, Pow(Mul(fs[1:]), e))
        return Pow(b, e)
    return Pow(b, e)

def neg(x):
    return mul(Num(-1), x)

# ----------------------------------------------------------------------
# Function constructor with automatic evaluation
# ----------------------------------------------------------------------

def _pi_coeff(arg):
    """Return numeric c if arg is c*pi (pure number multiple), else None."""
    if isinstance(arg, Const) and arg.name == 'pi':
        return 1
    if isinstance(arg, Mul):
        others = [f for f in arg.factors
                  if not (isinstance(f, Const) and f.name == 'pi')]
        if len(others) == len(arg.factors):
            return None  # no pi factor
        if len(others) == 0:
            return 1
        if len(others) == 1 and isinstance(others[0], Num):
            return others[0].v
    return None

def _equal_valued(i, cm):
    return abs(i - cm) <= 1e-9 * max(1.0, abs(cm))

def _recast_pi_arg(arg):
    """trigonometric._pi_coeff replica for symbolic Mul args containing pi:
    sin/cos/tan(c*pi*rest) with Float c recastable to an exact binary
    Rational/Integer gets its argument recast (sin(2.0*pi*x) -> sin(2*pi*x)).
    Returns the new argument, arg unchanged, or None (no pi / pure number)."""
    if not isinstance(arg, Mul):
        return None
    others = [f for f in arg.factors
              if not (isinstance(f, Const) and f.name == 'pi')]
    if len(others) == len(arg.factors) or not others:
        return None
    cx = mul(*others) if len(others) > 1 else others[0]
    c, x = as_coeff_mul(cx)
    if x is None:
        return None  # pure number times pi: handled by the value table
    if not isinstance(c, float):
        return arg
    f = abs(c) % 1
    if f == 0:
        nc = int(c)
    else:
        p = -int(round(math.log2(f)))
        m = 2 ** p
        cm = c * m
        i = int(cm)
        if not _equal_valued(i, cm):
            return arg
        nc = Fraction(i, m)
    return mul(Num(nc), x, Const('pi'))

_SQRT2_2 = None

def _sqrt2_over_2():
    return mul(Num(Fraction(1, 2)), pow_(Num(2), Num(Fraction(1, 2))))

def _trig_pi_value(name, c):
    """Exact values for sin/cos/tan of c*pi with c hitting the quarter table."""
    cf = c if isinstance(c, (int, Fraction)) else Fraction(c)
    if name in ('sin', 'cos'):
        m = cf % 2
        table = {
            ('sin', 0): Num(0), ('sin', Fraction(1, 4)): _sqrt2_over_2(),
            ('sin', Fraction(1, 2)): Num(1), ('sin', Fraction(3, 4)): _sqrt2_over_2(),
            ('sin', 1): Num(0), ('sin', Fraction(5, 4)): neg(_sqrt2_over_2()),
            ('sin', Fraction(3, 2)): Num(-1), ('sin', Fraction(7, 4)): neg(_sqrt2_over_2()),
            ('cos', 0): Num(1), ('cos', Fraction(1, 4)): _sqrt2_over_2(),
            ('cos', Fraction(1, 2)): Num(0), ('cos', Fraction(3, 4)): neg(_sqrt2_over_2()),
            ('cos', 1): Num(-1), ('cos', Fraction(5, 4)): neg(_sqrt2_over_2()),
            ('cos', Fraction(3, 2)): Num(0), ('cos', Fraction(7, 4)): _sqrt2_over_2(),
        }
        return table.get((name, m))
    m = cf % 1
    table = {0: Num(0), Fraction(1, 4): Num(1), Fraction(1, 2): ZOO,
             Fraction(3, 4): Num(-1)}
    return table.get(m)

def func(name, arg):
    if isinstance(arg, Zoo):
        return ZOO if name == 'log' else Func(name, arg)  # nan chains: deviation
    if name == 'exp':
        if isinstance(arg, Num):
            if arg.v == 0:
                return Num(1)
            if arg.v == 1 and isinstance(arg.v, int):
                return Const('E')  # exp(1) -> E
            if isinstance(arg.v, float):
                try:
                    return Num(math.exp(arg.v))
                except OverflowError:
                    pass  # keep symbolic (out of float range; deviation)
        if isinstance(arg, Func) and arg.name == 'log':
            return arg.arg  # exp(log(x)) -> x
        if isinstance(arg, Add):
            # exp(a + b) -> exp(a)*exp(b) for the numeric (Float/Integer) part
            num_terms = [t for t in arg.terms if isinstance(t, Num)]
            other = [t for t in arg.terms if not isinstance(t, Num)]
            if num_terms and other:
                cv = 0
                for t in num_terms:
                    cv = nadd(cv, t.v)
                if cv != 0:
                    return mul(func('exp', Num(cv)),
                               func('exp', add(*other)))
        return Func('exp', arg)
    if name == 'log':
        if isinstance(arg, Num):
            if arg.v == 1:
                return Num(0)
            if arg.v == 0:
                return ZOO
            if isinstance(arg.v, float):
                if arg.v < 0:
                    return Func('log', arg)  # complex; deviation
                return Num(math.log(arg.v))
            return Func('log', arg)
        if isinstance(arg, Const) and arg.name == 'E':
            return Num(1)
        if isinstance(arg, Func) and arg.name == 'exp':
            return arg.arg  # log(exp(x)) -> x
        return Func('log', arg)
    # trig / inverse trig
    if isinstance(arg, Num):
        v = arg.v
        if v == 0:
            if name in ('sin', 'tan', 'asin', 'atan'):
                return Num(0)
            if name == 'cos':
                return Num(1)
            return mul(Num(Fraction(1, 2)), Const('pi'))  # acos(0) -> pi/2
        if name == 'acos' and v == 1:
            return Num(0)
        if name == 'acos' and v == -1 and not isinstance(v, float):
            return Const('pi')  # acos(-1) -> pi (exact args only)
        if name == 'asin' and v == 1 and not isinstance(v, float):
            return mul(Num(Fraction(1, 2)), Const('pi'))
        if name == 'asin' and v == -1 and not isinstance(v, float):
            return neg(mul(Num(Fraction(1, 2)), Const('pi')))
        if isinstance(v, float):
            if name in ('asin', 'acos') and abs(v) > 1:
                return Func(name, arg)  # complex; deviation
            return Num(getattr(math, name)(v))
        return Func(name, arg)  # exact nonzero Integer/Rational stays symbolic
    if name in ('sin', 'cos', 'tan'):
        c = _pi_coeff(arg)
        if c is not None:
            # recast exact binary Float coefficients to Rational/Integer
            if isinstance(c, float):
                f = abs(c) % 1
                if f == 0:
                    c = int(c)
                else:
                    p = -int(round(math.log2(f)))
                    i = int(c * 2 ** p)
                    if _equal_valued(i, c * 2 ** p):
                        c = Fraction(i, 2 ** p)
            if not isinstance(c, float):
                r = _trig_pi_value(name, c)
                if r is not None:
                    return r
        else:
            new_arg = _recast_pi_arg(arg)
            if new_arg is not None and new_arg != arg:
                return Func(name, new_arg)
    # parity: sin/tan/asin/atan odd, cos even (acos untouched)
    c, rest = as_coeff_mul(arg)
    if rest is not None and c < 0:
        pos = mul(Num(-c), rest)
        if name in ('sin', 'tan', 'asin', 'atan'):
            return neg(func(name, pos))
        if name == 'cos':
            return func(name, pos)
    # inverse compositions (sympy trig eval table)
    if isinstance(arg, Func):
        u = arg.arg
        one_minus_u2 = lambda: pow_(add(Num(1), neg(pow_(u, Num(2)))),
                                    Num(Fraction(1, 2)))
        one_plus_u2 = lambda: pow_(add(Num(1), pow_(u, Num(2))),
                                   Num(Fraction(1, 2)))
        comp = None
        if (name, arg.name) in (('sin', 'asin'), ('cos', 'acos'), ('tan', 'atan')):
            comp = u
        elif (name, arg.name) == ('sin', 'acos'):
            comp = one_minus_u2()
        elif (name, arg.name) == ('cos', 'asin'):
            comp = one_minus_u2()
        elif (name, arg.name) == ('sin', 'atan'):
            comp = mul(u, pow_(add(Num(1), pow_(u, Num(2))), Num(Fraction(-1, 2))))
        elif (name, arg.name) == ('cos', 'atan'):
            comp = pow_(add(Num(1), pow_(u, Num(2))), Num(Fraction(-1, 2)))
        elif (name, arg.name) == ('tan', 'asin'):
            comp = mul(u, pow_(add(Num(1), neg(pow_(u, Num(2)))), Num(Fraction(-1, 2))))
        elif (name, arg.name) == ('tan', 'acos'):
            comp = mul(one_minus_u2(), pow_(u, Num(-1)))
        if comp is not None:
            return comp
    return Func(name, arg)

# ----------------------------------------------------------------------
# Precedence (sympy printing/precedence.py subset)
# ----------------------------------------------------------------------

PREC_ADD = 40
PREC_MUL = 50
PREC_POW = 60
PREC_FUNC = 70
PREC_ATOM = 1000

def precedence(x):
    if isinstance(x, Num):
        if x.v < 0:
            return PREC_ADD
        if isinstance(x.v, Fraction):
            return PREC_MUL
        return PREC_ATOM
    if isinstance(x, Add):
        return PREC_ADD
    if isinstance(x, Mul):
        return PREC_ADD if _is_negative(x) else PREC_MUL
    if isinstance(x, Pow):
        return PREC_POW
    if isinstance(x, Func):
        return PREC_FUNC
    return PREC_ATOM

# ----------------------------------------------------------------------
# Float formatting: mpmath to_str(mpf, 15, strip_zeros=strip) replica
# ----------------------------------------------------------------------

def _fmt_float(v, strip):
    if v == 0:
        return '0.0'
    sign = '-' if v < 0 else ''
    mant, exp = ('%.14e' % abs(v)).split('e')
    e = int(exp)
    digits = mant.replace('.', '')  # 15 significant digits
    if -4 <= e <= 14:
        if e >= 14:
            s = digits + '.'
            if strip:
                s = digits + '.0'
        elif e >= 0:
            ip = digits[:e + 1]
            fp = digits[e + 1:]
            if strip:
                fp = fp.rstrip('0') or '0'
            s = ip + '.' + fp
        else:
            fp = '0' * (-e - 1) + digits
            if strip:
                fp = fp.rstrip('0') or '0'
            s = '0.' + fp
        return sign + s
    # scientific
    m = digits[0] + '.' + digits[1:]
    if strip:
        m = m.rstrip('0')
        if m.endswith('.'):
            m += '0'
    return '%s%se%+d' % (sign, m, e)

# ----------------------------------------------------------------------
# StrPrinter replica
# ----------------------------------------------------------------------

def to_string(expr):
    return _p(expr, 1)

def _paren(s, item, level, print_level, strict=False):
    if precedence(item) < level or (not strict and precedence(item) <= level):
        return '(%s)' % s
    return s

def _p(x, pl):
    if isinstance(x, Num):
        v = x.v
        if isinstance(v, int):
            return str(v)
        if isinstance(v, Fraction):
            return '%s/%s' % (v.numerator, v.denominator)
        return _fmt_float(v, pl > 1)
    if isinstance(x, Sym):
        return x.name
    if isinstance(x, Const):
        return 'pi' if x.name == 'pi' else 'E'
    if isinstance(x, Zoo):
        return 'zoo'
    if isinstance(x, Add):
        return _p_add(x, pl)
    if isinstance(x, Mul):
        return _p_mul(x, pl)
    if isinstance(x, Pow):
        return _p_pow(x, pl)
    if isinstance(x, Func):
        return '%s(%s)' % (x.name, _p(x.arg, pl + 1))
    raise TypeError('unknown node %r' % (x,))

def _p_add(x, pl):
    terms = ordered_terms(x)
    prec = PREC_ADD
    parts = []
    for term in terms:
        t = _p(term, pl + 1)
        if t.startswith('-') and not isinstance(term, Add):
            sign = '-'
            t = t[1:]
        else:
            sign = '+'
        if precedence(term) < prec or isinstance(term, Add):
            parts.extend([sign, '(%s)' % t])
        else:
            parts.extend([sign, t])
    sign = parts.pop(0)
    if sign == '+':
        sign = ''
    return sign + ' '.join(parts)

def _p_mul(x, pl):
    prec = PREC_MUL
    # sympy _print_Mul 正常分支用 as_ordered_factors（default_sort_key，
    # 数值 Python 原生序）；存储序（Basic.compare）仅用于规范化
    factors = sorted(x.factors, key=default_sort_key)
    sign = ''
    if factors and isinstance(factors[0], Num) and factors[0].v < 0:
        sign = '-'
        factors[0] = Num(-factors[0].v)
    # _keep_coeff: Integer 1 coefficient is not printed (Float 1.0 is kept)
    if factors and isinstance(factors[0], Num) and isinstance(factors[0].v, int) \
            and factors[0].v == 1 and len(factors) > 1:
        factors.pop(0)
    a = []  # numerator
    b = []  # denominator
    pow_paren = []
    for item in factors:
        if isinstance(item, Pow) and as_coeff_mul(item.e)[0] < 0:
            exp = item.e
            if isinstance(exp, Num) and isinstance(exp.v, int) and exp.v == -1:
                base = item.b
                b.append(base)
                if isinstance(base, (Mul, Pow)):
                    n = len(base.factors) if isinstance(base, Mul) else 2
                    if n != 1:
                        pow_paren.append(base)
            else:
                # apow: negate the exponent
                if isinstance(exp, Num):
                    ne = Num(-exp.v)
                else:
                    c, r = as_coeff_mul(exp)
                    ne = mul(Num(-c), r) if r is not None else Num(-c)
                b.append(Pow(item.b, ne))
        elif isinstance(item, Num) and isinstance(item.v, Fraction):
            if item.v.numerator != 1:
                a.append(Num(item.v.numerator))
            if item.v.denominator != 1:
                b.append(Num(item.v.denominator))
        else:
            a.append(item)
    if not a:
        a = [Num(1)]
    a_str = [_paren(_p(t, pl + 1), t, prec, pl + 1) for t in a]
    b_str = [_paren(_p(t, pl + 1), t, prec, pl + 1) for t in b]
    for item in pow_paren:
        if item in b:
            i = b.index(item)
            b_str[i] = '(%s)' % b_str[i]
    if not b:
        return sign + '*'.join(a_str)
    if len(b) == 1:
        return sign + '*'.join(a_str) + '/' + b_str[0]
    return sign + '*'.join(a_str) + '/(%s)' % '*'.join(b_str)

def _p_pow(x, pl):
    PREC = PREC_POW
    b, e = x.b, x.e
    if isinstance(e, Num) and isinstance(e.v, Fraction):
        if e.v == Fraction(1, 2):
            return 'sqrt(%s)' % _p(b, pl + 1)
        if e.v == Fraction(-1, 2):
            return '1/sqrt(%s)' % _p(b, pl + 1)
    if isinstance(e, Num) and isinstance(e.v, int) and e.v == -1:
        return '1/%s' % _paren(_p(b, pl + 1), b, PREC, pl + 1)
    es = _paren(_p(e, pl + 1), e, PREC, pl + 1)
    return '%s**%s' % (_paren(_p(b, pl + 1), b, PREC, pl + 1), es)

# ----------------------------------------------------------------------
# diff
# ----------------------------------------------------------------------

def diff(x, s):
    if isinstance(x, (Num, Const, Zoo)):
        return Num(0)
    if isinstance(x, Sym):
        return Num(1) if x.name == s.name else Num(0)
    if isinstance(x, Add):
        return add(*(diff(t, s) for t in x.terms))
    if isinstance(x, Mul):
        fs = list(x.factors)
        terms = []
        for i, f in enumerate(fs):
            d = diff(f, s)
            if isinstance(d, Num) and d.v == 0:
                continue
            terms.append(mul(*(fs[:i] + [d] + fs[i + 1:])))
        return add(*terms) if terms else Num(0)
    if isinstance(x, Pow):
        # sympy Pow._eval_derivative: b**e * (de*log(b) + db*e/b)  -- always
        # 构造顺序对齐 Python 左结合：db*e/b = (db*e)/b；其中 mul(db, e) 是
        # 二元 Number×Add 情形，sympy 会把数值系数分配进 Add（影响打印形式）。
        b, e = x.b, x.e
        db = diff(b, s)
        de = diff(e, s)
        return mul(pow_(b, e),
                   add(mul(de, func('log', b)),
                       mul(mul(db, e), pow_(b, Num(-1)))))
    if isinstance(x, Func):
        u, du = x.arg, diff(x.arg, s)
        n = x.name
        if n == 'sin':
            return mul(func('cos', u), du)
        if n == 'cos':
            return mul(Num(-1), func('sin', u), du)
        if n == 'tan':
            return mul(add(pow_(func('tan', u), Num(2)), Num(1)), du)
        if n == 'exp':
            return mul(func('exp', u), du)
        if n == 'log':
            return mul(du, pow_(u, Num(-1)))
        if n == 'asin':
            return mul(du, pow_(add(Num(1), neg(pow_(u, Num(2)))), Num(Fraction(-1, 2))))
        if n == 'acos':
            return mul(Num(-1), du,
                       pow_(add(Num(1), neg(pow_(u, Num(2)))), Num(Fraction(-1, 2))))
        if n == 'atan':
            return mul(du, pow_(add(Num(1), pow_(u, Num(2))), Num(-1)))
    raise TypeError('cannot diff %r' % (x,))

# ----------------------------------------------------------------------
# evaluate
# ----------------------------------------------------------------------

_MATH_FUNC = {
    'sin': math.sin, 'cos': math.cos, 'tan': math.tan, 'exp': math.exp,
    'log': math.log, 'asin': math.asin, 'acos': math.acos, 'atan': math.atan,
}

def evaluate(expr, subs):
    """Numeric evaluation with the math library. Domain/overflow errors
    and non-finite results raise ValueError('公式在当前输入处无定义')."""
    v = _eval(expr, subs)
    if not math.isfinite(v):
        raise ValueError('公式在当前输入处无定义')
    return v

def _eval(x, subs):
    if isinstance(x, Num):
        return float(x.v)
    if isinstance(x, Sym):
        return float(subs[x.name])
    if isinstance(x, Const):
        return math.pi if x.name == 'pi' else math.e
    if isinstance(x, Zoo):
        raise ValueError('公式在当前输入处无定义')
    if isinstance(x, Add):
        return sum(_eval(t, subs) for t in x.terms)
    if isinstance(x, Mul):
        r = 1.0
        for f in x.factors:
            r *= _eval(f, subs)
        return r
    if isinstance(x, Pow):
        a = _eval(x.b, subs)
        b = _eval(x.e, subs)
        try:
            r = a ** b
        except ZeroDivisionError:
            # 0**负指数：sympy evalf（mpmath）此时抛裸露 ZeroDivisionError；
            # 用双重身份的标记异常携带该语义（仍是 ValueError，不破坏 evaluate 合约）
            raise EvalZeroDivision('公式在当前输入处无定义') from None
        except (ValueError, OverflowError):
            raise ValueError('公式在当前输入处无定义') from None
        if isinstance(r, complex):
            raise ValueError('公式在当前输入处无定义')
        return r
    if isinstance(x, Func):
        a = _eval(x.arg, subs)
        try:
            return _MATH_FUNC[x.name](a)
        except (ValueError, OverflowError):
            raise ValueError('公式在当前输入处无定义') from None
    raise TypeError('cannot evaluate %r' % (x,))

# ----------------------------------------------------------------------
# parse: verbatim port of core.py expression()
# ----------------------------------------------------------------------

def _finite(value, name='数值'):
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
        raise ValueError(f'{name}必须为有限数值')
    return float(value)

def _is_number(x):
    if isinstance(x, (Num, Const)):
        return True
    if isinstance(x, Zoo):
        return False
    if isinstance(x, Sym):
        return False
    if isinstance(x, Add):
        return all(_is_number(t) for t in x.terms)
    if isinstance(x, Mul):
        return all(_is_number(f) for f in x.factors)
    if isinstance(x, Pow):
        return _is_number(x.b) and _is_number(x.e)
    if isinstance(x, Func):
        return _is_number(x.arg)
    return False

def _to_float(x):
    """float(b) replica for the exponent check; raises on non-real."""
    return _eval(x, {})

_FUNCTIONS = ('sin', 'cos', 'tan', 'exp', 'log', 'ln', 'sqrt', 'asin', 'acos', 'atan')

def parse(text, symbols):
    """Verbatim port of compute/core.py expression(). symbols: dict name -> Sym."""
    if not isinstance(text, str) or len(text) > 400:
        raise ValueError('公式不得超过 400 个字符')
    tree = ast.parse(text.replace('^', '**'), mode='eval')
    if len(list(ast.walk(tree))) > 120:
        raise ValueError('公式过于复杂')

    def build(node, depth=0):
        if depth > 16:
            raise ValueError('公式嵌套过深')
        if isinstance(node, ast.Constant):
            n = _finite(node.value, '公式常数')
            if abs(n) > 1e100:
                raise ValueError('公式常数过大')
            return Num(n)
        if isinstance(node, ast.Name):
            if node.id in symbols:
                return symbols[node.id]
            if node.id == 'pi':
                return Const('pi')
            if node.id == 'e':
                return Const('E')
            raise ValueError(f'未声明变量：{node.id}')
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            v = build(node.operand, depth + 1)
            return neg(v) if isinstance(node.op, ast.USub) else v
        if isinstance(node, ast.BinOp) and isinstance(node.op,
                (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow)):
            a, b = build(node.left, depth + 1), build(node.right, depth + 1)
            if isinstance(node.op, ast.Add):
                return add(a, b)
            if isinstance(node.op, ast.Sub):
                return add(a, neg(b))
            if isinstance(node.op, ast.Mult):
                return mul(a, b)
            if isinstance(node.op, ast.Div):
                return mul(a, pow_(b, Num(-1)))
            if _is_number(b):
                try:
                    bv = _to_float(b)
                    real = True
                except (ValueError, OverflowError):
                    real = False
                    bv = 0.0
                if not real or abs(bv) > 12:
                    raise ValueError('常数指数的绝对值不得超过 12')
            return pow_(a, b)
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id in _FUNCTIONS and len(node.args) == 1
                and not node.keywords):
            arg = build(node.args[0], depth + 1)
            fname = node.func.id
            if fname == 'sqrt':
                return pow_(arg, Num(Fraction(1, 2)))
            if fname == 'ln':
                fname = 'log'
            return func(fname, arg)
        raise ValueError('公式仅允许数字、变量、四则运算、乘方及白名单数学函数')

    return build(tree.body)
