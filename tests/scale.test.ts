import {test} from 'node:test';
import assert from 'node:assert/strict';
import {niceScale} from '../src/scale';
import {exampleDataset} from '../src/model';
import {buildPlot} from '../src/plot';
test('标度使用 1、2、5 间隔，覆盖原范围且不产生浮点尾数',()=>{
 for(const [min,max] of [[.005,.027],[34.72,34.79],[-3,7],[1,9000],[0,1e-8]]){
  const s=niceScale(min!,max!);assert.ok(s.min<=min! && s.max>=max!);assert.ok([1,2,5].includes(Number((s.step/10**Math.floor(Math.log10(s.step))).toPrecision(10))));
  assert.ok(s.ticks.length<=12);
 }
 assert.deepEqual(niceScale(.005,.027,5).ticks,[.005,.01,.015,.02,.025,.03]);
});
test('重复测量忽略旧横轴与拟合曲线',()=>{
 const d=exampleDataset(0);d.plot_axes={x:d.columns[0]!.id,y:d.columns[0]!.id};const p=buildPlot(d,0,[[1,999]]);
 assert.equal(p.xlabel,'测量序号');assert.equal(p.points[0]!.x,1);assert.equal(p.fittedLine,'');assert.ok(p.yticks.every(t=>Number(t.label)<13));
});
