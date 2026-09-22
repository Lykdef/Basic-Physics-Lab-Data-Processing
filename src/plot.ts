import { evaluateStatistics } from './statistics';
import { niceScale, niceStep } from './scale';
import type { Dataset } from './model';

export function resolvePlotAxes(dataset:Dataset, selectedColumn=0) {
  const defaults={x:dataset.kind==='paired' && dataset.columns.length>1 ? dataset.columns[0]!.id : 'sequence',y:dataset.columns[dataset.kind==='paired' && dataset.columns.length>1 ? 1 : selectedColumn]?.id ?? dataset.columns[0]!.id};
  const saved=dataset.plot_axes;
  return {x:dataset.kind==='repeated' ? 'sequence' : saved && (saved.x==='sequence' || dataset.columns.some(c=>c.id===saved.x)) ? saved.x : defaults.x,
    y:saved && dataset.columns.some(c=>c.id===saved.y) ? saved.y : defaults.y};
}
export function buildPlot(dataset: Dataset, selectedColumn: number, curve: number[][] = []) {
  if(dataset.kind==='repeated')curve=[];
  const axes=resolvePlotAxes(dataset,selectedColumn);
  const paired=axes.x!=='sequence';
  const xi=dataset.columns.findIndex(c=>c.id===axes.x),yi=dataset.columns.findIndex(c=>c.id===axes.y);
  const xcol=dataset.columns[xi] ?? dataset.columns[0]!;
  const ycol=dataset.columns[yi]!;
  const label = (c: typeof xcol) => c.unit ? `${c.name} / ${c.unit}` : c.name;
  const values = dataset.rows.map((r, i) => ({ id:r.id, x: paired ? r.values[xi] : i + 1, y: r.values[yi], excluded: r.excluded }))
    .filter((p): p is {id:string; x: number; y: number; excluded: boolean} => p.x != null && p.y != null);
  const statistics=dataset.kind==='repeated'?evaluateStatistics(dataset,yi,dataset.analysis.alpha,null):null;
  const mean=statistics?.mean ?? null, standardDeviation=statistics?.s ?? null;
  const markers:{value:number;label:string;color:string}[]=[];
  if(mean!==null){
    if(dataset.preview?.mean)markers.push({value:mean,label:`平均值 ${Number(mean.toPrecision(7))}`,color:'#218477'});
    if(dataset.preview?.relative && standardDeviation!==null){const offset=standardDeviation;
      for(const sign of [-1,1]){const value=mean+sign*offset;if(Number.isFinite(value))markers.push({value,label:`x̄ ${sign>0?'+':'−'} s · ${Number(value.toPrecision(7))}`,color:'#b78238'});}
    }
  }
  const xs = values.map(p => p.x), ys = [...values.map(p => p.y), ...curve.map(p=>p[1]!), ...markers.map(m=>m.value)];
  let xmin = xs.length ? Math.min(...xs) : 1, xmax = xs.length ? Math.max(...xs) : 10;
  if (xmin === xmax) { const pad = paired ? Math.abs(xmin) * 0.1 || 1 : 1; xmin -= pad; xmax += pad; }
  const ymin = ys.length ? Math.min(...ys) : 0, ymax = ys.length ? Math.max(...ys) : 1;
  const pad = (ymax - ymin || Math.abs(ymax) * 0.01 || 1) * 0.3;
  const yscale=niceScale(ymin-pad,ymax+pad,5);
  const low=yscale.min,high=yscale.max;
  const xscale=niceScale(xmin,xmax);
  if(paired){xmin=xscale.min;xmax=xscale.max;}
  const px = (v: number) => 76 + (v - xmin) / (xmax - xmin) * 632;
  const py = (v: number) => 190 - (v - low) / (high - low) * 170;
  const tickLabel = (v: number) => Number(v.toPrecision(6)).toString();
  const points = values.map(p => ({ ...p, px: px(p.x), py: py(p.y) }));
  const first = paired ? xmin : Math.max(1,Math.ceil(xmin));
  const last = Math.floor(xmax);
  const step = last-first <= 49 ? 1 : niceStep(last-first,15);
  const xvalues = paired ? xscale.ticks
    : Array.from({length:Math.floor((last-first)/step)+1},(_,i)=>first+i*step);
  return { mean, standardDeviation, markers:markers.map(m=>({...m,py:py(m.value)})), points, fittedLine:curve.map(p=>`${px(p[0]!)},${py(p[1]!)}`).join(' '), line: points.filter(p => !p.excluded).map(p => `${p.px},${p.py}`).join(' '),
    xlabel: paired ? label(xcol) : '测量序号', ylabel: label(ycol),
    xticks: xvalues.map(v => ({position: px(v), label: tickLabel(v)})),
    yticks: yscale.ticks.map(v => { return {position: py(v), label: tickLabel(v)}; }) };
}
