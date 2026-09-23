import { createApp } from 'vue';
import App from './App.vue';
import './style.css';
import './minimal.css';
import './advanced.css';
import { initializeDesktop } from './desktop';
initializeDesktop().then(()=>createApp(App).mount('#app')).catch(error=>{
  document.getElementById('app')!.textContent='启动失败：'+String(error?.message ?? error)+'。原有项目未被覆盖，请重新启动或导入备份。';
});
