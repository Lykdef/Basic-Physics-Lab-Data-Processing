import { standardUncertaintyB, type Project } from './model';
import { evaluateStatistics } from './statistics';
import type { PropagationConfig } from './advanced-model';
import type { FitState } from './calculation';
export function sourceOptions(project:Project){return project.datasets.flatMap(d=>[
  ...(d.kind==='repeated'?d.columns.map(c=>({id:`mean:${d.id}:${c.id}`,label:`${d.name} · ${c.symbol} 均值${c.unit?' / '+c.unit:''}`})):[]),
  ...(d.fit?.enabled ? d.fit.parameters.map((_,i)=>({id:`fit:${d.id}:${i}`,label:`${d.name} · 拟合参数 ${d.fit!.model==='polynomial'?'a'+i:['a','b','c'][i]}`})):[])
]);}
export function resolveInputs(config:PropagationConfig,project:Project,fits:Record<string,FitState>){
  return config.variables.map(v=>{
    if(v.source==='manual')return {...v};
    const [kind,did,key]=v.source.split(':'),d=project.datasets.find(d=>d.id===did);
    if(!d)throw new Error(`${v.symbol} 的数据组已删除，请重新选择来源`);
    if(kind==='fit'){
      const state=fits[d.id],i=Number(key);
      if(d.kind!=='paired' || !d.fit?.enabled || d.fit.mode==='manual')throw new Error(`${v.symbol} 需要自动拟合结果`);
      if(state?.pending)throw new Error('等待拟合完成…');
      if(!state?.result?.standard_errors || !state.result.covariance || state.result.parameters[i]===undefined)throw new Error(`${v.symbol} 的拟合参数不确定度不可用`);
      return {...v,value:state.result.parameters[i]!,uncertainty:state.result.standard_errors[i]!};
    }
    if(kind!=='mean' || d.kind!=='repeated')throw new Error(`${v.symbol} 的来源不再是重复测量`);
    const ci=d.columns.findIndex(c=>c.id===key);if(ci<0)throw new Error(`${v.symbol} 的变量已删除`);
    const b=standardUncertaintyB(d.instrument.b_sources[key!] ?? {delta:null,distribution:d.instrument.distribution});
    const stats=evaluateStatistics(d,ci,d.analysis.alpha,b);
    if(stats.mean===null || stats.combined===null)throw new Error(`${v.symbol} 需要至少两次有效测量及已设置的 B 类不确定度`);
    return {...v,value:stats.mean,uncertainty:stats.combined};
  });
}
export const correlationKey=(a:string,b:string)=>[a,b].sort().join('|');
export function autoCorrelation(a:PropagationConfig['variables'][number],b:PropagationConfig['variables'][number],fits:Record<string,FitState>):number|null{
  if(a.source!=='manual' && a.source===b.source)return 1;
  const [ak,ad,ai]=a.source.split(':'),[bk,bd,bi]=b.source.split(':');
  if(ak==='fit' && bk==='fit' && ad===bd){const r=fits[ad!]?.result,cov=r?.covariance?.[Number(ai)]?.[Number(bi)],u=r?.standard_errors;if(cov!==undefined && u){const divisor=u[Number(ai)]!*u[Number(bi)]!;return divisor===0?0:Math.max(-1,Math.min(1,cov/divisor));}}
  return null;
}
export function propagationRequest(config:PropagationConfig,project:Project,fits:Record<string,FitState>){
  const variables=resolveInputs(config,project,fits);
  const correlation=variables.map((a,i)=>variables.map((b,j)=>i===j?1:autoCorrelation(a,b,fits) ?? config.correlations[correlationKey(a.id,b.id)] ?? 0));
  return {operation:'propagate',expression:config.expression,variables,correlation,k:config.k};
}
