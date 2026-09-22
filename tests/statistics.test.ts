import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { evaluateStatistics, grubbsCritical, histogram } from '../src/statistics';
import { exampleDataset, parseProject, serialize, starterProject } from '../src/model';
const references=JSON.parse(readFileSync(new URL('./statistics-reference.json',import.meta.url),'utf8'));
const close=(actual:number,expected:number,tolerance=1e-8)=>assert.ok(Math.abs(actual-expected)<=tolerance*Math.max(1,Math.abs(expected)),`${actual} != ${expected}`);
test('Grubbs 临界值与 SciPy 独立网格一致（n=3–10000，α=0.01、0.05）',()=>{
  for(const c of references.criticals.filter((c:any)=>c.alpha===0.01 || c.alpha===0.05)) close(grubbsCritical(c.n,c.alpha),c.critical,2e-7);
});
test('均值、s、uA、G 与 SciPy 独立样本一致',()=>{
  for(const c of references.samples) {
    const d=exampleDataset(0);d.rows=c.values.map((value:number,i:number)=>({id:String(i),values:[value],excluded:false,reason:''}));
    const r=evaluateStatistics(d,0,0.05,0.01);
    const tolerance=c.mean>1e10?0.002:1e-10;
    close(r.mean!,c.mean);close(r.s!,c.s,tolerance);close(r.uA!,c.uA,tolerance);close(r.g!,c.g,tolerance);
    close(r.combined!,Math.hypot(r.uA!,0.01));
  }
});
test('异常点编号、排除重算、缺失值与未知 B 类处理',()=>{
  const d=exampleDataset(1);let r=evaluateStatistics(d,0,0.05,null);
  assert.equal(r.outlier,true);assert.equal(r.candidate?.id,d.rows[6]!.id);assert.equal(r.combined,null);
  d.rows[6]!.excluded=true;d.rows[6]!.reason='读数异常';d.rows[0]!.values[0]=null;
  r=evaluateStatistics(d,0,0.05,0);assert.equal(r.n,8);assert.equal(r.missing,1);assert.equal(r.excluded,1);assert.equal(r.outlier,false);assert.equal(r.combined,r.uA);
});
test('成对数据、单点、常数、空值与超范围提示',()=>{
  const d=exampleDataset(0);d.kind='paired';assert.equal(evaluateStatistics(d,0,0.05,0).uA,null);d.kind='repeated';
  d.rows=d.rows.slice(0,1);assert.equal(evaluateStatistics(d,0,0.05,0).uA,null);
  d.rows=[];assert.equal(evaluateStatistics(d,0,0.05,0).mean,null);
  for(const values of [[1,1,1],[0,0,0]]){d.rows=values.map((v,i)=>({id:String(i),values:[v],excluded:false,reason:''}));const r=evaluateStatistics(d,0,0.05,0);assert.equal(r.s,0);assert.equal(r.g,null);}
  d.rows=[-1e308,1e308,1e308].map((v,i)=>({id:String(i),values:[v],excluded:false,reason:''}));assert.ok(Number.isFinite(evaluateStatistics(d,0,0.05,0).s));
  assert.throws(()=>grubbsCritical(2,0.05));assert.throws(()=>grubbsCritical(10,0));assert.throws(()=>grubbsCritical(10,0.02));
  for(const alpha of [0.01,0.05])for(let n=3;n<=10000;n++){const value=grubbsCritical(n,alpha);assert.ok(Number.isFinite(value) && value>0);}
});
test('显著性水平持久化，旧项目补默认值；直方图不丢数据',()=>{
  const p=starterProject();p.datasets[0]!.analysis.alpha=0.01;assert.deepEqual(parseProject(serialize(p)),p);
  const raw=JSON.parse(serialize(p));delete raw.datasets[0].analysis;assert.equal(parseProject(JSON.stringify(raw)).datasets[0]!.analysis.alpha,0.05);
  const values=[1,1,2,4,5,9];assert.equal(histogram(values).reduce((s,b)=>s+b.count,0),values.length);
});
