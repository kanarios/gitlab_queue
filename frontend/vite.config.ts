import path from 'path';
import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }) => {
    const env = loadEnv(mode, '.', '');
    const apiUrl = env.VITE_API_URL || 'http://localhost:8080';
    const wsUrl = env.VITE_WS_URL || 'ws://localhost:8080';

    return {
      server: {
        port: 5173,
        host: '0.0.0.0',
        proxy: {
          '/api': {
            target: apiUrl,
            changeOrigin: true,
          },
          '/auth': {
            target: apiUrl,
            changeOrigin: true,
          },
          '/ws': {
            target: wsUrl,
            ws: true,
          },
          '/webhook': {
            target: apiUrl,
            changeOrigin: true,
          },
          '/health': {
            target: apiUrl,
            changeOrigin: true,
          },
          '/ready': {
            target: apiUrl,
            changeOrigin: true,
          },
        },
      },
      plugins: [react()],
      resolve: {
        alias: {
          '@': path.resolve(__dirname, './src'),
        }
      }
    };
});
