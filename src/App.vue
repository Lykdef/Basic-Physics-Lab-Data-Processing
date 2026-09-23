<script setup lang="ts">
import { evaluateStatistics } from './statistics';
import DataGrid from './DataGrid.vue';
import FitPanel from './FitPanel.vue';
import PropagationPanel from './PropagationPanel.vue';
import { useFits } from './calculation';
import StatisticsPanel from './StatisticsPanel.vue';
import { buildPlot, resolvePlotAxes } from './plot';
import { computed, onMounted, onUnmounted, ref, watch } from 'vue';
import { Activity, ArrowUpRight, BookOpen, ChartNoAxesCombined, ChevronDown, FlaskConical, FolderClosed, FolderOpen, Grid2X2, Info, ListFilter, Pencil, Plus, Redo2, Ruler, Save, SlidersHorizontal, Table2, Trash2, Undo2, Upload, X, Zap } from 'lucide-vue-next';
import { standardUncertaintyB, type BSource, exampleDataset, exampleInfo, id, makeDataset, newProject, parseCell, parseProject, pasteCells, serialize, starterProject, type Column, type Project } from './model';

const STORAGE = 'physical-lab.workspace.v1';
const emptyProject = newProject('未命名项目');
const targetProjectId = ref('');
const projects = ref<Project[]>([starterProject()]);
const activeProject = ref(projects.value[0]!.project.id);
const activeDataset = ref(projects.value[0]!.datasets[0]!.id);
const project = computed(() => projects.value.find(p => p.project.id === activeProject.value) ?? projects.value[0] ?? emptyProject);
const dataset = computed(() => project.value.datasets.find(d => d.id === activeDataset.value) ?? project.value.datasets[0]!);
const tab = ref('data'); const workspace = ref('workbench'); const selectedColumn = ref(0); const query = ref(''); const showExcluded = ref(true);
watch(()=>dataset.value.kind,kind=>{if(kind==='combined')tab.value='uncertainty';else if(tab.value==='uncertainty' || (kind==='repeated' && tab.value==='propagation') || (kind==='paired' && tab.value==='statistics'))tab.value='data';},{flush:'sync',immediate:true});
const uncertaintyProject=computed(()=>({...project.value,propagation:dataset.value.uncertainty}));
const toast = ref(''); let toastTimer: ReturnType<typeof setTimeout>;
const notice = (message: string) => { toast.value = message; clearTimeout(toastTimer); toastTimer = setTimeout(() => toast.value = '', 4500); };
const recovery = ref('');
try {
  const saved = window.labInitialWorkspace!==undefined ? window.labInitialWorkspace : localStorage.getItem(STORAGE);
  if (saved) { const state = JSON.parse(saved); if (!Array.isArray(state.projects)) throw new Error(); projects.value = state.projects.map((p: unknown) => parseProject(JSON.stringify(p))); activeProject.value = state.activeProject; activeDataset.value = state.activeDataset; }
} catch { recovery.value = '恢复失败，请导入备份'; }
watch([projects, activeProject, activeDataset], () => { try { const content=JSON.stringify({ projects: projects.value, activeProject: activeProject.value, activeDataset: activeDataset.value });if(window.labDesktop?.saveWorkspace){void window.labDesktop.saveWorkspace(content).then(()=>recovery.value='').catch(()=>recovery.value='本机保存失败，请导出项目');}else{localStorage.setItem(STORAGE,content);recovery.value='';} } catch { recovery.value = '本机存储已满，请导出项目'; } }, { deep: true, immediate:true });
const undoStack = ref<string[]>([]); const redoStack = ref<string[]>([]);
function edit(action: () => void) { undoStack.value.push(serialize(project.value)); if (undoStack.value.length > 80) undoStack.value.shift(); redoStack.value = []; action(); project.value.project.modified_at = new Date().toISOString(); }
function replaceProject(raw: string) { const next = parseProject(raw); const i = projects.value.findIndex(p => p.project.id === project.value.project.id); projects.value[i] = next; selectedColumn.value = Math.min(selectedColumn.value, dataset.value.columns.length - 1); }
function undo() { const previous = undoStack.value.pop(); if (!previous) return; redoStack.value.push(serialize(project.value)); replaceProject(previous); }
function redo() { const next = redoStack.value.pop(); if (!next) return; undoStack.value.push(serialize(project.value)); replaceProject(next); }
function switchProject(value: string) { activeProject.value = value; activeDataset.value = project.value.datasets[0]!.id; selectedColumn.value = 0; undoStack.value = []; redoStack.value = []; }
function switchDataset(value: string) { activeDataset.value = value; selectedColumn.value = 0; workspace.value = 'workbench'; }
const column = computed(() => dataset.value.columns[selectedColumn.value] ?? dataset.value.columns[0]!);
const bSource = computed<BSource>(() => dataset.value.instrument.b_sources[column.value.id] ?? {delta:null, distribution:dataset.value.instrument.distribution});
const uB = computed(() => standardUncertaintyB(bSource.value));
const bFormula = computed(() => ({uniform:'δ / √3',triangular:'δ / √6',normal2:'δ / 2',normal3:'δ / 3',normal:'—'}[bSource.value.distribution]));
function updateB(event: Event, key: 'delta' | 'distribution') {
  const el = event.target as HTMLInputElement;
  try {
    const next = {...bSource.value};
    if (key === 'delta') { const value = parseCell(el.value); if (value !== null && value < 0) throw new Error('误差限须为非负数'); next.delta = value; }
    else next.distribution = el.value as BSource['distribution'];
    edit(() => { dataset.value.instrument.b_sources[column.value.id] = next; });
  } catch (e) { notice((e as Error).message); el.value = bSource.value.delta === null ? '' : String(bSource.value.delta); }
}
const suspectedRow = computed(() => { const result = evaluateStatistics(dataset.value, selectedColumn.value, dataset.value.analysis.alpha, null); return result.outlier ? result.candidate?.id : undefined; });




