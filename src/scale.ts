/** Linear axes use 1, 2, 5 × 10^n steps, never arbitrary fractions of the range. */
export function niceStep(span:number,intervals=6){
  const raw=span/intervals;
  if(!Number.isFinite(raw) || raw<=0)return 1;
  const magnitude=10**Math.floor(Math.log10(raw));
  const fraction=raw/magnitude;
  return (fraction<=1?1:fraction<=2?2:fraction<=5?5:10)*magnitude;
}
export function niceScale(min:number,max:number,intervals=6,integer=false){
  if(min===max){const pad=Math.abs(min)*.1 || 1;min-=pad;max+=pad;}
  const step=Math.max(integer?1:0,niceStep(max-min,intervals));
  const first=Math.floor(min/step+1e-10),last=Math.ceil(max/step-1e-10);
  const ticks=Array.from({length:Math.min(100,Math.max(1,last-first+1))},(_,i)=>Number(((first+i)*step).toPrecision(14)));
  return {min:ticks[0]!,max:ticks.at(-1)!,step,ticks};
}
