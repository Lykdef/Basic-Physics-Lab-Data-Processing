import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from desktop.backend import Api, Calculator


class Window:
    url='http://127.0.0.1:1234/local/index.html'
    result=None
    def get_current_url(self):return self.url
    def create_file_dialog(self,*args,**kwargs):return self.result


class BackendTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.api=Api(self.temp.name,Window.url)
        self.window=Window();self.api._window=self.window
    def tearDown(self):
        self.api._calculator.shutdown();self.temp.cleanup()
    def test_workspace_roundtrip_and_reject_invalid(self):
        self.assertIsNone(self.api.load_workspace())
        content='{"projects":[],"note":"中文"}'
        self.api.save_workspace(content);self.assertEqual(self.api.load_workspace(),content)
        with self.assertRaises(ValueError):self.api.save_workspace('{broken')
        self.assertEqual(self.api.load_workspace(),content)
        self.assertEqual(list(Path(self.temp.name).glob('*.tmp')),[])
    def test_external_page_rejected(self):
        self.window.url='https://example.org/'
        with self.assertRaises(PermissionError):self.api.load_workspace()
        with self.assertRaises(PermissionError):self.api.calculate({})
    def test_files_and_cancellation(self):
        self.assertFalse(self.api.save_project('test','{}'));self.assertIsNone(self.api.open_project())
        file=Path(self.temp.name)/'项目.json';self.window.result=(str(file),)
        self.api.save_project('test','{"中文":1}');self.assertEqual(self.api.open_project(),'{"中文":1}')
        self.api.save_project('test','{"中文":2}');self.assertEqual(self.api.open_project(),'{"中文":2}')
    def test_worker_recovers_from_formula_error(self):
        c=self.api._calculator
        request={'operation':'propagate','expression':'1/x','variables':[{'symbol':'x','value':0,'uncertainty':.1}]}
        with self.assertRaises(ValueError):c.calculate(request)
        request['expression']='x+1';self.assertEqual(c.calculate(request)['value'],1)
        c.shutdown()
        with self.assertRaises(RuntimeError):c.calculate(request)


if __name__=='__main__':unittest.main()
