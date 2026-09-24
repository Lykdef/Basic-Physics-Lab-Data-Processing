export async function initializeDesktop(){
  if(new URLSearchParams(location.search).get('desktop')!=='pywebview')return;
  if(!window.pywebview?.api)await new Promise<void>((resolve,reject)=>{
    const timer=setTimeout(()=>reject(new Error('桌面接口启动超时，请重新启动应用')),15000);
    window.addEventListener('pywebviewready',()=>{clearTimeout(timer);resolve();},{once:true});
  });
  const api=window.pywebview!.api;
  let queue=Promise.resolve();
  window.labDesktop={saveImage:(name,content)=>api.save_image(name,content),calculate:payload=>api.calculate(payload),openProject:()=>api.open_project(),saveProject:(name,content)=>api.save_project(name,content),
    saveWorkspace:content=>{const job=queue.catch(()=>{}).then(()=>api.save_workspace(content)).then(()=>{});queue=job;return job;}};
  window.labInitialWorkspace=await api.load_workspace();
}
