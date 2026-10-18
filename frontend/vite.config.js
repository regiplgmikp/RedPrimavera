import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// El puerto 5173 ya está en CORS_ORIGINS del .env del backend. Usa http://localhost:5173
// (no 127.0.0.1): son orígenes distintos para CORS.
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, strictPort: true },
});
