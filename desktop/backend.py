import base64
import json
import multiprocessing as mp
import os
import re
import threading
import uuid
from pathlib import Path


def compute_worker(connection):
    from compute.core import calculate
    while True:
        try:
            payload = connection.recv()
        except EOFError:
            break
        try:
            result = calculate(payload)
            json.dumps(result, allow_nan=False)
            connection.send({'result': result})
        except Exception as error:
            connection.send({'error': str(error) or type(error).__name__})


class Calculator:
    def __init__(self):
        self._lock = threading.RLock()
        self._closed = False
        self._process = None
        self._connection = None

    def stop(self):
        with self._lock:
            self._stop()

    def shutdown(self):
        with self._lock:
            self._closed = True
            self._stop()

    def _stop(self):
        if self._process is not None:
            if self._process.is_alive():
                self._process.terminate()
            self._process.join(timeout=2)
            self._process.close()
            self._process = None
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    def calculate(self, payload):
        if not isinstance(payload, dict) or payload.get('operation') not in ('fit', 'propagate'):
            raise ValueError('未知计算类型')
        if len(json.dumps(payload, allow_nan=False)) > 1_800_000:
            raise ValueError('计算请求过大')
        with self._lock:
            if self._closed:
                raise RuntimeError('应用正在关闭')
            if self._process is None or not self._process.is_alive():
                self.stop()
                context = mp.get_context('spawn')
                self._connection, child = context.Pipe()
                self._process = context.Process(target=compute_worker, args=(child,), daemon=True)
                self._process.start()
                child.close()
            try:
                self._connection.send(payload)
                if not self._connection.poll(30):
                    self.stop()
                    raise TimeoutError('计算超时，请简化模型或调整初值')
                response = self._connection.recv()
            except (EOFError, BrokenPipeError, OSError):
                self.stop()
                raise RuntimeError('计算进程意外退出，请重试') from None
            if 'error' in response:
                raise ValueError(response['error'])
            return response['result']


def validated_json(content, limit):
    if not isinstance(content, str) or len(content.encode('utf-8')) > limit:
        raise ValueError('文件内容为空或超过大小限制')
    return json.loads(content, parse_constant=lambda _: (_ for _ in ()).throw(ValueError('非法数值')))


def atomic_write(path, content):
    path = Path(path)
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        options = {} if isinstance(content, bytes) else {'encoding': 'utf-8', 'newline': ''}
        with temporary.open('wb' if isinstance(content, bytes) else 'w', **options) as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


class Api:
    def __init__(self, data_dir, trusted_url):
        self._window = None
        self._url = trusted_url
        self._data_dir = Path(data_dir)
        self._calculator = Calculator()
        self._storage_lock = threading.Lock()

    def _check(self):
        if self._window is None or self._window.get_current_url().split('#')[0] != self._url:
            raise PermissionError('不允许外部页面访问桌面接口')

    def calculate(self, payload):
        self._check()
        return self._calculator.calculate(payload)

    def load_workspace(self):
        self._check()
        file = self._data_dir / 'workspace.json'
        with self._storage_lock:
            if not file.exists():
                return None
            if file.stat().st_size > 100_000_000:
                raise ValueError('本机工作区过大，请导入项目备份')
            content = file.read_text(encoding='utf-8')
            validated_json(content, 100_000_000)
            return content

    def save_workspace(self, content):
        self._check()
        state = validated_json(content, 100_000_000)
        if not isinstance(state, dict) or not isinstance(state.get('projects'), list):
            raise ValueError('工作区格式不正确')
        with self._storage_lock:
            atomic_write(self._data_dir / 'workspace.json', content)
        return True

    def open_project(self):
        import webview
        self._check()
        files = self._window.create_file_dialog(webview.FileDialog.OPEN, allow_multiple=False, file_types=('实验项目 (*.json)',))
        if not files:
            return None
        file = Path(files[0])
        if file.stat().st_size > 15_000_000:
            raise ValueError('文件超过 15 MB')
        content = file.read_text(encoding='utf-8-sig')
        validated_json(content, 15_000_000)
        return content

    def save_project(self, name, content):
        import webview
        self._check()
        validated_json(content, 15_000_000)
        filename = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', str(name))[:80].strip('. ') or '实验项目'
        files = self._window.create_file_dialog(webview.FileDialog.SAVE, save_filename=filename+'.json', file_types=('实验项目 (*.json)',))
        if not files:
            return False
        file = files if isinstance(files, str) else files[0]
        atomic_write(file, content)
        return True

    def save_image(self, name, content):
        import webview
        self._check()
        if not isinstance(content, str) or len(content) > 20_000_000:
            raise ValueError('图像超过大小限制')
        image = base64.b64decode(content, validate=True)
        if not image.startswith(b'\x89PNG\r\n\x1a\n'):
            raise ValueError('无效的 PNG 图像')
        filename = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', str(name))[:80].strip('. ') or '数据预览'
        files = self._window.create_file_dialog(webview.FileDialog.SAVE, save_filename=filename+'.png', file_types=('PNG 图像 (*.png)',))
        if not files:
            return False
        file = Path(files if isinstance(files, str) else files[0])
        atomic_write(file, image)
        return True
