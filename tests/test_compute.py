import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'compute'))
import core
import unittest
import math

def request(model='linear',values=(1,0),mode='auto',weighting='ordinary'):
    return dict(config=dict(model=model,mode=mode,weighting=weighting,parameters=[dict(value=v,min=None,max=None,fixed=False) for v in values]),points=[dict(id=str(i),x=x,y=y,sigma=.1+i*.02) for i,(x,y) in enumerate([(1,2.1),(2,4.2),(3,5.8),(4,8.1),(5,9.9)])])

class ComputeTests(unittest.TestCase):
    def assertClose(self, actual, expected, tolerance=1e-5):
        if isinstance(expected,(list,tuple)):
            self.assertEqual(len(actual),len(expected))
            for a,b in zip(actual,expected):self.assertClose(a,b,tolerance)
        else:self.assertTrue(math.isclose(actual,expected,rel_tol=tolerance,abs_tol=1e-9),(actual,expected))
    def analytic_line(self, req, weighted=False, relative=True):
        points=req['points'];w=[1/p['sigma']**2 if weighted else 1 for p in points]
        sw=sum(w);sx=sum(t*p['x'] for t,p in zip(w,points));sy=sum(t*p['y'] for t,p in zip(w,points))
        xx=sum(t*p['x']**2 for t,p in zip(w,points));xy=sum(t*p['x']*p['y'] for t,p in zip(w,points));det=sw*xx-sx*sx
        a=(sw*xy-sx*sy)/det;b=(xx*sy-sx*xy)/det
        scale=sum(t*(p['y']-a*p['x']-b)**2 for t,p in zip(w,points))/(len(points)-2) if relative else 1
        return [a,b],[[sw/det*scale,-sx/det*scale],[-sx/det*scale,xx/det*scale]]
    def test_ols_analytic_covariance(self):
        req=request();r=core.fit(req);expected,cov=self.analytic_line(req)
        self.assertClose(r['parameters'],expected);self.assertClose(r['covariance'],cov)
    def test_weighted_absolute_relative(self):
        for weighting in ['absolute','relative']:
            req=request(weighting=weighting);r=core.fit(req);expected,cov=self.analytic_line(req,True,weighting=='relative')
            self.assertClose(r['parameters'],expected);self.assertClose(r['covariance'],cov)
    def test_fixed_manual_exact(self):
        req=request();req['config']['parameters'][1]['fixed']=True;r=core.fit(req);self.assertEqual(r['parameters'][1],0);self.assertEqual(r['standard_errors'][1],0)
        req['config']['mode']='manual';r=core.fit(req);self.assertIsNone(r['covariance']);self.assertTrue(r['manual'])
        req=request(values=(2,0));req['points']=[dict(id=str(i),x=i,y=2*i) for i in range(5)];r=core.fit(req);self.assertIsNotNone(r['covariance'])
    def test_models(self):
        for model,values,fn in [('origin',[2],lambda x:2*x),('polynomial',[1,2,3],lambda x:1+2*x+3*x*x),('exponential',[4,-.3,1],lambda x:4*math.exp(-.3*x)+1),('power',[2,1.5],lambda x:2*x**1.5),('logarithmic',[3,2],lambda x:3*math.log(x)+2)]:
            with self.subTest(model=model):
                req=request(model,values);req['points']=[dict(id=str(i),x=float(x),y=float(fn(x))) for i,x in enumerate([1+i*4/19 for i in range(20)])];r=core.fit(req);self.assertClose(r['parameters'],values)
    def test_invalid_fit(self):
        req=request();req['config']['parameters'][0]['min']=2
        with self.assertRaises(ValueError):core.fit(req)
        req=request();req['points']=req['points'][:2]
        with self.assertRaises(ValueError):core.fit(req)
        req=request('power');req['points'][0]['x']=0
        with self.assertRaises(ValueError):core.fit(req)
    def test_correlated_propagation(self):
        req=dict(expression='U/I',variables=[dict(symbol='U',value=10,uncertainty=.2),dict(symbol='I',value=2,uncertainty=.1)],correlation=[[1,.5],[.5,1]],k=2)
        r=core.propagate(req);self.assertAlmostEqual(r['value'],5);self.assertAlmostEqual(r['uncertainty']**2,.01+.0625-.025);self.assertAlmostEqual(r['expanded'],2*r['uncertainty'])
        req['expression']='4*pi^2*U/I^2';r=core.propagate(req);self.assertAlmostEqual(r['budget'][0]['sensitivity'],math.pi**2);self.assertAlmostEqual(r['budget'][1]['sensitivity'],-10*math.pi**2)
    def test_invalid_formula_and_correlation(self):
        req=dict(expression='x',variables=[dict(symbol='x',value=0,uncertainty=.1)])
        for formula in ["__import__('os').system('echo bad')",'sqrt(x)','1/x','unknown+1']:
            with self.subTest(formula=formula):
                req['expression']=formula
                with self.assertRaises(Exception):core.propagate(req)
        req['expression']='x';r=core.propagate(req);self.assertIsNone(r['relative'])
        req['variables']=[dict(symbol=n,value=1,uncertainty=.1) for n in ['x','y','z']];req['correlation']=[[1,.9,.9],[.9,1,-.9],[.9,-.9,1]]
        with self.assertRaises(ValueError):core.propagate(req)

    def test_value_only_science_does_not_compute_derivatives(self):
        request=dict(operation='propagate',values_only=True,expression='1/b',variables=[dict(symbol='b',value=.1)])
        self.assertAlmostEqual(core.calculate(request)['value'],10)
        self.assertEqual(set(core.calculate(request)),{'value'})
        request['expression']='sqrt(b)';request['variables'][0]['value']=0
        self.assertEqual(core.calculate(request)['value'],0)
        request['expression']='1/b'
        with self.assertRaises(ValueError):core.calculate(request)

if __name__=='__main__':unittest.main()
