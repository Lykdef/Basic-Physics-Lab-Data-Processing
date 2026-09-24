import {test} from 'node:test';
import assert from 'node:assert/strict';
import {defaultFit,defaultPropagation} from '../src/advanced-model';
import {starterProject,serialize,parseProject} from '../src/model';
import {fitRequest} from '../src/calculation';
import {propagationRequest} from '../src/propagation';
test('计算设置持久化、旧范围不参与计算且排除保持配对',()=>{
 const p=starterProject(),d=p.datasets[1]!;d.fit=defaultFit();d.fit.enabled=true;d.fit.rangeMin=1;d.fit.rangeMax=2;d.rows[2]!.excluded=true;d.rows[2]!.reason='test';p.propagation=defaultPropagation();
 const copy=parseProject(serialize(p));assert.deepEqual(copy,p);assert.deepEqual(fitRequest(copy.datasets[1]!)!.points.map(p=>p.x),[.5,1,2,2.5,3,3.5,4,4.5,5]);
});
test('传播绑定完整均值不确定度，并拒绝缺失来源',()=>{
 const p=starterProject(),d=p.datasets[0]!,c=defaultPropagation();c.variables[0]!.source=`mean:${d.id}:${d.columns[0]!.id}`;
 assert.throws(()=>propagationRequest(c,p,{}),/B 类/);d.instrument.b_sources[d.columns[0]!.id]={delta:.02,distribution:'uniform'};
 assert.ok(propagationRequest(c,p,{}).variables[0]!.uncertainty>0);p.datasets.shift();assert.throws(()=>propagationRequest(c,p,{}),/已删除/);
});
test('拟合参数仅使用数值，不引入协方差',()=>{
 const p=starterProject(),d=p.datasets[1]!;d.fit=defaultFit();d.fit.enabled=true;const c=defaultPropagation();c.variables=[{id:'a',symbol:'a',source:`fit:${d.id}:0`,value:0,uncertainty:0},{id:'b',symbol:'b',source:`fit:${d.id}:1`,value:0,uncertainty:0}];
 const states:any={[d.id]:{pending:false,result:{parameters:[2,1],standard_errors:[.2,.1],covariance:[[.04,-.01],[-.01,.01]]}}};
 assert.equal(propagationRequest(c,p,states).correlation[0]![1],0);assert.equal(propagationRequest(c,p,states).variables[0]!.uncertainty,0);states[d.id].pending=true;assert.throws(()=>propagationRequest(c,p,states),/等待拟合/);
});
