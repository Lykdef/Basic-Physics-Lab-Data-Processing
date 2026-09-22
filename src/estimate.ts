// Decimal integer rounding: uncertainty upwards, mean half to even.
function decimal(value:number) {
  const [mantissa,exponent]=Math.abs(value).toExponential().split('e');
  const digits=mantissa!.replace('.','');
  return {coefficient:BigInt(digits),power:Number(exponent)-digits.length+1,exponent:Number(exponent)};
}
function quantize(value:number,place:number,mode:'up'|'even'):bigint {
  const d=decimal(value),shift=d.power-place;let q:bigint;
  if(shift>=0) q=d.coefficient*10n**BigInt(shift);
  else {const divisor=10n**BigInt(-shift);q=d.coefficient/divisor;const rest=d.coefficient%divisor;
    if(mode==='up' ? rest>0n : rest*2n>divisor || (rest*2n===divisor && q%2n!==0n)) q++;
  }
  return value<0?-q:q;
}
function fixed(coefficient:bigint,place:number):string {
  const negative=coefficient<0n, digits=(negative?-coefficient:coefficient).toString();
  if(place>=0) return (negative?'-':'')+digits+'0'.repeat(place);
  const padded=digits.padStart(1-place,'0'),split=padded.length+place;
  return (negative?'-':'')+padded.slice(0,split)+'.'+padded.slice(split);
}
function roundedUncertainty(u:number,digits:1|2) {
  let place=decimal(u).exponent-digits+1;let coefficient=quantize(u,place,'up');
  if(coefficient.toString().length>digits) {coefficient/=10n;place++;}
  return {coefficient,place};
}
export function formatUncertainty(u:number|null,digits:1|2=1):string {
  if(u===null || !Number.isFinite(u) || u<0) return '—';if(u===0) return '0';
  const r=roundedUncertainty(u,digits),exponent=r.place+r.coefficient.toString().length-1;
  return r.place < -8 || exponent > 8 ? `${fixed(r.coefficient,r.place-exponent)} × 10^${exponent}` : fixed(r.coefficient,r.place);
}
export function formatAlignedMean(mean:number|null,u:number|null,digits:1|2=1):string {
  if(mean===null || !Number.isFinite(mean)) return '—';
  if(u===null || u<=0 || !Number.isFinite(u)) return String(mean);
  const r=roundedUncertainty(u,digits);return fixed(quantize(mean,r.place,'even'),r.place);
}
export function formatEstimate(mean:number|null,u:number|null,unit:string,digits:1|2=1):string {
  if(mean===null || u===null || !Number.isFinite(mean) || !Number.isFinite(u) || u<0) return '—';
  const suffix=unit?` ${unit}`:'';if(u===0) return `(${mean} ± 0)${suffix}`;
  const r=roundedUncertainty(u,digits),m=quantize(mean,r.place,'even');
  if(r.place < -8 || r.place > 8 || Math.abs(mean)>=1e12) {
    const exponent=r.place+r.coefficient.toString().length-1;
    return `(${fixed(m,r.place-exponent)} ± ${fixed(r.coefficient,r.place-exponent)}) × 10^${exponent}${suffix}`;
  }
  return `(${fixed(m,r.place)} ± ${fixed(r.coefficient,r.place)})${suffix}`;
}
