import { test } from 'node:test';
import assert from 'node:assert/strict';
import { exampleDataset, id, parseCell, parseProject, pasteCells, serialize, starterProject } from '../src/model';

test('完整项目通过 JSON 往返保留数据、配置、原始精度和排除状态，不保存操作记录', () => {
  const p = starterProject();
  p.datasets[0]!.rows[0]!.values[0] = 12.52123456;
  p.datasets[0]!.rows[1]!.values[0] = null;
  p.datasets[0]!.rows[2]!.excluded = true; p.datasets[0]!.rows[2]!.reason = '仪器移动';
  p.exclusions.push({ dataset_id:p.datasets[0]!.id, row_id:p.datasets[0]!.rows[2]!.id,reason:'仪器移动',at:new Date().toISOString(),action:'exclude' });
  p.datasets[1]!.instrument.note = '电流单位 mA';
  p.plots.showLines = false;
  assert.deepEqual(parseProject(serialize(p)),{...p,exclusions:[]});
});
test('Excel 粘贴保持已有行编号与横纵坐标配对，并扩展新行', () => {
  const d=exampleDataset(2), original=d.rows[9]!.id;
  const next=pasteCells(d,9,0,'5.5\t55.04\r\n6\t60.01\r\n');
  assert.equal(next.rows.length,11); assert.equal(next.rows[9]!.id,original);
  assert.deepEqual(next.rows[10]!.values,[6,60.01]); assert.equal(d.rows.length,10);
});
test('非法粘贴原子失败，不污染原始数据', () => {
  const d=exampleDataset(0), snapshot=JSON.stringify(d);
  assert.throws(()=>pasteCells(d,0,0,'12.5\nNaN'));
  assert.throws(()=>pasteCells(d,0,0,'1\t2'));
  assert.equal(JSON.stringify(d),snapshot);
});
test('仅允许有限十进制数字；空单元格表示缺失值', () => {
  assert.equal(parseCell(' '),null); assert.equal(parseCell(' -1.2e-3 '),-0.0012);
  for(const bad of ['NaN','Infinity','1e999','0xff','1,234','abc']) assert.throws(()=>parseCell(bad));
});
test('拒绝版本不支持、重复变量、重复行编号和错误列数', () => {
  const p=starterProject(); const invalid=()=>parseProject(JSON.stringify(p));
  (p as any).schema_version=2; assert.throws(invalid); p.schema_version=1;
  p.datasets[1]!.columns[1]!.symbol='U'; assert.throws(invalid); p.datasets[1]!.columns[1]!.symbol='I';
  p.datasets[0]!.rows[0]!.id=p.datasets[0]!.rows[1]!.id; assert.throws(invalid); p.datasets[0]!.rows[0]!.id=id();
  p.datasets[0]!.rows[0]!.values.push(1); assert.throws(invalid);
});
test('全部内置示例通过格式校验并明确标记模拟数据', () => {
  for(let i=0;i<5;i++){ const p=starterProject();p.datasets=[exampleDataset(i)];assert.equal(parseProject(serialize(p)).datasets[0]!.simulated,true); }
});