const format = (v: number | null, precision: number) => v === null ? '' : v.toFixed(precision);
function changeCell(event: Event, ri: number, ci: number) { const input = event.target as HTMLInputElement; try { const value = parseCell(input.value); if (value !== dataset.value.rows[ri]!.values[ci]) edit(() => { dataset.value.rows[ri]!.values[ci] = value; }); input.value = format(value, dataset.value.columns[ci]!.precision); } catch (e) { notice((e as Error).message); input.value = format(dataset.value.rows[ri]!.values[ci]!, dataset.value.columns[ci]!.precision); } }
function paste(event: ClipboardEvent, ri: number, ci: number) { const raw = event.clipboardData?.getData('text'); if (!raw) return; event.preventDefault(); try { const next = pasteCells(dataset.value, ri, ci, raw, dataset.value.table_layout); edit(() => { project.value.datasets[project.value.datasets.findIndex(d => d.id === dataset.value.id)] = next; }); } catch (e) { notice((e as Error).message); } }
function addRow() { if (dataset.value.rows.length >= 10000) return notice('每组最多支持 10000 行'); edit(() => dataset.value.rows.push({ id:id(), values:dataset.value.columns.map(() => null), excluded:false, reason:'' })); }
const modal = ref(''); const form = ref({name:'',symbol:'',unit:'',precision:2,kind:'repeated',reason:''}); const modalError = ref(''); const targetRow = ref(''); const targetDatasetId=ref('');
function deleteDataset(value=dataset.value.id){targetDatasetId.value=value;openModal('delete-dataset');}
function openModal(name: string) { modal.value = name; modalError.value = ''; form.value = {name:'',symbol:'',unit:'',precision:2,kind:'repeated',reason:''}; if (name === 'column') form.value = {...form.value,...column.value}; if (name === 'rename') form.value.name = dataset.value.name; }
function submitModal() {
  const f = form.value; modalError.value = '';
  if (['project','dataset','column','add-column','rename'].includes(modal.value) && !f.name.trim()) { modalError.value = '请输入名称'; return; }
  if (modal.value === 'project') { const p = newProject(f.name.trim()); projects.value.push(p); switchProject(p.project.id); workspace.value = 'workbench'; }
  if (modal.value === 'dataset') { const d = makeDataset(f.name.trim(), f.kind as 'paired' | 'repeated' | 'combined'); edit(() => project.value.datasets.push(d)); switchDataset(d.id); }
  if (modal.value === 'rename') edit(() => dataset.value.name = f.name.trim());
  if (['column','add-column'].includes(modal.value)) {
    if (!/^[A-Za-z][A-Za-z0-9_]*$/.test(f.symbol)) { modalError.value = '变量符号须以英文字母开头，仅含字母、数字或下划线'; return; }
    if (dataset.value.columns.some((c,i) => c.symbol === f.symbol && (modal.value === 'add-column' || i !== selectedColumn.value))) { modalError.value = '变量符号已存在'; return; }
    if (!Number.isInteger(Number(f.precision)) || f.precision < 0 || f.precision > 8) { modalError.value = '显示精度须为 0–8 位'; return; }
    const c: Column = { id: modal.value === 'column' ? column.value.id : id(), name:f.name.trim(),symbol:f.symbol,unit:f.unit,precision:Number(f.precision) };
    if (modal.value === 'add-column' && dataset.value.columns.length >= 20) { modalError.value = '每组最多 20 列'; return; }
    edit(() => { if (modal.value === 'column') dataset.value.columns[selectedColumn.value] = c; else { dataset.value.columns.push(c); dataset.value.rows.forEach(r => r.values.push(null)); selectedColumn.value = dataset.value.columns.length - 1; } });
  }
  if (modal.value === 'delete-project') {
    const index=projects.value.findIndex(p=>p.project.id===targetProjectId.value);
    if(index>=0) { projects.value.splice(index,1);
      if(activeProject.value===targetProjectId.value) {if(projects.value.length) switchProject(projects.value[Math.min(index,projects.value.length-1)]!.project.id);else {activeProject.value='';activeDataset.value='';undoStack.value=[];redoStack.value=[];}}
    }
  }
  if (modal.value === 'delete-dataset') {
    if (project.value.datasets.length <= 1) { modalError.value = '至少保留一个数据组'; return; }
    const index = project.value.datasets.findIndex(d => d.id === targetDatasetId.value);
    if(index<0)return;
    const wasActive=dataset.value.id===targetDatasetId.value;
    edit(() => project.value.datasets.splice(index, 1));
    if(wasActive)switchDataset(project.value.datasets[Math.min(index, project.value.datasets.length - 1)]!.id);
  }
  if (modal.value === 'delete-column') { if (dataset.value.columns.length <= 1) return; edit(() => { dataset.value.columns.splice(selectedColumn.value,1); dataset.value.rows.forEach(r => r.values.splice(selectedColumn.value,1)); selectedColumn.value = 0; }); }
  if (modal.value === 'delete-row') edit(() => { dataset.value.rows = dataset.value.rows.filter(r => r.id !== targetRow.value); });
  modal.value = '';
}
function toggleExclude(rowId:string){const r=dataset.value.rows.find(r=>r.id===rowId);if(!r)return;edit(()=>{r.excluded=!r.excluded;r.reason='';});}
function loadExample(index: number) { const d = exampleDataset(index); edit(() => project.value.datasets.push(d)); switchDataset(d.id); modal.value = ''; }
async function saveProject() { if(!projects.value.length) return; try { const content = serialize(project.value); if (window.labDesktop) { if (!await window.labDesktop.saveProject(project.value.project.name, content)) return; } else { const url = URL.createObjectURL(new Blob([content],{type:'application/json'})); const a = document.createElement('a'); a.href = url; a.download = project.value.project.name + '.json'; a.click(); setTimeout(() => URL.revokeObjectURL(url),1000); } notice('项目已导出'); } catch(e) { notice('保存失败：' + (e as Error).message); } }
const fileInput = ref<HTMLInputElement>();
function acceptImport(raw: string) { const p = parseProject(raw); const existing = projects.value.findIndex(v => v.project.id === p.project.id); if (existing >= 0) { p.project.id = id(); p.project.name += '（导入副本）'; } projects.value.push(p); switchProject(p.project.id); workspace.value = 'workbench'; notice('项目已导入'); }
async function openProject() { try { if (window.labDesktop) { const raw = await window.labDesktop.openProject(); if (raw) acceptImport(raw); } else fileInput.value?.click(); } catch(e) { notice((e as Error).message); } }
async function importFile(event: Event) { const input = event.target as HTMLInputElement; const f = input.files?.[0]; if (!f) return; try { if (f.size > 15_000_000) throw new Error('项目超过 15 MB'); acceptImport(await f.text()); } catch(e) { notice((e as Error).message); } input.value = ''; }
function updateInstrument(event: Event, key: 'name' | 'note') { const el = event.target as HTMLInputElement; edit(() => { (dataset.value.instrument[key] as string) = el.value; }); }
function keyboard(e: KeyboardEvent) { if (e.key === 'Escape') modal.value = ''; if (!(e.ctrlKey || e.metaKey)) return; if (e.key.toLowerCase() === 's') { e.preventDefault(); void saveProject(); } if (!['INPUT','TEXTAREA'].includes((e.target as HTMLElement).tagName) && e.key.toLowerCase() === 'z') { e.preventDefault(); e.shiftKey ? redo() : undo(); } }
onMounted(() => window.addEventListener('keydown', keyboard)); onUnmounted(() => { window.removeEventListener('keydown', keyboard); clearTimeout(toastTimer); });
const plotAxes = computed(() => resolvePlotAxes(dataset.value, selectedColumn.value));
function setPlotAxis(axis:'x'|'y', event:Event) { const value= (event.target as HTMLSelectElement).value;edit(()=>dataset.value.plot_axes={...plotAxes.value,[axis]:value}); }
const fits=useFits(project);
const preview=computed(()=>dataset.value.preview ?? {mean:false,relative:false});
function previewOption(key:'mean'|'relative',value:boolean){edit(()=>dataset.value.preview={...preview.value,[key]:value});}
const plot = computed(() => buildPlot(dataset.value, selectedColumn.value, fits[dataset.value.id]?.result?.curve));
</script>

