import { onUnmounted, reactive, watch, type Ref } from 'vue';
import type { Project, Dataset } from './model';
import { resolvePlotAxes } from './plot';
import type { FitResult } from './advanced-model';
export async function calculate<T>(payload:unknown):Promise<T>{
  if(window.labDesktop)return await window.labDesktop.calculate(payload) as T;
  const response=await fetch('/api/calculate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
  const data=await response.json();if(data.error)throw new Error(data.error);if(!response.ok)throw new Error('计算服务不可用');return data.result;
}
export function fitRequest(d:Dataset){
  if(d.kind!=='paired' || !d.fit?.enabled)return null;
  const config={...d.fit,weighting:'ordinary',sigmaColumn:'',rangeMin:null,rangeMax:null,parameters:d.fit.parameters.map(p=>({...p,min:null,max:null}))};
  const axes=resolvePlotAxes(d),xi=d.columns.findIndex(c=>c.id===axes.x),yi=d.columns.findIndex(c=>c.id===axes.y);
  const points=d.rows.flatMap((r,i)=>{
    const x=axes.x==='sequence'?i+1:r.values[xi],y=r.values[yi];
    if(r.excluded || x==null || y==null)return [];
    return [{id:r.id,x,y,}];
  });return {operation:'fit',config,points};
}
export interface FitState {result:FitResult|null;error:string;pending:boolean}
export function useFits(project:Ref<Project>){
  const states=reactive<Record<string,FitState>>({});let writingBack=false;let generation=0;let timer:ReturnType<typeof setTimeout>;
  watch(()=>JSON.stringify([project.value.project.id,project.value.datasets]),()=>{
    if(writingBack)return;
    const version=++generation;clearTimeout(timer);
    for(const key of Object.keys(states))delete states[key];
    for(const d of project.value.datasets)if(d.kind==='paired' && d.fit?.enabled)states[d.id]={result:null,error:'',pending:true};
    timer=setTimeout(async()=>{
      for(const d of project.value.datasets){
        if(version!==generation)return;if(d.kind!=='paired' || !d.fit?.enabled)continue;
        try{const result=await calculate<FitResult>(fitRequest(d));if(version===generation){
          if(!result.manual){writingBack=true;try{d.fit.parameters.forEach((p,i)=>p.value=result.parameters[i]!);}finally{writingBack=false;}}
          states[d.id]={result,error:'',pending:false};
        }}
        catch(e){if(version===generation)states[d.id]={result:null,error:(e as Error).message,pending:false};}
      }
    },350);
  },{immediate:true,flush:'sync'});
  onUnmounted(()=>{generation++;clearTimeout(timer);});return states;
}