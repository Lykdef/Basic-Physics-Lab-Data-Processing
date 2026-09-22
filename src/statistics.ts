import grubbsTable from './grubbs-table.json';
import type { Dataset } from './model';

export function grubbsCritical(n: number, alpha: number): number {
  if(!Number.isInteger(n) || n<3 || n>10000 || (alpha!==0.01 && alpha!==0.05))throw new Error('Grubbs 查表支持 n = 3–10000，α = 0.01 或 0.05');
  return grubbsTable[alpha===0.01?'0.01':'0.05'][n-3]!;
}
export function evaluateStatistics(dataset: Dataset, columnIndex: number, alpha: number, uB: number | null) {
  const samples = dataset.rows.map((r, i) => ({id:r.id, row:i + 1, value:r.values[columnIndex], excluded:r.excluded}))
    .filter((r): r is {id:string;row:number;value:number;excluded:boolean} => !r.excluded && r.value != null);
  const n = samples.length;
  const result = { n, excluded:dataset.rows.filter(r=>r.excluded).length, missing:dataset.rows.filter(r=>!r.excluded && r.values[columnIndex]==null).length,
    mean:null as number|null, s:null as number|null, uA:null as number|null, combined:null as number|null,
    g:null as number|null, critical:null as number|null, candidate:null as typeof samples[number]|null, outlier:false,
    reason:'', grubbsReason:'', samples };
  if (dataset.kind !== 'repeated') { result.reason='成对数据不适用重复测量评定'; return result; }
  if (!n) { result.reason='没有有效测量值'; return result; }
  // Scale and shift before compensated sums: avoid overflow for large finite values.
  const sum = (values: number[]) => { let total=0, correction=0; for(const value of values) {const y=value-correction;const t=total+y;correction=(t-total)-y;total=t;} return total; };
  const anchor = samples[0]!.value;
  const shifted = samples.map(r=>r.value-anchor);
  const canShift = shifted.every(Number.isFinite);
  const scale = Math.max(...(canShift ? shifted : samples.map(r=>r.value)).map(Math.abs)) || 1;
  const normalized = canShift ? shifted.map(v=>v/scale) : samples.map(r=>r.value/scale);
  const center = sum(normalized) / n;
  result.mean = canShift ? anchor + center * scale : center * scale;
  if (n < 2) { result.reason='至少 2 次有效测量才能估计 A 类不确定度'; result.grubbsReason='Grubbs 至少需要 3 次有效测量'; return result; }
  const deviations = normalized.map(v=>v-center);
  const normalizedS = Math.sqrt(sum(deviations.map(v=>v*v)) / (n-1));
  result.s = normalizedS * scale;
  result.uA = normalizedS / Math.sqrt(n) * scale;
  if (!Number.isFinite(result.s) || !Number.isFinite(result.uA) || !Number.isFinite(result.mean)) {result.mean=null;result.s=null;result.uA=null;result.reason='数值超出计算范围，请换用合适的单位';return result;}
  if (uB !== null) { const combined=Math.hypot(result.uA,uB); if (Number.isFinite(combined)) result.combined=combined; }
  if (n<3) {result.grubbsReason='Grubbs 至少需要 3 次有效测量';return result;}
  if (normalizedS===0) {result.grubbsReason='数据无离散性，无法计算 G';return result;}
  let index=0;for(let i=1;i<n;i++) if(Math.abs(deviations[i]!)>Math.abs(deviations[index]!)) index=i;
  result.g=Math.abs(deviations[index]!) / normalizedS;
  result.critical=grubbsCritical(n,alpha);
  result.candidate=samples[index]!;
  result.outlier=result.g>result.critical;
  return result;
}

export function histogram(values: number[]) {
  if (!values.length) return [];
  const low=Math.min(...values), high=Math.max(...values);
  if(low===high) return [{low, high, count:values.length}];
  const count=Math.min(12,Math.max(3,Math.ceil(Math.sqrt(values.length))));
  const step=(high-low)/count;
  if (!Number.isFinite(step) || step===0) return [];
  const bins=Array.from({length:count},(_,i)=>({low:low+i*step,high:low+(i+1)*step,count:0}));
  for(const v of values) bins[Math.min(count-1,Math.floor((v-low)/step))]!.count++;
  return bins;
}
