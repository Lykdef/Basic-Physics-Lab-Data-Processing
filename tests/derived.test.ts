import {test} from 'node:test';
import assert from 'node:assert/strict';
import {compileDerived,derivedDataset} from '../src/derived';
import {starterProject,serialize,parseProject} from '../src/model';
import {defaultFit} from '../src/advanced-model';
import {fitRequest} from '../src/calculation';
test('导出量安全计算、优先级、缺失值与定义域',()=>{
  assert.equal(compileDerived('-u^2 + 2^-2',['u'])({u:2}),-3.75);
  assert.equal(compileDerived('1/u',['u'])({u:null}),null);
  assert.throws(()=>compileDerived('1/u',['u'])({u:0}),/除零/);
  assert.throws(()=>compileDerived('sqrt(u)',['u'])({u:-1}),/定义域/);
  assert.throws(()=>compileDerived('window.alert(1)',['u']));
});
test('导出量不修改原始值、保存恢复、配对拟合与无效数据阻止拟合',()=>{
  const p=starterProject(),d=p.datasets[1]!;
  d.derived=[{id:'inverse',name:'1/U',symbol:'inverseU',unit:'1/V',precision:6,expression:'1/U'}];
  d.plot_axes={x:'inverse',y:d.columns[1]!.id};d.fit={...defaultFit(),enabled:true};
  const before=JSON.stringify(d.rows);
  assert.equal(derivedDataset(d).dataset.rows[0]!.values[2],2);
  assert.equal(JSON.stringify(d.rows),before);
  assert.equal(fitRequest(d)!.points[0]!.x,2);
  assert.deepEqual(parseProject(serialize(p)).datasets[1]!.derived,d.derived);
  d.rows[0]!.values[0]=0;assert.throws(()=>fitRequest(d),/第 1 行/);
  d.rows[0]!.excluded=true;assert.equal(fitRequest(d)!.points.length,9);
});
