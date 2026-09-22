"""Generate the bundled two-sided Grubbs table; never run during app use."""
import sys,json
from pathlib import Path
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'.python-deps'))
import numpy as np
from scipy.stats import t
n=np.arange(3,10001)
table={}
for alpha in [.01,.05]:
    q=t.isf(alpha/(2*n),n-2)
    table[str(alpha)]=np.round((n-1)/np.sqrt(n)/np.sqrt(1+(n-2)/(q*q)),10).tolist()
(root/'src/grubbs-table.json').write_text(json.dumps(table,separators=(',',':')),encoding='utf-8')
