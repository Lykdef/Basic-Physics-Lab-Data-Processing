<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue';
import DecimalInput from './DecimalInput.vue';
import type { Project } from './model';
import { defaultPropagation, type PropagationConfig, type PropagationResult } from './advanced-model';
import { calculate, type FitState } from './calculation';
import { autoCorrelation, correlationKey, propagationRequest, resolveInputs, sourceOptions } from './propagation';
import { formatEstimate, formatUncertainty } from './estimate';
const props=defineProps<{project:Project;fits:Record<string,FitState>;valuesOnly?:boolean}>();
const emit=defineEmits<{change:[config:PropagationConfig]}>();
const initial=defaultPropagation(),config=computed(()=>props.project.propagation ?? initial);
const valuesOnly=computed(()=>config.value.variables.some(v=>v.source.startsWith('mean:'))?false:config.value.variables.some(v=>v.source.startsWith('fit:'))?true:!!props.valuesOnly);
const invalidInputs=ref<Record<string,boolean>>({});
const invalid=computed(()=>config.value.variables.some(v=>v.source==='manual' && (invalidInputs.value[v.id+':value'] || (!valuesOnly.value && invalidInputs.value[v.id+':uncertainty']))));
const sources=computed(()=>sourceOptions(props.project));
const inputs=computed(()=>{try{return resolveInputs(config.value,props.project,props.fits,valuesOnly.value);}catch{return null;}});
const pairs=computed(()=>config.value.variables.flatMap((a,i)=>config.value.variables.slice(i+1).map(b=>({a,b,key:correlationKey(a.id,b.id),auto:autoCorrelation(a,b,props.fits)}))));
function update(fn:(v:PropagationConfig)=>void){const next=JSON.parse(JSON.stringify(config.value));fn(next);emit('change',next);}
function field(key:'expression'|'unit',e:Event){update(c=>c[key]=(e.target as HTMLInputElement).value);}
function variable(i:number,key:'symbol'|'source'|'value'|'uncertainty',e:Event){const raw=(e.target as HTMLInputElement).value;
  if(key==='value' || key==='uncertainty'){if(raw==='' || !Number.isFinite(Number(raw)) || (key==='uncertainty' && Number(raw)<0))return;update(c=>c.variables[i]![key]=Number(raw));}
  else update(c=>c.variables[i]![key]=raw);
}
function add(){update(c=>{let i=c.variables.length+1;while(c.variables.some(v=>v.symbol==='x'+i))i++;c.variables.push({id:crypto.randomUUID(),symbol:'x'+i,source:'manual',value:1,uncertainty:0});});}
function remove(id:string){update(c=>{c.variables=c.variables.filter(v=>v.id!==id);for(const key of Object.keys(c.correlations))if(key.split('|').includes(id))delete c.correlations[key];});}
const result=ref<PropagationResult|null>(null),error=ref(''),pending=ref(false);let timer:ReturnType<typeof setTimeout>,generation=0;
watch(()=>JSON.stringify([config.value,props.project.datasets,props.fits,invalid.value,valuesOnly.value]),()=>{
  const version=++generation;clearTimeout(timer);result.value=null;error.value='';pending.value=true;
  timer=setTimeout(async()=>{try{if(invalid.value)throw new Error('请输入有效数值，标准不确定度须为非负数');const r=await calculate<PropagationResult>(propagationRequest(config.value,props.project,props.fits,valuesOnly.value));if(version===generation)result.value=r;}catch(e){if(version===generation)error.value=(e as Error).message;}finally{if(version===generation)pending.value=false;}},400);
},{immediate:true,flush:'sync'});
onUnmounted(()=>{generation++;clearTimeout(timer);});
</script>
<template>
  <section class="advanced-panel propagation-panel">
    <div class="advanced-fields formula-fields"><label>测量模型 · y =<input aria-label="传播公式" :value="config.expression" maxlength="400" @input="field('expression',$event)"/></label><label>结果单位<input aria-label="传播结果单位" :value="config.unit" @input="field('unit',$event)"/></label></div>
    <details class="formula-help"><summary>公式写法</summary><p>例如 4*pi^2*L/T^2。支持 + − * / ^、sqrt、exp、ln、sin、cos、tan、asin、acos、atan；角度用弧度，输入单位需自行统一。</p></details>
    <div class="advanced-table-wrap"><table class="advanced-table"><thead><tr><th>变量</th><th>来源</th><th>最佳估计值</th><th v-if="!valuesOnly">标准不确定度</th><th></th></tr></thead><tbody><tr v-for="(v,i) in config.variables" :key="v.id"><td><input :aria-label="`变量 ${i+1} 符号`" :value="v.symbol" @change="variable(i,'symbol',$event)"/></td><td><select :aria-label="`变量 ${i+1} 来源`" :value="v.source" @change="variable(i,'source',$event)"><option value="manual">手动输入</option><option v-if="v.source!=='manual' && !sources.some(s=>s.id===v.source)" :value="v.source">来源已失效</option><option v-for="s in sources" :key="s.id" :value="s.id">{{s.label}}</option></select></td><td><DecimalInput v-if="v.source==='manual'" :aria-label="`变量 ${i+1} 估计值`" :model-value="v.value" @update:model-value="update(c=>c.variables[i]!.value=$event)" @invalid="invalidInputs[v.id+':value']=$event"/><output v-else>{{inputs?.[i]?.value ?? '—'}}</output></td><td v-if="!valuesOnly"><DecimalInput v-if="v.source==='manual'" nonnegative :aria-label="`变量 ${i+1} 标准不确定度`" :model-value="v.uncertainty" @update:model-value="update(c=>c.variables[i]!.uncertainty=$event)" @invalid="invalidInputs[v.id+':uncertainty']=$event"/><output v-else>{{v.source.startsWith('fit:')?'—':inputs?.[i]?.uncertainty ?? '—'}}</output></td><td><button :aria-label="`删除输入变量 ${i+1}`" :disabled="config.variables.length<=1" @click="remove(v.id)">删除</button></td></tr></tbody></table></div>
    <button :disabled="config.variables.length>=16" @click="add">＋ 添加输入变量</button>
    <details v-if="!valuesOnly && pairs.length" class="correlations"><summary>相关系数</summary><p class="calculation-note">未设置的输入按独立量处理；拟合参数仅引用数值。</p><div class="advanced-fields"><label v-for="pair in pairs" :key="pair.key">{{pair.a.symbol}} ↔ {{pair.b.symbol}}<input type="number" min="-1" max="1" step="0.01" :aria-label="`相关系数 ${pair.a.symbol} ${pair.b.symbol}`" :disabled="pair.auto!==null" :value="pair.auto ?? config.correlations[pair.key] ?? 0" @input="Number.isFinite(Number(($event.target as HTMLInputElement).value)) && update(c=>c.correlations[pair.key]=Math.max(-1,Math.min(1,Number(($event.target as HTMLInputElement).value))))"/></label></div></details>
    <div v-if="!valuesOnly" class="advanced-fields"><label>不确定度有效数字<select aria-label="传播不确定度有效数字" :value="config.digits" @change="update(c=>c.digits=Number(($event.target as HTMLSelectElement).value) as 1|2)"><option :value="1">1 位</option><option :value="2">2 位</option></select></label><label>包含因子 k<input type="number" min="0.01" step="any" :value="config.k" aria-label="包含因子" @input="Number(($event.target as HTMLInputElement).value)>0 && update(c=>c.k=Number(($event.target as HTMLInputElement).value))"/></label></div>
    <p v-if="pending" role="status">计算中…</p><p v-if="error" class="calculation-error" role="alert">{{error}}</p>
    <div v-if="result && valuesOnly" class="propagation-result"><span>计算结果</span><output aria-label="科学计算结果">{{Number(result.value.toPrecision(10))}} {{config.unit}}</output></div><template v-if="result && !valuesOnly"><div class="propagation-result"><span>y ± u</span><output aria-label="传播最佳估计值">{{formatEstimate(result.value,result.uncertainty,config.unit,config.digits)}}</output><span>相对标准不确定度：{{result.relative===null?'—':(result.relative*100).toPrecision(6)+'%'}}</span><span>扩展不确定度 U（k = {{config.k}}）：{{formatUncertainty(result.expanded,config.digits)}} {{config.unit}}</span></div>
    <p class="calculation-note">一阶传播：u² = Σ cᵢ²uᵢ² + 2Σ cᵢcⱼuᵢuⱼrᵢⱼ</p>
    <div class="advanced-table-wrap"><table class="advanced-table" aria-label="不确定度预算"><thead><tr><th>输入</th><th>偏导数</th><th>灵敏系数 cᵢ</th><th>标准不确定度 uᵢ</th><th>方差贡献</th></tr></thead><tbody><tr v-for="v in result.budget"><th>{{v.symbol}}</th><td>{{v.derivative}}</td><td>{{v.sensitivity}}</td><td>{{v.uncertainty}}</td><td>{{v.contribution}}</td></tr><tr v-for="v in result.cross"><th>{{v.left}} ↔ {{v.right}}</th><td colspan="3">r = {{v.correlation}}</td><td>{{v.contribution}}</td></tr></tbody></table></div>
    </template>
  </section>
</template>
