<script setup lang="ts">
import { niceScale } from './scale';
import DataGrid from './DataGrid.vue';
import { formatEstimate, formatUncertainty } from './estimate';
import { computed } from 'vue';
import type { Dataset } from './model';
import { evaluateStatistics, histogram } from './statistics';
const props=defineProps<{dataset:Dataset; columnIndex:number; uB:number|null}>();
const emit=defineEmits<{digits:[1|2];layout:['vertical'|'horizontal'];column:[index:number];alpha:[value:0.01|0.05];exclude:[rowId:string];error:[message:string]}>();
const column=computed(()=>props.dataset.columns[props.columnIndex]!);
const alpha=computed(()=>props.dataset.analysis.alpha);
const result=computed(()=>evaluateStatistics(props.dataset,props.columnIndex,alpha.value,props.uB));
const estimate=computed(()=>formatEstimate(result.value.mean,result.value.combined,column.value.unit,props.dataset.analysis.uncertainty_digits));
const bins=computed(()=>histogram(result.value.samples.map(r=>r.value)));
const frequencyScale=computed(()=>niceScale(0,Math.max(1,...bins.value.map(b=>b.count)),4,true));
const highest=computed(()=>frequencyScale.value.max);
const value=(n:number|null)=>n===null?'—':Number(n.toPrecision(7)).toString();
function changeAlpha(event:Event) {
  const input=event.target as HTMLInputElement;
  const n=Number(input.value);
  if (!input.value.trim() || !Number.isFinite(n) || (n!==0.01 && n!==0.05)) {emit('error','显著性水平 α 请选择 0.01 或 0.05');input.value=String(alpha.value);return;}
  emit('alpha',n as 0.01|0.05);
}
</script>

<template>
  <div class="statistics-panel">
    <div class="analysis-controls"><label for="analysis-column">变量</label><select id="analysis-column" :value="columnIndex" @change="emit('column',Number(($event.target as HTMLSelectElement).value))"><option v-for="(c,i) in dataset.columns" :key="c.id" :value="i">{{c.name}} · {{c.symbol}}{{c.unit ? ' / '+c.unit : ''}}</option></select><output class="inline-estimate" aria-label="变量最佳估计值">{{estimate}}</output></div>
    <DataGrid :dataset="dataset" :column-index="columnIndex" :readonly="true" :suspected-row="result.outlier ? result.candidate?.id : undefined" @column="emit('column',$event)" @layout="emit('layout',$event)"/>
    <p v-if="dataset.kind==='paired'" class="analysis-message">{{result.reason}}</p>
    <template v-else>
      <section class="grubbs-section"><div class="grubbs-header"><h3>Grubbs 双侧检验</h3><label for="grubbs-alpha">α</label><select id="grubbs-alpha" aria-label="显著性水平" :value="alpha" @change="changeAlpha"><option :value="0.01">0.01</option><option :value="0.05">0.05</option></select></div>
        <p v-if="result.grubbsReason || result.reason" class="analysis-message">{{result.grubbsReason || result.reason}}</p>
        <template v-else><div class="grubbs-numbers"><span>G <strong data-testid="grubbs-g">{{value(result.g)}}</strong></span><span>G<sub>crit</sub> <strong data-testid="grubbs-critical">{{value(result.critical)}}</strong></span></div><div class="grubbs-verdict" :class="{suspected:result.outlier}"><span v-if="result.outlier">疑似异常：第 {{result.candidate!.row}} 行 · {{value(result.candidate!.value)}} {{column.unit}}</span><span v-else>未检出异常值</span><button v-if="result.outlier" class="button small" @click="emit('exclude',result.candidate!.id)">排除此点</button></div></template>
        <p class="analysis-note">适用于近似正态样本的单异常值检验；连续排除不保持原整体显著性水平。</p>
      </section>
      <div class="sample-count">n = {{result.n}}<span v-if="result.missing">缺失 {{result.missing}}</span><span v-if="result.excluded">排除 {{result.excluded}}</span></div>
      <table class="statistics-table"><thead><tr><th>统计量</th><th>结果<span v-if="column.unit"> / {{column.unit}}</span></th></tr></thead><tbody>
        <tr><td>均值 x̄</td><td data-testid="stat-mean">{{value(result.mean)}}</td></tr>
        <tr><td>样本标准差 s</td><td data-testid="stat-s">{{value(result.s)}}</td></tr>
        <tr><td>A 类标准不确定度 <span>u<sub>A</sub> = s / √n</span></td><td data-testid="stat-ua">{{result.uA === null ? '—' : String(result.uA)}}</td></tr>
        <tr><td>B 类标准不确定度 u<sub>B</sub></td><td data-testid="stat-ub">{{uB === null ? '—' : String(uB)}}</td></tr>
        <tr class="combined-row"><td>合成标准不确定度 <span>u = √(u<sub>A</sub>² + u<sub>B</sub>²)</span></td><td data-testid="stat-combined">{{formatUncertainty(result.combined,dataset.analysis.uncertainty_digits)}}</td></tr>
      </tbody></table>
      <p v-if="result.reason" class="analysis-message">{{result.reason}}</p>
      <p v-else-if="uB===null" class="analysis-note">请设置误差限与分布后合成。</p>
      <p class="analysis-note">独立、同条件重复测量；A/B 分量按独立处理。</p>

      <div class="rounding-controls"><label for="uncertainty-digits">不确定度有效位数</label><select id="uncertainty-digits" :value="dataset.analysis.uncertainty_digits" @change="emit('digits',Number(($event.target as HTMLSelectElement).value) as 1|2)"><option :value="1">1 位</option><option :value="2">2 位</option></select></div>
      <div class="best-estimate"><span>最佳估计值 <small>x̄ ± u</small></span><output aria-label="最佳估计值">{{estimate}}</output></div>
      <details v-if="bins.length" class="histogram-details"><summary>分布直方图</summary><svg viewBox="0 0 660 210" role="img" aria-label="有效样本分布直方图"><text x="28" y="14">频数</text><path d="M 45 25 V 164 H 620" stroke="#9fb4aa" fill="none"/><text v-for="tick in frequencyScale.ticks" x="36" :y="168-tick/highest*134" text-anchor="end">{{tick}}</text><g v-for="(bin,i) in bins" :key="i"><rect :x="48+i*568/bins.length" :y="164-bin.count/highest*134" :width="Math.max(1,568/bins.length-3)" :height="bin.count/highest*134" fill="#7cb0a0"><title>{{value(bin.low)}} – {{value(bin.high)}}：{{bin.count}}</title></rect></g><text x="45" y="183">{{value(bins[0]!.low)}}</text><text x="620" y="183" text-anchor="end">{{value(bins[bins.length-1]!.high)}}</text><text x="330" y="205" text-anchor="middle">{{column.name}}{{column.unit ? ' / '+column.unit : ''}}</text></svg></details>
    </template>
  </div>
