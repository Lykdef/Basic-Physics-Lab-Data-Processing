import { z } from 'zod';
import { defaultPropagation, fitSchema, propagationSchema } from './advanced-model';

const columnSchema = z.object({ id: z.string().min(1), name: z.string().min(1), symbol: z.string().regex(/^[A-Za-z][A-Za-z0-9_]*$/), unit: z.string(), precision: z.number().int().min(0).max(8) });
const rowSchema = z.object({ id: z.string().min(1), values: z.array(z.number().finite().nullable()), excluded: z.boolean(), reason: z.string() });
export const bSourceSchema = z.object({ delta: z.number().finite().nonnegative().nullable(), distribution: z.enum(['uniform', 'triangular', 'normal2', 'normal3', 'normal']) });
export type BSource = z.infer<typeof bSourceSchema>;
export function standardUncertaintyB(source: BSource): number | null {
  if (source.delta === null || source.distribution === 'normal') return null;
  const divisor = { uniform: Math.sqrt(3), triangular: Math.sqrt(6), normal2: 2, normal3: 3 }[source.distribution];
  return source.delta / divisor;
}
const datasetSchema = z.object({ uncertainty:propagationSchema.optional(), preview:z.object({mean:z.boolean(),relative:z.boolean()}).optional(), fit:fitSchema.optional(), id: z.string().min(1), name: z.string().min(1), kind: z.enum(['repeated', 'paired', 'combined']), description: z.string(), simulated: z.boolean(), plot_axes: z.object({x:z.string(),y:z.string()}).nullable().default(null), table_layout: z.enum(['vertical','horizontal']).default('vertical'), analysis: z.object({ uncertainty_digits: z.union([z.literal(1),z.literal(2)]).default(1), alpha: z.number().finite().min(0.000001).max(0.2).transform(value=>value===0.01?0.01:0.05) }).default({alpha:0.05,uncertainty_digits:1}), columns: z.array(columnSchema).min(1).max(20), rows: z.array(rowSchema).max(10000), instrument: z.object({ name: z.string(), b_sources: z.record(bSourceSchema).default({}), range: z.string().default(''), resolution: z.number().finite().nonnegative().optional(), distribution: z.enum(['uniform', 'triangular', 'normal']), note: z.string() }) }).superRefine((d, ctx) => {
  if (new Set(d.columns.map(c => c.symbol)).size !== d.columns.length) ctx.addIssue({ code: 'custom', message: '同一数据组的变量符号不能重复' });
  if (new Set(d.columns.map(c => c.id)).size !== d.columns.length || new Set(d.rows.map(r => r.id)).size !== d.rows.length) ctx.addIssue({ code: 'custom', message: '行或列编号重复' });
  if (d.rows.some(r => r.values.length !== d.columns.length)) ctx.addIssue({ code: 'custom', message: '数据列数不一致' });
});
export const projectSchema = z.object({ propagation:propagationSchema.optional(), schema_version: z.literal(1), project: z.object({ id: z.string(), name: z.string().min(1), description: z.string(), created_at: z.string().datetime(), modified_at: z.string().datetime() }), datasets: z.array(datasetSchema).min(1).max(100), exclusions: z.array(z.object({ dataset_id: z.string(), row_id: z.string(), reason: z.string(), at: z.string(), action: z.enum(['exclude', 'restore']) })).default([]).transform(logs=>logs.slice(0,0)), uncertainty_sources: z.array(z.unknown()), measurement_models: z.array(z.unknown()), fits: z.array(z.unknown()), plots: z.object({ showLines: z.boolean() }), provenance: z.object({ software_version: z.string(), stage: z.literal('foundation') }) }).superRefine((p, ctx) => { if (new Set(p.datasets.map(d => d.id)).size !== p.datasets.length) ctx.addIssue({ code: 'custom', message: '数据组编号重复' }); });
export type Project = z.infer<typeof projectSchema>;
export type Dataset = Project['datasets'][number];
export type Column = Dataset['columns'][number];
export const id = () => crypto.randomUUID();
export const clone = <T>(v: T): T => JSON.parse(JSON.stringify(v));
export function makeDataset(name = '新数据组', kind: Dataset['kind'] = 'repeated'): Dataset {
  return { ...(kind==='combined'?{uncertainty:defaultPropagation()}:{}), id: id(), name, kind, description: '', simulated: false, plot_axes:null, table_layout:'vertical', analysis: {alpha:0.05,uncertainty_digits:1}, columns: [{ id: id(), name: '测量值', symbol: 'x', unit: 'mm', precision: 3 }], rows: Array.from({ length: kind==='combined'?0:2 }, () => ({ id: id(), values: [null], excluded: false, reason: '' })), instrument: { name: '', b_sources: {}, range: '', distribution: 'uniform', note: '' } };
}
export function newProject(name: string): Project {
  const now = new Date().toISOString();
  return { schema_version: 1, project: { id: id(), name, description: '', created_at: now, modified_at: now }, datasets: [makeDataset()], exclusions: [], uncertainty_sources: [], measurement_models: [], fits: [], plots: { showLines: true }, provenance: { software_version: '0.1.0', stage: 'foundation' } };
}
export const exampleInfo = [
  { name: '长度的重复测量', tag: '重复测量', detail: '用游标卡尺测量圆柱体直径，熟悉重复测量数据的录入与管理。', icon: 'ruler' },
  { name: '含疑似异常值的测量', tag: '异常值示例', detail: '保留一个偏离较大的模拟数值，为后续 Grubbs 检验准备数据。', icon: 'scan' },
  { name: '伏安法测电阻', tag: '成对数据', detail: '记录不同电压下的电流，保留每次测量的对应关系。', icon: 'zap' },
  { name: '单摆测重力加速度', tag: '成对数据', detail: '记录摆长与周期，为测量模型和不确定度传播准备数据。', icon: 'orbit' },
  { name: '指数衰减', tag: '成对数据', detail: '模拟电容放电过程，为后续指数模型拟合准备数据。', icon: 'chart' }
];
export function exampleDataset(index: number): Dataset {
  const d = makeDataset(exampleInfo[index]!.name, index < 2 ? 'repeated' : 'paired'); d.simulated = true; d.description = exampleInfo[index]!.detail;
  const specs: [string, string, string, number][][] = [ [['直径', 'd', 'mm', 2]], [['长度', 'L', 'mm', 2]], [['电压', 'U', 'V', 2], ['电流', 'I', 'mA', 2]], [['摆长', 'L', 'm', 3], ['周期', 'T', 's', 3]], [['时间', 't', 's', 1], ['电压', 'U', 'V', 3]] ];
  const data: number[][][] = [ [[12.52],[12.54],[12.50],[12.56],[12.52],[12.54],[12.50],[12.52],[12.54],[12.52]], [[20.02],[20.04],[20.00],[20.03],[20.01],[20.02],[20.35],[20.03],[20.01],[20.02]], [[0.5,5.02],[1,9.98],[1.5,15.06],[2,20.01],[2.5,24.95],[3,30.08],[3.5,34.99],[4,40.04],[4.5,44.96],[5,50.03]], [[0.4,1.269],[0.5,1.419],[0.6,1.554],[0.7,1.679],[0.8,1.795],[0.9,1.903],[1,2.007]], Array.from({length: 10}, (_,i) => [i, Number((5 * Math.exp(-i / 3)).toFixed(3))]) ];
  d.columns = specs[index]!.map(([name,symbol,unit,precision]) => ({id:id(),name,symbol,unit,precision}));
  d.rows = data[index]!.map(values => ({id:id(),values,excluded:false,reason:''}));
  d.instrument = {b_sources: {}, name: index < 2 ? '游标卡尺' : index === 2 ? '数字万用表' : index === 3 ? '米尺与电子秒表' : '数字电压表', range: ['0–150 mm', '0–150 mm', '0–20 V / 0–200 mA', '0–2 m / 0–60 s', '0–20 V'][index]!, distribution: 'uniform', note: '教学模拟数据；仪器参数为示例假设，请按实际仪器修改。'};
  return d;
}
export function starterProject(): Project {
  const p = newProject('基础物理实验'); p.project.description = '从一次测量开始，让每一个数据都有据可循。'; p.datasets = [exampleDataset(0), exampleDataset(2), exampleDataset(3)]; return p;
}
export function serialize(p: Project): string { return JSON.stringify(projectSchema.parse(p), null, 2); }
export function parseProject(raw: string): Project {
  if (raw.length > 15_000_000) throw new Error('项目超过 15 MB，请拆分后导入。');
  try { return projectSchema.parse(JSON.parse(raw)); } catch (e) { if (e instanceof z.ZodError) throw new Error('项目格式不正确：' + e.issues[0]?.message); throw new Error('无法读取 JSON，请检查文件内容。'); }
}
export function parseCell(raw: string): number | null {
  const v = raw.trim(); if (!v) return null;
  if (!/^[+-]?(?:\d+\.?\d*|\.\d+)(?:e[+-]?\d+)?$/i.test(v) || !Number.isFinite(Number(v))) throw new Error(`“${v}”不是有效数字`);
  return Number(v);
}
export function pasteCells(d: Dataset, rowIndex: number, colIndex: number, text: string, layout: 'vertical'|'horizontal' = 'vertical'): Dataset {
  const pasted = text.replace(/\r/g, '').replace(/\n+$/, '').split('\n').map(l => l.split('\t').map(parseCell));
  const lines = layout === 'horizontal' ? Array.from({length:Math.max(...pasted.map(row=>row.length))},(_,i)=>pasted.map(row=>row[i] ?? null)) : pasted;
  if (lines.some(l => l.length + colIndex > d.columns.length)) throw new Error('粘贴的列数超出表格，请先添加变量列。');
  if (rowIndex + lines.length > 10000) throw new Error('每组最多支持 10000 行。');
  const next = clone(d);
  lines.forEach((values, ri) => { const index = rowIndex + ri; while (next.rows.length <= index) next.rows.push({id:id(),values:next.columns.map(() => null),excluded:false,reason:''}); values.forEach((v, ci) => { next.rows[index]!.values[colIndex + ci] = v; }); });
  return next;
}
