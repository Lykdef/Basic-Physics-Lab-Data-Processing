import {test} from 'node:test';
import assert from 'node:assert/strict';
import {starterProject,serialize,parseProject} from '../src/model';
import {buildPlot} from '../src/plot';
test('无理由排除可保存；标线使用有效均值，负均值方向正确',()=>{
 const p=starterProject(),d=p.datasets[0]!;d.preview={mean:true,relative:true};d.rows=d.rows.slice(0,3);d.rows[0]!.values=[100];d.rows[0]!.excluded=true;d.rows[1]!.values=[-10];d.rows[2]!.values=[-12];
 assert.deepEqual(parseProject(serialize(p)),p);const plot=buildPlot(d,0);assert.equal(plot.mean,-11);assert.deepEqual(plot.markers.map(m=>m.value),[-11,-11-Math.sqrt(2),-11+Math.sqrt(2)]);assert.ok(plot.markers.every(m=>m.py>=20 && m.py<=190));
 d.rows[1]!.values=[-1];d.rows[2]!.values=[1];assert.equal(buildPlot(d,0).markers.length,3);
 d.rows[2]!.excluded=true;assert.equal(buildPlot(d,0).markers.length,1);
 d.rows.forEach(r=>r.excluded=true);assert.equal(buildPlot(d,0).markers.length,0);
});
