import path from 'node:path';
import { defineConfig } from 'vite';
import tailwindcss from '@tailwindcss/vite';
export default defineConfig({
  root: path.resolve(import.meta.dirname, 'static'),
  base: process.env.PUBLIC_BASE_PATH || '/ai-news-radar/',
  plugins: [tailwindcss()],
  build: { assetsDir: 'assets/public-reader', outDir: path.resolve(import.meta.dirname, '../../.public-export/site'), emptyOutDir: true },
});
