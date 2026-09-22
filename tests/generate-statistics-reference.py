"""Generate independent SciPy oracle values. Run with PYTHONPATH=.verification."""
import json
from pathlib import Path
import numpy as np
import scipy
from scipy.stats import t

criticals=[]
for n in [3,4,5,10,30,100,1000,10000]:
    for alpha in [0.000001,0.01,0.05,0.2]:
        quantile=t.isf(alpha/(2*n),n-2)
        critical=(n-1)/np.sqrt(n)/np.sqrt(1+(n-2)/(quantile*quantile))
        criticals.append(dict(n=n,alpha=alpha,critical=float(critical)))
samples=[]
for values in [[12.52,12.54,12.50,12.56,12.52,12.54,12.50,12.52,12.54,12.52], [20.02,20.04,20.,20.03,20.01,20.02,20.35,20.03,20.01,20.02], [1,2,3], [1000000000000.1,1000000000000.2,1000000000000.3]]:
    x=np.array(values); mean=np.mean(x);s=np.std(x,ddof=1)
    samples.append(dict(values=values,mean=float(mean),s=float(s),uA=float(s/np.sqrt(len(x))),g=float(max(abs(x-mean))/s)))
Path('tests/statistics-reference.json').write_text(json.dumps(dict(scipy=scipy.__version__,criticals=criticals,samples=samples),indent=2),encoding='utf-8')
