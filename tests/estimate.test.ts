import { test } from 'node:test';
import assert from 'node:assert/strict';
import { formatEstimate, formatUncertainty } from '../src/estimate';
import { exampleDataset, pasteCells, starterProject, serialize, parseProject } from '../src/model';
test('最佳估计值与向上修约的不确定度对齐',()=>{
  assert.equal(formatEstimate(12.526,0.01224745,'mm'),'(12.53 ± 0.02) mm');
  assert.equal(formatEstimate(20.02,0.00999,'mm'),'(20.02 ± 0.01) mm');
  assert.equal(formatEstimate(12345,1234,'m'),'(12000 ± 2000) m');
  assert.equal(formatEstimate(5,null,'mm'),'—');
  assert.equal(formatEstimate(5,0,'mm'),'(5 ± 0) mm');
  assert.equal(formatEstimate(1.234e-10,1.2e-12,'m'),'(123 ± 2) × 10^-12 m');
});
test('横向粘贴转置为成对观测，保持稳定编号并扩展测量',()=>{
  const d=exampleDataset(2);const rowId=d.rows[9]!.id;
  const next=pasteCells(d,9,0,'5.5\t6\n55.04\t60.01','horizontal');
  assert.equal(next.rows[9]!.id,rowId);assert.deepEqual(next.rows[9]!.values,[5.5,55.04]);assert.deepEqual(next.rows[10]!.values,[6,60.01]);
  assert.throws(()=>pasteCells(d,0,1,'1\n2','horizontal'));
  assert.throws(()=>pasteCells(d,0,0,'1\tNaN','horizontal'));
});
test('表格方向随项目保存，旧项目默认为纵向',()=>{
  const p=starterProject();p.datasets[0]!.table_layout='horizontal';assert.deepEqual(parseProject(serialize(p)),p);
  const raw=JSON.parse(serialize(p));delete raw.datasets[0].table_layout;assert.equal(parseProject(JSON.stringify(raw)).datasets[0]!.table_layout,'vertical');
});

test('只进不舍、进位、两位选项与四舍六入五凑偶',()=>{
  assert.equal(formatUncertainty(0.01),'0.01');
  assert.equal(formatUncertainty(0.0100000000001),'0.02');
  assert.equal(formatUncertainty(0.0999),'0.1');
  assert.equal(formatUncertainty(0.01224745,2),'0.013');
  assert.equal(formatUncertainty(0.0999,2),'0.10');
  assert.equal(formatEstimate(12.525,0.011,'mm'),'(12.52 ± 0.02) mm');
  assert.equal(formatEstimate(12.535,0.011,'mm'),'(12.54 ± 0.02) mm');
  assert.equal(formatEstimate(12.5251,0.011,'mm'),'(12.53 ± 0.02) mm');
  assert.equal(formatEstimate(12.5249,0.011,'mm'),'(12.52 ± 0.02) mm');
  assert.equal(formatEstimate(-12.525,0.011,'mm'),'(-12.52 ± 0.02) mm');
  assert.equal(formatEstimate(-12.535,0.011,'mm'),'(-12.54 ± 0.02) mm');
  assert.equal(formatEstimate(12.526,0.01224745,'mm',2),'(12.526 ± 0.013) mm');
});
