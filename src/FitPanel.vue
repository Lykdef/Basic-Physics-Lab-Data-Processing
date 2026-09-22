<script setup lang="ts">
import { niceScale } from './scale';
import { computed } from 'vue';
import type { Dataset } from './model';
import { defaultFit, models, parameterNames, type FitConfig } from './advanced-model';
import type { FitState } from './calculation';
const props=defineProps<{dataset:Dataset;state?:FitState}>();
const emit=defineEmits<{change:[value:FitConfig]}>();
const config=computed(()=>props.dataset.fit ?? defaultFit());
const names=computed(()=>parameterNames(config.value.model,config.value.degree));
function change(key:keyof FitConfig,value:unknown){const next=structuredClone(JSON.parse(JSON.stringify(config.value)));next[key]=value;
  if(key==='model' || key==='degree')next.parameters=parameterNames(next.model,next.degree).map((_,i)=>({value:next.model==='exponential'?[1,-1,0][i]:i===0?1:0,min:null,max:null,fixed:false}));emit('change',next);}
function param(i:number,key:'value'|'min'|'max'|'fixed',event:Event){const el=event.target as HTMLInputElement;const next=JSON.parse(JSON.stringify(config.value)) as FitConfig;
  const value=key==='fixed'?el.checked:el.value===''?null:Number(el.value);if(key==='value' && value===null)return;if(typeof value==='number' && !Number.isFinite(value))return;
  Object.assign(next.parameters[i]!,{[key]:value});emit('change',next);}
const residualScale=computed(()=>{const r=props.state?.result?.residuals ?? [];const max=Math.max(...r.map(p=>Math.abs(p.residual)),1e-15);return {x:niceScale(Math.min(...r.map(p=>p.x),0),Math.max(...r.map(p=>p.x),1)),y:niceScale(-max,max,4)};});
const residuals=computed(()=>{const scale=residualScale.value;return (props.state?.result?.residuals ?? []).map(p=>({...p,px:76+(p.x-scale.x.min)/(scale.x.max-scale.x.min)*632,py:105-(p.residual-scale.y.min)/(scale.y.max-scale.y.min)*80}));});
const n=(event:Event)=>{const v=(event.target as HTMLInputElement).value;return v===''?null:Number(v);};
</script>
<template>
  <section class="advanced-panel fit-panel">
    <label class="check-label"><input type="checkbox" :checked="config.enabled" @change="change('enabled',($event.target as HTMLInputElement).checked)"/>曲线拟合</label>
    <template v-if="config.enabled">
      <div class="advanced-fields">
        <label>模型<select aria-label="拟合模型" :value="config.model" @change="change('model',($event.target as HTMLSelectElement).value)"><option v-for="(label,key) in models" :value="key">{{label}}</option></select></label>
        <label v-if="config.model==='polynomial'">次数<input aria-label="多项式次数" type="number" min="1" max="6" :value="config.degree" @change="change('degree',Math.min(6,Math.max(1,n($event) || 2)))"/></label>
        <label>参数<select aria-label="参数模式" :value="config.mode" @change="change('mode',($event.target as HTMLSelectElement).value)"><option value="auto">自动拟合</option><option value="manual">手动调节</option></select></label>
      </div>
      <div class="advanced-table-wrap"><table class="advanced-table"><thead><tr><th>参数</th><th>值</th><th>固定</th></tr></thead><tbody><tr v-for="(p,i) in config.parameters" :key="i"><th>{{names[i]}}</th><td><input type="number" step="any" :aria-label="`参数 ${names[i]} 值`" :value="p.value" @input="param(i,'value',$event)"/></td><td><input type="checkbox" :aria-label="`固定参数 ${names[i]}`" :checked="p.fixed" @change="param(i,'fixed',$event)"/></td></tr></tbody></table></div>
      <p v-if="state?.pending" role="status">计算中…</p><p v-if="state?.error" class="calculation-error" role="alert">{{state.error}}</p>
      <template v-if="state?.result"><div class="fit-metrics"><span>{{state.result.manual?'手动曲线':'拟合结果'}}</span><span>n = {{state.result.n}}</span><span>R² = {{state.result.r2?.toPrecision(6) ?? '—'}}</span><span>RMSE = {{state.result.rmse.toPrecision(6)}}</span></div>
      <div class="residual-plot"><span>残差 · y − ŷ</span><svg viewBox="0 0 760 140" role="img" aria-label="拟合残差图"><path d="M76 20 V105 H708 M76 65 H708" fill="none" stroke="#b8ccc7"/><g v-for="value in residualScale.y.ticks"><text x="66" :y="109-(value-residualScale.y.min)/(residualScale.y.max-residualScale.y.min)*80" text-anchor="end">{{Number(value.toPrecision(6))}}</text></g><g v-for="value in residualScale.x.ticks"><text :x="76+(value-residualScale.x.min)/(residualScale.x.max-residualScale.x.min)*632" y="124" text-anchor="middle">{{Number(value.toPrecision(6))}}</text></g><circle v-for="p in residuals" :key="p.id" :cx="p.px" :cy="p.py" r="3" fill="#218477"><title>x={{p.x}}；残差={{p.residual}}</title></circle></svg></div>
      </template>
    </template>
  </section>
</template>