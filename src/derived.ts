import type {Dataset} from './model';

type Evaluate = (values:Record<string,number|null>)=>number|null;
const functions:Record<string,(x:number)=>number>={sqrt:Math.sqrt,exp:Math.exp,ln:Math.log,log:Math.log,sin:Math.sin,cos:Math.cos,tan:Math.tan,asin:Math.asin,acos:Math.acos,atan:Math.atan};
/** Small expression parser: never executes JavaScript or accesses object properties. */
export function compileDerived(expression:string,symbols:string[]):Evaluate {
  if(!expression.trim() || expression.length>200)throw new Error('公式需要 1–200 个字符');
  const tokens=expression.match(/(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?|[A-Za-z][A-Za-z0-9_]*|\*\*|[+\-*/^()]|\S/g) ?? [];
  if(tokens.length>100)throw new Error('公式过于复杂');
  let index=0;
  const binary=(a:Evaluate,b:Evaluate,op:string):Evaluate=>values=>{
    const x=a(values),y=b(values);if(x===null || y===null)return null;
    const n=op==='+'?x+y:op==='-'?x-y:op==='*'?x*y:op==='/'?x/y:x**y;
    if(!Number.isFinite(n))throw new Error('除零或超出定义域');return n;
  };
  function atom():Evaluate {
    const token=tokens[index++];
    if(token==='('){const node=sum();if(tokens[index++]!==')')throw new Error('括号不匹配');return node;}
    if(token && /^(?:\d|\.)/.test(token)){const n=Number(token);if(!Number.isFinite(n))throw new Error('常数无效');return ()=>n;}
    if(token && symbols.includes(token))return values=>values[token] ?? null;
    if(token==='pi')return ()=>Math.PI;if(token==='e')return ()=>Math.E;
    if(token && Object.hasOwn(functions,token)){
      if(tokens[index++]!=='(')throw new Error('函数需要括号');const node=sum();if(tokens[index++]!==')')throw new Error('括号不匹配');
      return values=>{const x=node(values);if(x===null)return null;const n=functions[token]!(x);if(!Number.isFinite(n))throw new Error('超出函数定义域');return n;};
    }
    throw new Error(`未知变量或符号：${token ?? ''}`);
  }
  function power():Evaluate {let node=atom();if(['^','**'].includes(tokens[index] ?? '')){index++;node=binary(node,unary(),'^');}return node;}
  function unary():Evaluate {if(tokens[index]==='+' || tokens[index]==='-'){const sign=tokens[index++],node=unary();return values=>{const n=node(values);return n===null?null:sign==='-'?-n:n;};}return power();}
  function product():Evaluate {let node=unary();while(['*','/'].includes(tokens[index] ?? '')){const op=tokens[index++]!;node=binary(node,unary(),op);}return node;}
  function sum():Evaluate {let node=product();while(['+','-'].includes(tokens[index] ?? '')){const op=tokens[index++]!;node=binary(node,product(),op);}return node;}
  const result=sum();if(index!==tokens.length)throw new Error('公式格式错误');return result;
}

export function axisInputs(dataset:Dataset, selectedColumn=0) {
  const columns=[...dataset.columns,...(dataset.derived ?? [])];
  const x=columns.find(c=>c.id===dataset.plot_axes?.x) ?? dataset.columns[0]!;
  const y=columns.find(c=>c.id===dataset.plot_axes?.y) ?? dataset.columns[dataset.kind==='paired' && dataset.columns.length>1?1:selectedColumn] ?? dataset.columns[0]!;
  const expression=(c:typeof x)=>'expression' in c?String(c.expression):c.symbol;
  return dataset.axis_inputs ?? {x:{expression:dataset.kind==='repeated' || dataset.plot_axes?.x==='sequence'?'sequence':expression(x),unit:x.unit},y:{expression:expression(y),unit:y.unit}};
}
export function derivedDataset(dataset:Dataset,selectedColumn=0) {
  if(!dataset.axis_inputs && !dataset.derived?.length)return {dataset,errors:[] as string[]};
  const inputs=axisInputs(dataset,selectedColumn),errors:string[]=[];
  const axes=dataset.kind==='repeated'?['y'] as const:['x','y'] as const;
  const columns=axes.map(axis=>({id:'__plot_'+axis,name:inputs[axis].expression==='sequence'?'测量序号':inputs[axis].expression,display_symbol:inputs[axis].expression,symbol:axis==='x'?'plotX':'plotY',unit:inputs[axis].expression==='sequence'?'':inputs[axis].unit,precision:6}));
  const evaluators=axes.map(axis=>{if(inputs[axis].expression==='sequence' && axis==='x')return null;try{return compileDerived(inputs[axis].expression,dataset.columns.map(c=>c.symbol));}catch(e){errors.push(`${axis}：${(e as Error).message}`);return null;}});
  const rows=dataset.rows.map((row,i)=>{
    const values=Object.fromEntries(dataset.columns.map((c,j)=>[c.symbol,row.values[j] ?? null]));
    const extra=evaluators.map((evaluate,j)=>{if(axes[j]==='x' && inputs.x.expression==='sequence')return i+1;try{return evaluate?.(values) ?? null;}catch(e){if(!row.excluded && errors.length<8)errors.push(`第 ${i+1} 行 ${axes[j]}：${(e as Error).message}`);return null;}});
    return {...row,values:[...row.values,...extra]};
  });
  return {dataset:{...dataset,axis_inputs:undefined,derived:undefined,plot_axes:{x:dataset.kind==='repeated' || inputs.x.expression==='sequence'?'sequence':'__plot_x',y:'__plot_y'},columns:[...dataset.columns,...columns],rows},errors};
}
