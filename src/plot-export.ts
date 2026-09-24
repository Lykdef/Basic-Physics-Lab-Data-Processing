import type {Dataset} from './model';
import type {FitResult} from './advanced-model';
import {resolvePlotAxes} from './plot';
import {mathParts} from './math-label';
export interface ExportOptions {title?:string;table?:boolean;formula?:boolean;r2?:boolean;dataset?:Dataset;fit?:FitResult}
export function fitFormula(dataset:Dataset, fit:FitResult) {
  const p=fit.parameters.map(v=>`(${Number(v.toPrecision(7))})`);
  const model=dataset.fit?.model;
  const expr=model==='origin'?`${p[0]}·x`:model==='polynomial'?p.map((v,i)=>i===0?v:`${v}·x^{${i}}`).join(' + '):model==='exponential'?`${p[0]}·exp(${p[1]}·x) + ${p[2]}`:model==='power'?`${p[0]}·x^{${Number(fit.parameters[1]!.toPrecision(7))}}`:model==='logarithmic'?`${p[0]}·ln(x) + ${p[1]}`:`${p[0]}·x + ${p[1]}`;
  const axes=resolvePlotAxes(dataset);
  const label=(id:string)=>{const c=dataset.columns.find(c=>c.id===id);return c?(c.display_symbol || c.symbol):'n';};
  return `${fit.manual?'手动曲线':'拟合公式'}：${label(axes.y)} = ${expr.replace(/\bx\b/g,()=>label(axes.x))}`;
}
/** Export the displayed plot with its computed styles, labels and white background. */
export async function exportPlotPng(source: SVGSVGElement, name: string, ylabel: string, options: ExportOptions = {}) {
  await document.fonts.ready;
  const copy = source.cloneNode(true) as SVGSVGElement;
  const originals = [source, ...source.querySelectorAll('*')];
  const copies = [copy, ...copy.querySelectorAll('*')];
  const properties = ['fill', 'stroke', 'stroke-width', 'stroke-dasharray', 'opacity', 'font-family', 'font-size', 'font-weight', 'text-anchor', 'paint-order', 'stroke-linejoin'];
  originals.forEach((element, i) => {
    const style = getComputedStyle(element);
    for (const property of properties) (copies[i] as SVGElement).style.setProperty(property, style.getPropertyValue(property));
  });
  copy.setAttribute('x', '0');
  const top=options.title?.trim()?72:36;
  copy.setAttribute('y', String(top));
  copy.setAttribute('width', '760');
  copy.setAttribute('height', '260');
  const ns = 'http://www.w3.org/2000/svg';
  const svg = document.createElementNS(ns, 'svg');
  svg.setAttribute('width', '760');
  const addText=(value:string,x:number,y:number,size=12,anchor='start')=>{
    const text=document.createElementNS(ns,'text');
    for(const [key,val] of Object.entries({x:String(x),y:String(y),'font-size':String(size),'font-family':'Microsoft YaHei, sans-serif',fill:'#29483f','text-anchor':anchor}))text.setAttribute(key,val);
    for(const part of mathParts(value)){
      const span=document.createElementNS(ns,'tspan');span.textContent=part.text;
      if(part.kind!=='plain'){span.setAttribute('baseline-shift',part.kind==='sup'?'super':'sub');span.setAttribute('font-size','75%');}
      text.append(span);
    }
    svg.append(text);return text;
  };
  if(options.title?.trim()){
    const heading=addText(options.title.trim(),380,26,18,'middle');
    if(options.title.length>40){heading.setAttribute('textLength','680');heading.setAttribute('lengthAdjust','spacingAndGlyphs');}
  }
  addText(ylabel,76,top-9,14);
  svg.append(copy);
  let height=top+260;
  if(options.dataset?.kind==='paired' && (options.formula || options.r2)){
    if(!options.fit)throw new Error('请等待拟合完成，或取消导出拟合信息');
    if(options.formula){
      const formula=fitFormula(options.dataset,options.fit);
      // Wrap long polynomial formulas between terms.
      const terms=formula.split(' + ');let line='';
      for(const term of terms){if(line.length+term.length>75){addText(line,76,height+18);height+=24;line='+ '+term;}else line+=(line?' + ':'')+term;}
      addText(line,76,height+18);height+=28;
    }
    if(options.r2){addText(`R^{2} = ${options.fit.r2===null?'—（不可定义）':Number(options.fit.r2.toPrecision(7))}`,76,height+18);height+=28;}
  }
  if(options.table && options.dataset){
    const d=options.dataset, chunkSize=8;
    const blocks=Math.ceil(d.rows.length/chunkSize);
    const tableHeight=blocks*((d.columns.length+1)*28+18)+36;
    if((height+tableHeight)*3>16000)throw new Error('源数据过多，超出单张图像尺寸；请减少数据或取消源数据表格');
    addText('源数据（* 为已排除，— 为缺失）',40,height+20);height+=36;
    for(let start=0;start<d.rows.length;start+=chunkSize){
      const rows=d.rows.slice(start,start+chunkSize);
      const labels=['测量序号',...d.columns.map(c=>`${c.display_symbol || c.symbol}${c.unit?' / '+c.unit:''}`)];
      labels.forEach((label,ci)=>{
        const values=[label,...rows.map((r,i)=>ci===0?`${start+i+1}${r.excluded?'*':''}`:r.values[ci-1]===null?'—':String(r.values[ci-1]))];
        values.forEach((value,j)=>{
          const x=j===0?40:200+(j-1)*65, width=j===0?160:65;
          const rect=document.createElementNS(ns,'rect');
          for(const [key,val] of Object.entries({x:String(x),y:String(height),width:String(width),height:'28',fill:j===0 || ci===0?'#f0f5f3':'white',stroke:'#dce6e1'}))rect.setAttribute(key,val);
          svg.append(rect);
          const text=addText(value,x+width/2,height+18,11,'middle');
          if(value.length>(j===0?18:9)){text.setAttribute('textLength',String(width-10));text.setAttribute('lengthAdjust','spacingAndGlyphs');}
        });height+=28;
      });height+=18;
    }
  }
  svg.setAttribute('height',String(height));
  svg.setAttribute('viewBox',`0 0 760 ${height}`);
  const url = URL.createObjectURL(new Blob([new XMLSerializer().serializeToString(svg)], {type: 'image/svg+xml;charset=utf-8'}));
  try {
    const image = new Image();
    image.src = url;
    await image.decode();
    const canvas = document.createElement('canvas');
    canvas.width = 2280;
    canvas.height = height * 3;
    const context = canvas.getContext('2d');
    if (!context) throw new Error('无法创建图像');
    context.fillStyle = '#ffffff';
    context.fillRect(0, 0, canvas.width, canvas.height);
    context.drawImage(image, 0, 0, canvas.width, canvas.height);
    const data = canvas.toDataURL('image/png');
    const filename = name.replace(/[<>:"/\\|?*\x00-\x1f]/g, '_').slice(0, 80) || '数据预览';
    if (window.labDesktop?.saveImage) {
      await window.labDesktop.saveImage(filename, data.split(',')[1]!);
    } else {
      const link = document.createElement('a');
      link.href = data;
      link.download = `${filename}.png`;
      link.click();
    }
  } finally {
    URL.revokeObjectURL(url);
  }
}
