const {spawn}=require('node:child_process');
const path=require('node:path');
const readline=require('node:readline');
const fs=require('node:fs');
let child=null,seq=0;
const pending=new Map();
function stop(message='计算进程已停止') {const process=child;child=null;process?.kill();for(const p of pending.values()){clearTimeout(p.timer);p.reject(new Error(message));}pending.clear();}
function start(){
  if(child)return;
  const bundledPython=path.join(__dirname,'../runtime/python/python.exe');
  const executable=fs.existsSync(bundledPython)?bundledPython:(global.process.env.PHYSICAL_LAB_PYTHON || 'python');
  const process=spawn(executable,['-u',path.join(__dirname,'core.py')],{windowsHide:true,stdio:['pipe','pipe','pipe'],env:{...global.process.env,PYTHONIOENCODING:'utf-8'}});child=process;
  let errors='';process.stderr.on('data',b=>{errors=(errors+b.toString()).slice(-2000);});
  process.on('error',()=>{if(child===process)stop('无法启动 Python，请按使用说明安装计算依赖');});
  process.on('exit',()=>{if(child===process)stop(errors.includes('ModuleNotFoundError')?'缺少计算依赖，请运行 npm run setup:compute':'计算进程意外退出');});
  readline.createInterface({input:process.stdout}).on('line',line=>{try{const msg=JSON.parse(line),p=pending.get(msg.id);if(!p)return;pending.delete(msg.id);clearTimeout(p.timer);msg.error?p.reject(new Error(msg.error)):p.resolve(msg.result);}catch{stop('计算结果格式错误');}});
}
function calculate(payload){
  const raw=JSON.stringify(payload);if(raw.length>1_800_000)return Promise.reject(new Error('计算请求过大'));
  if(!['fit','propagate'].includes(payload?.operation))return Promise.reject(new Error('未知计算类型'));
  start();const id=++seq;
  return new Promise((resolve,reject)=>{const timer=setTimeout(()=>stop('计算超时，请简化模型或调整初值'),20000);pending.set(id,{resolve,reject,timer});child.stdin.write(JSON.stringify({id,payload})+'\n',error=>{if(error)stop('无法发送计算请求');});});
}
function middleware(req,res,next){
  if(req.url!=='/api/calculate')return next();
  if(req.method!=='POST' || !req.headers['content-type']?.startsWith('application/json') || (req.headers.origin && req.headers.origin!==`http://${req.headers.host}`)){res.statusCode=403;res.end('Forbidden');return;}
  let body='';req.on('data',b=>{body+=b;if(body.length>1_800_000)req.destroy();});
  req.on('end',async()=>{res.setHeader('Content-Type','application/json');try{const result=await calculate(JSON.parse(body));res.end(JSON.stringify({result}));}catch(e){res.statusCode=400;res.end(JSON.stringify({error:e.message}));}});
}
module.exports={calculate,stop,middleware};
