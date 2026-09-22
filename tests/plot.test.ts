import { test } from 'node:test';
import assert from 'node:assert/strict';
import { buildPlot } from '../src/plot';
import { exampleDataset, starterProject, parseProject, serialize } from '../src/model';
test('旧文件保留原分辨力，量程留空，不改变字段含义', () => {
  const p = starterProject(); const instrument = p.datasets[0]!.instrument as any;
  delete instrument.range; instrument.resolution = 0.02;
  const loaded = parseProject(JSON.stringify(p));
  assert.equal(loaded.datasets[0]!.instrument.range, '');
  assert.equal(loaded.datasets[0]!.instrument.resolution, 0.02);
});
test('任意轴选择以行编号配对，缺失值不移位，选择随项目保存',()=>{
  const p=starterProject(),d=p.datasets[1]!;
  d.plot_axes={x:d.columns[1]!.id,y:d.columns[0]!.id};
  d.rows[1]!.values[1]=null;
  const plot=buildPlot(d,0);
  assert.equal(plot.xlabel,'电流 / mA');assert.equal(plot.ylabel,'电压 / V');
  assert.deepEqual([plot.points[1]!.x,plot.points[1]!.y,plot.points[1]!.id],[15.06,1.5,d.rows[2]!.id]);
  assert.deepEqual(parseProject(serialize(p)),p);
  d.plot_axes.x='sequence';assert.equal(buildPlot(d,0).xlabel,'测量序号');
  d.columns.splice(1,1);d.rows.forEach(r=>r.values.splice(1,1));
  assert.ok(buildPlot(d,0).points.every(v=>Number.isFinite(v.py)));
});
test('横轴分别使用序号与成对数据的真实数值、单位', () => {
  const repeated = buildPlot(exampleDataset(0), 0);
  assert.equal(repeated.xlabel, '测量序号');
  assert.equal(repeated.xticks[0]!.label, '1');
  assert.equal(repeated.xticks.at(-1)!.label, '10');
  const paired = buildPlot(exampleDataset(2), 0);
  assert.equal(paired.xlabel, '电压 / V');
  assert.equal(paired.xticks[0]!.label, '0');
  assert.equal(paired.xticks.at(-1)!.label, '5');
});
test('单点、空数据、恒定横坐标保持有限坐标', () => {
  const d = exampleDataset(2);
  for (const rows of [[], [d.rows[0]!], d.rows.map(r=>({...r,values:[1,r.values[1]!]}))]) {
    d.rows = rows; const p = buildPlot(d,0);
    assert.ok(p.xticks.every(t=>Number.isFinite(t.position)));
    assert.ok(p.points.every(v=>Number.isFinite(v.px) && Number.isFinite(v.py)));
  }
});
