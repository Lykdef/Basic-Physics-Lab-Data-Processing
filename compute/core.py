"""Offline numerical engine. JSON-lines on stdin/stdout; no expression eval."""
import sys
from pathlib import Path
import importlib.util
if importlib.util.find_spec('numpy') is None:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / '.python-deps'))
import ast
import json
import math
import re
import warnings
import numpy as np
from scipy.optimize import curve_fit, OptimizeWarning
import sympy as sp

def finite(value, name='数值'):
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
        raise ValueError(f'{name}必须为有限数值')
    return float(value)

def fit(request):
    points=request.get('points', [])
    if not 1 <= len(points) <= 10000: raise ValueError('需要 1–10000 个有效配对点')
    x=np.array([finite(p['x']) for p in points]); y=np.array([finite(p['y']) for p in points])
    config=request['config']; model=config['model']; degree=int(config.get('degree',2))
    if model=='linear': names=['a','b']; fn=lambda x,a,b:a*x+b
    elif model=='origin': names=['a']; fn=lambda x,a:a*x
    elif model=='polynomial':
        if not 1<=degree<=6: raise ValueError('多项式次数须为 1–6')
        names=[f'a{i}' for i in range(degree+1)];fn=lambda x,*p:np.polynomial.polynomial.polyval(x,p)
    elif model=='exponential': names=['a','b','c'];fn=lambda x,a,b,c:a*np.exp(b*x)+c
    elif model=='power': names=['a','b'];fn=lambda x,a,b:a*np.power(x,b)
    elif model=='logarithmic': names=['a','b'];fn=lambda x,a,b:a*np.log(x)+b
    else: raise ValueError('不支持的拟合模型')
    if model in ('power','logarithmic') and np.any(x<=0): raise ValueError('幂函数和对数模型要求横坐标 > 0')
    if np.ptp(x)==0: raise ValueError('横坐标无变化，无法拟合关系')
    settings=config['parameters']
    if len(settings)!=len(names): raise ValueError('参数数量与模型不一致')
    params=np.array([finite(p['value'],'参数') for p in settings]);free=[i for i,p in enumerate(settings) if not p.get('fixed',False)]
    lower=[-np.inf if p.get('min') is None else finite(p['min'],'下界') for p in settings]
    upper=[np.inf if p.get('max') is None else finite(p['max'],'上界') for p in settings]
    for i in range(len(params)):
        if lower[i]>=upper[i]:raise ValueError(f'{names[i]} 的下界必须小于上界')
        if not lower[i]<=params[i]<=upper[i]:raise ValueError(f'{names[i]} 的初值超出边界')
    mode=config.get('weighting','ordinary');sigma=None
    if mode!='ordinary':
        if mode not in ('absolute','relative'):raise ValueError('未知加权方式')
        sigma=np.array([finite(p.get('sigma'),'纵坐标标准不确定度') for p in points])
        if np.any(sigma<=0):raise ValueError('加权拟合要求每个有效点的纵坐标标准不确定度 > 0')
    covariance=None;errors=None;warning=None
    manual=config.get('mode')=='manual'
    if not manual:
        if len(x)<=len(free):raise ValueError('有效点数必须大于待拟合参数个数')
        if not free:raise ValueError('自动拟合至少需要一个未固定参数')
        def wrapped(xs,*v):
            p=params.copy();p[free]=v
            with np.errstate(over='raise',invalid='raise',divide='raise'):return fn(xs,*p)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always',OptimizeWarning)
            fitted,cov=curve_fit(wrapped,x,y,p0=params[free],sigma=sigma,absolute_sigma=mode=='absolute',
                                bounds=([lower[i] for i in free],[upper[i] for i in free]),method='trf',max_nfev=3000,x_scale='jac')
        params[free]=fitted
        # Check identifiability separately: an exact fit may have zero covariance.
        columns=[]
        for i in free:
            step=1e-6*max(1,abs(params[i]));plus=params.copy();minus=params.copy()
            plus[i]+=step;minus[i]-=step
            column=(fn(x,*plus)-fn(x,*minus))/(2*step)
            if sigma is not None:column=column/sigma
            columns.append(column)
        jac=np.column_stack(columns);norm=np.linalg.norm(jac,axis=0)
        identifiable=bool(np.all(norm>0)) and np.linalg.cond(jac/np.maximum(norm,1e-300))<1e7
        if np.all(np.isfinite(cov)) and identifiable and not caught:
            covariance=np.zeros((len(params),len(params)));covariance[np.ix_(free,free)]=cov
            errors=np.sqrt(np.maximum(np.diag(covariance),0)).tolist()
        else: warning='参数协方差不可可靠估计，请检查模型、范围与参数相关性'
        if any(abs(params[i]-lower[i])<1e-7*max(1,abs(params[i])) or abs(params[i]-upper[i])<1e-7*max(1,abs(params[i])) for i in free):
            warning='部分参数位于边界，协方差仅为局部近似'
    with np.errstate(over='raise',invalid='raise',divide='raise'):
        predicted=fn(x,*params); cx=np.linspace(float(min(x)),float(max(x)),241);cy=fn(cx,*params)
    if not np.all(np.isfinite(predicted)) or not np.all(np.isfinite(cy)):raise ValueError('模型结果超出数值范围，请调整参数')
    residual=y-predicted;sse=float(np.dot(residual,residual));sst=float(np.dot(y-y.mean(),y-y.mean()))
    return dict(names=names,parameters=params.tolist(),standard_errors=errors,covariance=None if covariance is None else covariance.tolist(),
                curve=np.column_stack([cx,cy]).tolist(),residuals=[dict(id=p['id'],x=float(x[i]),residual=float(residual[i])) for i,p in enumerate(points)],
                rmse=float(np.sqrt(sse/len(x))),r2=None if sst<=1e-28 else 1-sse/sst,n=len(x),manual=manual,warning=warning)

