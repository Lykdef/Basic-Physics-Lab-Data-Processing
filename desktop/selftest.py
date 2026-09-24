"""Explicit hidden-window integration checks; no hooks in normal application use."""
import json
import threading


def install(window, api, args):
    finished = threading.Event()

    def report(result):
        if finished.is_set():
            return
        if result.get('ok') and not args.verify_recovery:
            image = args.data_dir/'plot.png'
            if not image.exists() or not image.read_bytes().startswith(b'\x89PNG\r\n\x1a\n'):
                result = {'ok': False, 'error': '图像导出失败'}
        finished.set()
        args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        threading.Timer(.2, window.destroy).start()

    window.expose(report)
    saved = str(args.data_dir/'roundtrip.json')
    window.create_file_dialog = lambda *a, **k: (str(args.data_dir/'plot.png') if k.get('save_filename', '').endswith('.png') else saved,)
    script = r"""
    (async()=>{
      const wait=async(fn)=>{for(let i=0;i<200;i++){if(fn())return;await new Promise(r=>setTimeout(r,100));}throw Error('等待界面超时');};
      const check=(ok,message)=>{if(!ok)throw Error(message);};
      await wait(()=>window.labDesktop && document.querySelector('.measure-table input'));
      check(!window.require,'Node 不应暴露');
      const first=document.querySelector('.measure-table input');
      if(VERIFY_RECOVERY){check(first.value==='12.34','重启未恢复数值');await window.pywebview.api.report({ok:true,recovery:true});return;}
      first.value='12.34';first.dispatchEvent(new Event('change',{bubbles:true}));
      await new Promise(r=>setTimeout(r,500));
      const state=JSON.parse(await window.pywebview.api.load_workspace());check(state.projects[0].datasets[0].rows[0].values[0]===12.34,'自动保存失败');
      const project=JSON.stringify(state.projects[0]);check(await window.labDesktop.saveProject('验证',project),'原生保存失败');check(await window.labDesktop.openProject()===project,'原生打开不一致');
      const result=await window.labDesktop.calculate({operation:'propagate',expression:'x^2',variables:[{symbol:'x',value:3,uncertainty:.1}],k:2});check(result.value===9 && Math.abs(result.uncertainty-.6)<1e-12,'传播计算失败');
      let rejected=false;try{await window.labDesktop.calculate({operation:'propagate',expression:'1/x',variables:[{symbol:'x',value:0,uncertainty:.1}]});}catch(e){rejected=true;check(!!e.message,'错误消息丢失');}check(rejected,'非法公式未拒绝');
      const button=text=>[...document.querySelectorAll('button')].find(b=>b.textContent.trim()===text);
      button('伏安法测电阻').click();await new Promise(r=>setTimeout(r,200));button('数据预览').click();await wait(()=>document.querySelector('.fit-panel input[type=checkbox]'));document.querySelector('.fit-panel input[type=checkbox]').click();await wait(()=>document.querySelector('.fit-metrics'));check(document.querySelector('.fit-metrics').textContent.includes('拟合结果'),'拟合失败');
      button('导出图像').click();await new Promise(r=>setTimeout(r,500));await wait(()=>!button('导出图像').disabled);
      button('长度的重复测量').click();button('数据表格').click();await new Promise(r=>setTimeout(r,500));
      await window.pywebview.api.report({ok:true,fit:true,propagate:true,files:true,persistence:true});
    })().catch(e=>window.pywebview.api.report({ok:false,error:String(e),stack:e.stack}));
    """.replace('VERIFY_RECOVERY', 'true' if args.verify_recovery else 'false')

    def loaded():
        window.run_js(script)

    window.events.loaded += loaded
    timeout = threading.Timer(75, lambda: report({'ok': False, 'error': '集成测试超时'}))
    timeout.daemon = True
    timeout.start()
    window.events.closed += lambda: timeout.cancel()