</template>

<style scoped>
.inline-estimate{margin-left:12px;color:#31705b;font-size:16px;font-variant-numeric:tabular-nums;overflow-wrap:anywhere}.analysis-controls{flex-wrap:wrap}
.rounding-controls{margin-top:22px;display:flex;justify-content:flex-end;align-items:center;gap:9px;font-size:11px;color:#82988a}.rounding-controls select{width:70px;padding:5px 8px}
.best-estimate{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:15px 14px;background:#edf5f0;border:1px solid #e2ece5;border-radius:6px;margin:20px 0 17px;font-size:12px;color:#3c715a}.best-estimate small{margin-left:7px;color:#88a08e}.best-estimate output{font-size:16px;font-variant-numeric:tabular-nums;overflow-wrap:anywhere}@media(max-width:760px){.best-estimate{align-items:flex-start;flex-direction:column}.best-estimate output{font-size:14px}}
.statistics-panel{padding:20px;color:#526b60}.analysis-controls{display:flex;align-items:center;gap:12px;margin-bottom:17px;font-size:12px}.analysis-controls select{width:220px;font-size:12px}.sample-count{display:flex;gap:16px;font-size:11px;color:#91a399;margin-bottom:12px}.statistics-table th,.statistics-table td{position:static;padding:11px 14px;height:auto}.statistics-table th{font-size:11px}.statistics-table td{font-size:12px}.statistics-table td:last-child{width:45%;overflow-wrap:anywhere;font-family:Consolas,monospace;font-size:14px}.statistics-table td span{margin-left:8px;font-size:11px;color:#849b8d}.combined-row{background:#f1f7f3}.combined-row td{color:#31705b;font-weight:500}.analysis-note{font-size:10px;color:#8b9f91;line-height:1.7;margin-top:12px}.analysis-message{font-size:12px;color:#9b7c4d;background:#faf7ee;padding:12px;border-radius:5px;margin:12px 0}.grubbs-section{margin-bottom:24px;margin-top:0;border-top:1px solid #e5ede7;padding-top:20px}.grubbs-header{display:flex;align-items:center;gap:9px}.grubbs-header h3{margin-right:auto;font-size:13px;font-weight:500}.grubbs-header label{font-family:Georgia,serif;font-size:15px}.grubbs-header input{width:100px;font-size:11px}.grubbs-header select{width:83px;font-size:11px}.grubbs-numbers{display:flex;gap:40px;margin:19px 0;font-size:12px}.grubbs-numbers strong{margin-left:10px;font-weight:500;font-family:Consolas,monospace}.grubbs-verdict{display:flex;justify-content:space-between;align-items:center;min-height:42px;padding:10px 12px;background:#f2f7f3;border-radius:5px;font-size:12px}.grubbs-verdict.suspected{color:#a38044;background:#faf6eb}.histogram-details{margin-top:22px;border-top:1px solid #e5ede7;padding-top:17px;font-size:12px}.histogram-details summary{cursor:pointer}.histogram-details svg{width:100%;margin-top:20px}.histogram-details text{font-size:10px;fill:#8ca294}@media(max-width:760px){.statistics-panel{padding:16px 12px}.statistics-table td span{display:block;margin-left:0;margin-top:4px}.grubbs-header{flex-wrap:wrap}.grubbs-header h3{width:100%}.grubbs-verdict{gap:8px}.grubbs-numbers{gap:20px}}
</style>