FUNCTIONS={'sin':sp.sin,'cos':sp.cos,'tan':sp.tan,'exp':sp.exp,'log':sp.log,'ln':sp.log,'sqrt':sp.sqrt,'asin':sp.asin,'acos':sp.acos,'atan':sp.atan}
def expression(text, symbols):
    if not isinstance(text,str) or len(text)>400:raise ValueError('公式不得超过 400 个字符')
    tree=ast.parse(text.replace('^','**'),mode='eval')
    if len(list(ast.walk(tree)))>120:raise ValueError('公式过于复杂')
    def build(node,depth=0):
        if depth>16:raise ValueError('公式嵌套过深')
        if isinstance(node,ast.Constant):
            n=finite(node.value,'公式常数')
            if abs(n)>1e100:raise ValueError('公式常数过大')
            return sp.Float(n)
        if isinstance(node,ast.Name):
            if node.id in symbols:return symbols[node.id]
            if node.id=='pi':return sp.pi
            if node.id=='e':return sp.E
            raise ValueError(f'未声明变量：{node.id}')
        if isinstance(node,ast.UnaryOp) and isinstance(node.op,(ast.UAdd,ast.USub)):
            v=build(node.operand,depth+1);return -v if isinstance(node.op,ast.USub) else v
        if isinstance(node,ast.BinOp) and isinstance(node.op,(ast.Add,ast.Sub,ast.Mult,ast.Div,ast.Pow)):
            a,b=build(node.left,depth+1),build(node.right,depth+1)
            if isinstance(node.op,ast.Add):return a+b
            if isinstance(node.op,ast.Sub):return a-b
            if isinstance(node.op,ast.Mult):return a*b
            if isinstance(node.op,ast.Div):return a/b
            if b.is_number and (not b.is_real or abs(float(b))>12):raise ValueError('常数指数的绝对值不得超过 12')
            return a**b
        if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id in FUNCTIONS and len(node.args)==1 and not node.keywords:
            return FUNCTIONS[node.func.id](build(node.args[0],depth+1))
        raise ValueError('公式仅允许数字、变量、四则运算、乘方及白名单数学函数')
    return build(tree.body)