<template>
  <div class="app-shell">
    <aside class="sidebar">
      <a class="brand" href="#" @click.prevent="workspace='workbench'"><span class="brand-symbol"><FlaskConical :size="23" /></span><span>物理实验室</span></a>
      <button class="new-project" @click="openModal('project')"><Plus :size="17"/> 新建项目</button>

      <button class="nav-item" :class="{active:workspace==='workbench'}" @click="workspace='workbench'"><Grid2X2 :size="18"/>实验工作台</button>
      <button class="nav-item" :class="{active:workspace==='examples'}" @click="workspace='examples'"><BookOpen :size="18"/>示例实验</button>
      <div class="nav-label projects-label">项目 <button title="新建项目" @click="openModal('project')"><Plus :size="15"/></button></div>
      <div class="project-tree" v-for="p in projects" :key="p.project.id">
        <div class="project-entry-line"><button class="project-entry" :class="{chosen:p.project.id===project.project.id}" @click="switchProject(p.project.id)"><component :is="p.project.id===project.project.id ? FolderOpen : FolderClosed" :size="17"/><span>{{p.project.name}}</span><ChevronDown v-if="p.project.id===project.project.id" :size="14"/></button><button class="delete-project" :aria-label="`删除项目 ${p.project.name}`" title="删除项目" @click="targetProjectId=p.project.id;openModal('delete-project')"><Trash2 :size="14"/></button></div>
        <div v-if="p.project.id===project.project.id" class="dataset-tree"><div class="dataset-entry" v-for="d in p.datasets.filter(d => !query || d.name.includes(query))" :key="d.id"><button :class="{chosen:d.id===dataset.id}" @click="switchDataset(d.id)"><span class="tree-dot"/><span>{{ d.name }}</span></button><button class="delete-tree-dataset" :aria-label="`删除数据组 ${d.name}`" :disabled="p.datasets.length<=1" title="删除数据组" @click="deleteDataset(d.id)"><Trash2 :size="13"/></button></div><button class="add-dataset" @click="openModal('dataset')"><Plus :size="14"/>添加数据组</button></div>
      </div>
    </aside>
    <div class="main-shell">
      <header class="topbar"><strong>{{workspace==='examples' ? '示例实验' : '实验工作台'}}</strong><div class="topbar-right"><span v-if="recovery" class="error" role="alert">{{recovery}}</span><button class="button" @click="openProject"><Upload :size="16"/>导入项目</button><button class="button primary" :disabled="!projects.length" @click="saveProject"><Save :size="16"/>保存项目</button></div></header>
      <main>
        <template v-if="projects.length">
        <div class="page-title"><h1>{{project.project.name}}</h1><span v-if="workspace==='examples'" class="tiny-tag">模拟数据</span></div>
        <template v-if="workspace==='workbench'">


          <div class="work-area" :class="{'full-width':tab!=='data'}">
            <section class="data-panel panel">
              <div class="dataset-tabs"><button v-for="d in project.datasets" :key="d.id" :class="{selected:d.id===dataset.id}" @click="switchDataset(d.id)"><Table2 :size="14"/>{{d.name}}</button><button title="添加数据组" class="tab-add" @click="openModal('dataset')"><Plus :size="16"/></button></div>

              <div class="view-toolbar"><div class="view-tabs"><button v-if="dataset.kind!=='combined'" :class="{active:tab==='data'}" @click="tab='data'"><Table2 :size="15"/>数据表格</button><button v-if="dataset.kind==='repeated'" :class="{active:tab==='statistics'}" @click="tab='statistics'"><Activity :size="15"/>统计评定</button><button v-if="dataset.kind!=='combined'" :class="{active:tab==='plot'}" @click="tab='plot'"><ChartNoAxesCombined :size="15"/>数据预览</button><button v-if="dataset.kind==='paired'" :class="{active:tab==='propagation'}" @click="tab='propagation'">不确定度传播</button><button v-if="dataset.kind==='combined'" class="active" @click="tab='uncertainty'">不确定度</button></div><div class="table-tools"><span v-if="dataset.simulated" class="simulation">模拟数据</span><button :title="project.datasets.length > 1 ? '删除数据组' : '至少保留一个数据组'" aria-label="删除数据组" :disabled="project.datasets.length <= 1" @click="deleteDataset()"><Trash2 :size="14"/></button><button title="重命名数据组" @click="openModal('rename')"><Pencil :size="14"/></button><button title="撤销" :disabled="!undoStack.length" @click="undo"><Undo2 :size="16"/></button><button title="重做" :disabled="!redoStack.length" @click="redo"><Redo2 :size="16"/></button><span/><button v-if="dataset.kind!=='combined'" title="显示或隐藏已排除数据" :class="{filtered:!showExcluded}" @click="showExcluded=!showExcluded"><ListFilter :size="16"/></button><button v-if="dataset.kind!=='combined'" title="添加变量列" @click="openModal('add-column')"><Plus :size="17"/></button></div></div>
              <DataGrid v-if="tab==='data'" :dataset="dataset" :column-index="selectedColumn" :show-excluded="showExcluded" :suspected-row="suspectedRow" @column="selectedColumn=$event" @layout="edit(()=>dataset.table_layout=$event)" @cell="changeCell" @paste="paste" @exclude="toggleExclude" @delete="targetRow=$event;openModal('delete-row')" @add="addRow"/>
              <StatisticsPanel v-else-if="tab==='statistics'" :dataset="dataset" :column-index="selectedColumn" :u-b="uB" @column="selectedColumn=$event" @alpha="edit(()=>dataset.analysis.alpha=$event)" @exclude="toggleExclude" @error="notice" @digits="edit(()=>dataset.analysis.uncertainty_digits=$event)" @layout="edit(()=>dataset.table_layout=$event)"/>
              <PropagationPanel v-else-if="tab==='uncertainty'" :key="dataset.id" :project="uncertaintyProject" :fits="fits" @change="edit(()=>dataset.uncertainty=$event)"/>
              <PropagationPanel v-else-if="tab==='propagation'" :key="project.project.id" :project="project" :fits="fits" @change="edit(()=>project.propagation=$event)"/>
              <div v-else class="large-plot"><div class="plot-axis-controls"><div><label class="field-label" for="plot-x">自变量 · 横轴</label><select id="plot-x" :disabled="dataset.kind==='repeated'" :value="plotAxes.x" @change="setPlotAxis('x',$event)"><option value="sequence">测量序号</option><option v-for="c in (dataset.kind==='paired'?dataset.columns:[])" :key="c.id" :value="c.id">{{c.name}} · {{c.symbol}}{{c.unit ? ' / '+c.unit : ''}}</option></select></div><div><label class="field-label" for="plot-y">因变量 · 纵轴</label><select id="plot-y" :value="plotAxes.y" @change="setPlotAxis('y',$event)"><option v-for="c in dataset.columns" :key="c.id" :value="c.id">{{c.name}} · {{c.symbol}}{{c.unit ? ' / '+c.unit : ''}}</option></select></div></div><div class="plot-label">{{plot.ylabel}}<span>{{fits[dataset.id]?.result ? (fits[dataset.id]!.result!.manual ? '手动曲线' : '拟合曲线') : ''}}</span></div><svg viewBox="0 0 760 260" role="img" aria-label="原始测量数据预览"><g v-for="tick in plot.yticks" :key="tick.position"><line x1="76" x2="708" :y1="tick.position" :y2="tick.position" stroke="#e8edee" stroke-dasharray="3 4"/><text x="65" :y="tick.position+4" text-anchor="end">{{tick.label}}</text></g><path d="M 76 20 V 190 H 708" fill="none" stroke="#8da69b" stroke-width="1.2"/><g v-for="tick in plot.xticks" :key="tick.position" class="x-tick"><line :x1="tick.position" :x2="tick.position" y1="190" y2="196" stroke="#8da69b"/><text :x="tick.position" y="212" text-anchor="middle">{{tick.label}}</text></g><polyline v-if="dataset.kind==='paired' && project.plots.showLines" :points="plot.line" fill="none" stroke="#7ab8af" stroke-width="1.6"/><polyline v-if="plot.fittedLine" class="fitted-curve" :points="plot.fittedLine" fill="none" stroke="#d18a36" stroke-width="2"/><g v-for="mark in plot.markers" :key="mark.label" class="reference-marker"><line x1="76" x2="708" :y1="mark.py" :y2="mark.py" :stroke="mark.color" stroke-dasharray="6 4"/><text x="704" :y="mark.py-5" text-anchor="end" :style="{fill:mark.color}">{{mark.label}}</text></g><circle v-for="(p,i) in plot.points" :key="i" :cx="p.px" :cy="p.py" r="4" :fill="p.excluded ? '#c7a16a' : '#218477'" stroke="white" stroke-width="2"/><text class="x-axis-label" x="392" y="245" text-anchor="middle">{{plot.xlabel}}</text></svg><label v-if="dataset.kind==='paired'" class="check-label"><input type="checkbox" :checked="project.plots.showLines" @change="edit(()=>project.plots.showLines=!project.plots.showLines)"/>连接数据点</label><div v-if="dataset.kind==='repeated'" class="reference-controls"><label class="check-label"><input type="checkbox" :checked="preview.mean" @change="previewOption('mean',($event.target as HTMLInputElement).checked)"/>显示平均值</label><label class="check-label"><input type="checkbox" :checked="preview.relative" @change="previewOption('relative',($event.target as HTMLInputElement).checked)"/>标准差标线（x̄ ± s）</label><span v-if="preview.relative && plot.standardDeviation===null">至少两次有效测量才能计算标准差</span></div><FitPanel v-if="dataset.kind==='paired'" :dataset="dataset" :state="fits[dataset.id]" @change="edit(()=>{dataset.plot_axes={...plotAxes};dataset.fit=$event})"/></div>

            </section>
            <aside v-if="tab==='data'" class="inspector panel"><div class="inspector-header"><h3><SlidersHorizontal :size="17"/>数据设置</h3></div><section><label class="field-label">数据类型</label><select :value="dataset.kind" @change="edit(()=>dataset.kind=($event.target as HTMLSelectElement).value as 'repeated'|'paired')"><option value="repeated">同一测量量的重复测量</option><option value="paired">不同条件下的成对数据</option></select></section><section><div class="section-title">变量与单位 <button title="添加变量" @click="openModal('add-column')"><Plus :size="14"/></button></div><div class="variables-list"><div v-for="(c,ci) in dataset.columns" :key="c.id" class="variable-box" :class="{selected:ci===selectedColumn}"><button class="variable-select" :aria-label="`选择变量 ${c.name}`" :aria-pressed="ci===selectedColumn" @click="selectedColumn=ci"><span class="variable-symbol">{{c.symbol}}</span><span class="variable-description"><strong>{{c.name}}</strong><small>{{c.unit || '无量纲'}} · {{c.precision}} 位</small></span></button><button class="variable-action" :aria-label="`编辑变量 ${c.name}`" title="编辑变量" @click="selectedColumn=ci;openModal('column')"><Pencil :size="13"/></button><button v-if="dataset.columns.length>1" class="variable-action" :aria-label="`删除变量 ${c.name}`" title="删除变量" @click="selectedColumn=ci;openModal('delete-column')"><Trash2 :size="13"/></button></div></div></section><section><div class="section-title">仪器信息 </div><label class="field-label" for="instrument">测量仪器</label><input id="instrument" :value="dataset.instrument.name" placeholder="例如：游标卡尺" @change="updateInstrument($event,'name')"/><div class="two-fields"><div><label class="field-label" for="instrument-delta">误差限 δ<span v-if="column.unit"> / {{column.unit}}</span></label><input id="instrument-delta" inputmode="decimal" :value="bSource.delta ?? ''" placeholder="δ ≥ 0" @change="updateB($event,'delta')"/></div><div><label class="field-label" for="distribution">分布</label><select id="distribution" :value="bSource.distribution" @change="updateB($event,'distribution')"><option value="uniform">均匀分布</option><option value="triangular">三角分布</option><option v-if="bSource.distribution==='normal'" value="normal" disabled>选择 σ 范围</option><option value="normal3">正态分布 · 3σ</option><option value="normal2">正态分布 · 2σ</option></select></div></div><div class="b-result"><span :title="`变量 ${column.symbol} 的 B 类标准不确定度`">u<sub>B</sub> = {{bFormula}}</span><output aria-label="B 类标准不确定度">{{uB === null ? '—' : String(uB)}}<small v-if="uB !== null && column.unit">&nbsp;{{column.unit}}</small></output></div><label class="field-label" for="instrument-note">备注</label><textarea id="instrument-note" rows="2" :value="dataset.instrument.note"  @change="updateInstrument($event,'note')"/></section></aside>
          </div>


        </template>
        <template v-else-if="workspace==='examples'"><div class="example-grid"><button v-for="(ex,i) in exampleInfo" :key="ex.name" class="example-card panel" @click="loadExample(i)"><span class="example-icon"><component :is="i<2 ? Ruler : i===2 ? Zap : i===3 ? Activity : ChartNoAxesCombined" :size="25"/></span><span class="tiny-tag">{{ex.tag}}</span><h3>{{ex.name}}</h3><span class="example-action">添加 <ArrowUpRight :size="17"/></span></button></div></template>

        </template><div v-else class="empty-state"><h3>暂无项目</h3><button class="button primary" @click="openModal('project')">新建项目</button></div>
      </main>
    </div>
    <input ref="fileInput" type="file" accept=".json,application/json" class="hidden" @change="importFile"/>
    <Transition name="toast"><div v-if="toast" class="toast-message" role="status"><Info :size="18"/>{{toast}}<button title="关闭提示" @click="toast=''"><X :size="15"/></button></div></Transition>
    <div v-if="modal" class="modal-backdrop" @click.self="modal=''"><section class="modal" role="dialog" aria-modal="true" aria-labelledby="modal-title"><button class="modal-close icon-button" aria-label="关闭对话框" @click="modal=''"><X :size="19"/></button>

      <form @submit.prevent="submitModal"><h2 id="modal-title">{{({'project':'新建项目','dataset':'添加数据组','column':'编辑变量','add-column':'添加变量列','rename':'重命名数据组','delete-project':'删除项目','delete-dataset':'删除数据组','delete-column':'删除变量列','delete-row':'删除此行'} as Record<string,string>)[modal]}}</h2><p v-if="modal.startsWith('delete')" class="modal-intro">{{modal==='delete-project' ? `删除“${projects.find(p=>p.project.id===targetProjectId)?.project.name}”？删除后无法恢复。` : modal==='delete-dataset' ? `删除“${project.datasets.find(d=>d.id===targetDatasetId)?.name}”？可撤销。` : '删除后可撤销。'}}</p><template v-if="['project','dataset','column','add-column','rename'].includes(modal)"><label class="field-label" for="form-name">名称</label><input id="form-name" v-model="form.name" autofocus placeholder="输入名称" maxlength="80" required/></template><template v-if="modal==='dataset'"><label class="field-label" for="form-kind">数据类型</label><select id="form-kind" v-model="form.kind"><option value="repeated">同一测量量的重复测量</option><option value="paired">不同条件下的成对数据</option><option value="combined">合成标准不确定度</option></select></template><template v-if="['column','add-column'].includes(modal)"><div class="two-fields"><div><label class="field-label" for="form-symbol">变量符号</label><input id="form-symbol" v-model="form.symbol" placeholder="例如 d" required/></div><div><label class="field-label" for="form-unit">单位</label><input id="form-unit" v-model="form.unit" placeholder="例如 mm"/></div></div><label class="field-label" for="form-precision">显示小数位数（0–8）</label><input id="form-precision" v-model.number="form.precision" type="number" min="0" max="8" required/><div class="info-note"><Info :size="14"/>修改单位不会换算数值。</div></template><p v-if="modalError" class="error" role="alert">{{modalError}}</p><div class="modal-actions"><button type="button" class="button" @click="modal=''">取消</button><button type="submit" class="button" :class="modal.startsWith('delete') ? 'danger' : 'primary'">{{modal.startsWith('delete') ? '确认删除' : '确认'}}</button></div></form>
    </section></div>
  </div>
</template>