import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
os.chdir(root)
folder = root/'.webview-test'
folder.mkdir(exist_ok=True)
data = Path(tempfile.mkdtemp(prefix='integration-', dir=folder))
command = [sys.argv[1]] if len(sys.argv)>1 else [sys.executable, str(root/'desktop/main.py')]
for recovery in [False, True]:
    report = data/('recovery.json' if recovery else 'first.json')
    env = dict(os.environ, PYTHONIOENCODING='utf-8')
    if len(sys.argv)>1:
        env['PATH'] = os.environ['SystemRoot']+'\\System32'
        env.pop('PYTHONHOME', None)
        env.pop('PYTHONPATH', None)
    args = command+['--self-test','--data-dir',str(data),'--report',str(report)]
    if recovery:
        args+=['--verify-recovery']
    result = subprocess.run(args, env=env, timeout=100, capture_output=True, text=True, encoding='utf-8', errors='replace')
    if result.returncode or not report.exists():
        raise RuntimeError(f'Native app failed ({result.returncode}): {result.stderr[-4000:]}')
    status = json.loads(report.read_text(encoding='utf-8'))
    if not status.get('ok'):
        raise AssertionError(status)
    print(json.dumps(status, ensure_ascii=False))
print('PASS: pywebview native bridge, fitting, propagation, save/open and restart recovery.')
