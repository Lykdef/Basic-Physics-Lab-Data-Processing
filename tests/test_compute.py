import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'compute'))
import core
import unittest
import numpy as np

def request(model='linear',values=(1,0),mode='auto',weighting='ordinary'):
    return dict(config=dict(model=model,mode=mode,weighting=weighting,parameters=[dict(value=v,min=None,max=None,fixed=False) for v in values]),points=[dict(id=str(i),x=x,y=y,sigma=.1+i*.02) for i,(x,y) in enumerate([(1,2.1),(2,4.2),(3,5.8),(4,8.1),(5,9.9)])])

class ComputeTests(unittest.TestCase):
    def test_ols_analytic_covariance(self):
        req=request();r=core.fit(req);x=np.array([p['x'] for p in req['points']]);y=np.array([p['y'] for p in req['points']]);design=np.column_stack([x,np.ones(5)])
        expected=np.linalg.solve(design.T@design,design.T@y);res=y-design@expected;cov=np.linalg.inv(design.T@design)*(res@res)/3
        np.testing.assert_allclose(r['parameters'],expected,rtol=1e-6);np.testing.assert_allclose(r['covariance'],cov,rtol=1e-5)
    def test_weighted_absolute_relative(self):
        req=request(weighting='absolute');r=core.fit(req);x=np.array([p['x'] for p in req['points']]);y=np.array([p['y'] for p in req['points']]);sigma=np.array([p['sigma'] for p in req['points']]);design=np.column_stack([x,np.ones(5)])/sigma[:,None]
        cov=np.linalg.inv(design.T@design);expected=cov@design.T@(y/sigma)
        np.testing.assert_allclose(r['parameters'],expected,rtol=1e-5);np.testing.assert_allclose(r['covariance'],cov,rtol=1e-5)
        req['config']['weighting']='relative';r=core.fit(req);res=y/sigma-design@expected;np.testing.assert_allclose(r['covariance'],cov*(res@res)/3,rtol=1e-5)
    def test_fixed_manual_exact(self):
        req=request();req['config']['parameters'][1]['fixed']=True;r=core.fit(req);self.assertEqual(r['parameters'][1],0);self.assertEqual(r['standard_errors'][1],0)
        req['config']['mode']='manual';r=core.fit(req);self.assertIsNone(r['covariance']);self.assertTrue(r['manual'])
        req=request(values=(2,0));req['points']=[dict(id=str(i),x=i,y=2*i) for i in range(5)];r=core.fit(req);self.assertIsNotNone(r['covariance'])
    def test_models(self):
        for model,values,fn in [('origin',[2],lambda x:2*x),('polynomial',[1,2,3],lambda x:1+2*x+3*x*x),('exponential',[4,-.3,1],lambda x:4*np.exp(-.3*x)+1),('power',[2,1.5],lambda x:2*x**1.5),('logarithmic',[3,2],lambda x:3*np.log(x)+2)]:
            with self.subTest(model=model):
                req=request(model,values);req['points']=[dict(id=str(i),x=float(x),y=float(fn(x))) for i,x in enumerate(np.linspace(1,5,20))];r=core.fit(req);np.testing.assert_allclose(r['parameters'],values,atol=1e-5)
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
        req['expression']='4*pi^2*U/I^2';r=core.propagate(req);self.assertAlmostEqual(r['budget'][0]['sensitivity'],np.pi**2);self.assertAlmostEqual(r['budget'][1]['sensitivity'],-10*np.pi**2)
    def test_invalid_formula_and_correlation(self):
        req=dict(expression='x',variables=[dict(symbol='x',value=0,uncertainty=.1)])
        for formula in ["__import__('os').system('echo bad')",'sqrt(x)','1/x','unknown+1']:
            with self.subTest(formula=formula):
                req['expression']=formula
                with self.assertRaises(Exception):core.propagate(req)
        req['expression']='x';r=core.propagate(req);self.assertIsNone(r['relative'])
        req['variables']=[dict(symbol=n,value=1,uncertainty=.1) for n in ['x','y','z']];req['correlation']=[[1,.9,.9],[.9,1,-.9],[.9,-.9,1]]
        with self.assertRaises(ValueError):core.propagate(req)

if __name__=='__main__':unittest.main()
