import { test } from 'node:test';
import assert from 'node:assert/strict';
import { standardUncertaintyB, bSourceSchema, starterProject, serialize, parseProject } from '../src/model';
test('按用户给定的四种分布换算误差限', () => {
  assert.equal(standardUncertaintyB({delta:6,distribution:'uniform'}),6/Math.sqrt(3));
  assert.equal(standardUncertaintyB({delta:6,distribution:'triangular'}),6/Math.sqrt(6));
  assert.equal(standardUncertaintyB({delta:6,distribution:'normal3'}),2);
  assert.equal(standardUncertaintyB({delta:6,distribution:'normal2'}),3);
  assert.equal(standardUncertaintyB({delta:0,distribution:'uniform'}),0);
  assert.equal(standardUncertaintyB({delta:null,distribution:'uniform'}),null);
  assert.equal(standardUncertaintyB({delta:6,distribution:'normal'}),null);
  for (const delta of [-1,Infinity,NaN]) assert.equal(bSourceSchema.safeParse({delta,distribution:'uniform'}).success,false);
});
test('不同单位的变量独立保存 δ；旧量程不自动转为误差限', () => {
  const p=starterProject(), d=p.datasets[1]!;
  d.instrument.b_sources[d.columns[0]!.id]={delta:0.1,distribution:'normal2'};
  d.instrument.b_sources[d.columns[1]!.id]={delta:0.2,distribution:'triangular'};
  assert.deepEqual(parseProject(serialize(p)),p);
  const raw=JSON.parse(serialize(p));delete raw.datasets[1].instrument.b_sources;
  assert.deepEqual(parseProject(JSON.stringify(raw)).datasets[1]!.instrument.b_sources,{});
});
