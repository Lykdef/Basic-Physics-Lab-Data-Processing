import hashlib
import json
import os
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parents[1]
version = json.loads((root/'package.json').read_text(encoding='utf-8'))['version']
folder = f'PhysicalLab-WebView-{version}-win-x64'
archive = root/'release'/f'{folder}.zip'
with archive.open('rb') as stream:
    digest = hashlib.file_digest(stream,'sha256').hexdigest()
url = f'https://github.com/Lykdef/Basic-Physics-Lab-Data-Processing/releases/download/v{version}/{archive.name}'
config = root/'.webview-build/BuildConfig.cs'
config.parent.mkdir(exist_ok=True)
config.write_text('static class BuildConfig {\n'+''.join(f'public const string {key} = {json.dumps(value)};\n' for key,value in dict(Version=version,Folder=folder,Url=url,Hash=digest).items())+'}\n',encoding='utf-8')
compiler = Path(os.environ['SystemRoot'])/'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
output = root/'release'/f'PhysicalLab-Setup-{version}-win-x64.exe'
subprocess.run([str(compiler),'/nologo','/target:winexe','/platform:x64','/optimize+',f'/out:{output}',
               '/r:System.Windows.Forms.dll','/r:System.Drawing.dll','/r:System.IO.Compression.dll','/r:System.IO.Compression.FileSystem.dll','/r:Microsoft.CSharp.dll',str(root/'desktop/Installer.cs'),str(config)],check=True)
with output.open('rb') as stream:
    checksum = hashlib.file_digest(stream,'sha256').hexdigest()
Path(str(output)+'.sha256').write_text(f'{checksum}  {output.name}\n',encoding='ascii')
print(f'Installer: {output} ({output.stat().st_size} bytes)')