def propagate(request):
    variables=request['variables']
    if not 1<=len(variables)<=16:raise ValueError('模型需要 1–16 个输入变量')
    names=[v['symbol'] for v in variables]
    if len(set(names))!=len(names) or any(not re.fullmatch('[A-Za-z][A-Za-z0-9_]{0,30}',n) or n in FUNCTIONS or n in ('pi','e') for n in names):raise ValueError('变量名重复、不合法或与数学函数冲突')
    symbols={n:sp.Symbol(n,real=True) for n in names}
    expr=expression(request['expression'],symbols)
    vals=[finite(v['value'],n) for v,n in zip(variables,names)]
    u=np.array([finite(v['uncertainty'],f'u({n})') for v,n in zip(variables,names)])
    if np.any(u<0):raise ValueError('标准不确定度不得为负')
    corr=np.array(request.get('correlation',np.eye(len(names))),dtype=float)
    if corr.shape!=(len(names),len(names)) or not np.all(np.isfinite(corr)):raise ValueError('相关矩阵维数错误或含非法数值')
    if not np.allclose(corr,corr.T,atol=1e-12,rtol=0) or not np.allclose(np.diag(corr),1,atol=1e-12,rtol=0) or np.any(np.abs(corr)>1):raise ValueError('相关矩阵须对称、对角线为 1，且系数在 [-1,1]')
    if np.linalg.eigvalsh(corr).min() < -1e-10:raise ValueError('相关矩阵不是半正定矩阵')
    substitutions={symbols[n]:v for n,v in zip(names,vals)}
    def number(e):
        v=e.evalf(subs=substitutions)
        if v.is_real is not True or v.is_finite is not True:raise ValueError('公式或偏导数在当前输入处无定义')
        return finite(float(v),'公式结果')
    y=number(expr);derivatives=[sp.diff(expr,symbols[n]) for n in names];c=np.array([number(d) for d in derivatives])
    scaled=c*u;variance=float(scaled@corr@scaled)
    if not math.isfinite(variance):raise ValueError('传播计算超出数值范围')
    variance=max(variance,0);uc=math.sqrt(variance)
    k=finite(request.get('k',2),'包含因子')
    if k<=0:raise ValueError('包含因子须 > 0')
    budget=[dict(symbol=n,derivative=str(d),sensitivity=float(c[i]),uncertainty=float(u[i]),contribution=float(scaled[i]**2)) for i,(n,d) in enumerate(zip(names,derivatives))]
    cross=[dict(left=names[i],right=names[j],correlation=float(corr[i,j]),contribution=float(2*scaled[i]*scaled[j]*corr[i,j])) for i in range(len(names)) for j in range(i+1,len(names)) if corr[i,j]!=0]
    near_zero=abs(y)<=1e-12*max(1,sum(abs(c[i]*vals[i]) for i in range(len(names))))
    return dict(value=y,uncertainty=uc,relative=None if near_zero else uc/abs(y),expanded=k*uc,budget=budget,cross=cross,expression=str(expr))

def calculate(request):
    if request.get('operation')=='fit':return fit(request)
    if request.get('operation')=='propagate':return propagate(request)
    raise ValueError('未知计算请求')

if __name__=='__main__':
    for line in sys.stdin:
        request={}
        try:
            if len(line)>2_000_000:raise ValueError('请求过大')
            request=json.loads(line);result=calculate(request['payload']);response=dict(id=request['id'],result=result)
            print(json.dumps(response,ensure_ascii=False,allow_nan=False),flush=True)
        except Exception as error:
            print(json.dumps(dict(id=request.get('id'),error=str(error) or type(error).__name__),ensure_ascii=False),flush=True)
