import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import { fileURLToPath, URL } from 'node:url';

// 提线 (Marionette) 前端构建配置
// - dev: /api 代理到本地 FastAPI（docker compose 默认端口 8000）
// - Tailwind CSS v4 走官方 Vite 插件（CSS-first，不写 tailwind.config.js）
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
    target: 'es2022',
    // 厂商分包：把体积大且低频变动的 React 运行时单独拆出，改善首屏与缓存命中。
    // 只拆一层 —— vendor-react 为叶子，不反向依赖其它 vendor 包，结构上杜绝循环分包。
    // 注意：必须精确匹配 `node_modules/react`、`node_modules/react-dom`、`node_modules/scheduler`，
    // 否则 `@floating-ui/react-dom` 这类含 "react-dom" 子串的包会被误并入 react 包，形成循环分包。
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) return undefined;
          if (/node_modules[\\/](?:react|react-dom|scheduler)[\\/]/.test(id)) {
            return 'vendor-react';
          }
          return 'vendor';
        },
      },
    },
  },
});
