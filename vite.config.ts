import { defineConfig } from 'vite';
import { createRequire } from 'node:module';
const bridge=createRequire(import.meta.url)('./compute/bridge.cjs');
import vue from '@vitejs/plugin-vue';
export default defineConfig({ plugins: [vue(), {name:'local-compute',configureServer(server){server.middlewares.use(bridge.middleware);server.httpServer?.once('close',()=>bridge.stop());},configurePreviewServer(server){server.middlewares.use(bridge.middleware);server.httpServer?.once('close',()=>bridge.stop());}}], base: './', server: { port: 5173, strictPort: true } });
