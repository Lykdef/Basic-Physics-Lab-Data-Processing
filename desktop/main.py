import argparse
import functools
import http.server
import json
import multiprocessing as mp
import os
import secrets
import sys
import threading
from pathlib import Path

ROOT = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(ROOT))
from desktop.backend import Api


class StaticFiles(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def list_directory(self, _):
        self.send_error(403)

    def do_GET(self):
        prefix = '/' + self.server.token + '/'
        if not self.path.startswith(prefix):
            self.send_error(404)
            return
        self.path = '/' + self.path[len(prefix):]
        super().do_GET()


def main():
    import webview
    parser = argparse.ArgumentParser()
    parser.add_argument('--data-dir', type=Path)
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--verify-recovery', action='store_true')
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    data_dir = args.data_dir or Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'PhysicalLab'
    data_dir.mkdir(parents=True, exist_ok=True)
    if not (ROOT/'dist/index.html').exists():
        raise RuntimeError('缺少前端构建，请先运行 npm run build')
    handler = functools.partial(StaticFiles, directory=str(ROOT/'dist'))
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), handler)
    server.token = secrets.token_urlsafe(24)
    url = f'http://127.0.0.1:{server.server_port}/{server.token}/index.html?desktop=pywebview'
    threading.Thread(target=server.serve_forever, daemon=True).start()
    api = Api(data_dir, url)
    window = webview.create_window('物理实验室 · Physical Lab', url, js_api=api, width=1500, height=980, min_size=(1050,720), hidden=args.self_test)
    api._window = window
    if args.self_test:
        from desktop.selftest import install
        install(window, api, args)
    try:
        webview.start(gui='edgechromium', private_mode=False, storage_path=str(data_dir/'webview'), debug=False)
    finally:
        api._calculator.shutdown()
        server.shutdown()
        server.server_close()


if __name__ == '__main__':
    mp.freeze_support()
    try:
        main()
    except Exception:
        import traceback
        log = Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'PhysicalLab'
        log.mkdir(parents=True, exist_ok=True)
        (log/'startup-error.log').write_text(traceback.format_exc(), encoding='utf-8')
        if sys.stderr is not None:
            traceback.print_exc()
        if getattr(sys, 'frozen', False):
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, f'启动失败，请确认已安装 Microsoft Edge WebView2 Runtime。\n错误详情：{log / "startup-error.log"}', '物理实验室', 16)
        sys.exit(1)
