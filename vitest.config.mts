import { defineConfig } from 'vitest/config';
import { fileURLToPath } from 'node:url';

// Pruebas del frontend: funciones puras y componentes pequeños, sin red ni
// backend (los `fetch` se simulan en cada prueba).
export default defineConfig({
  esbuild: { jsx: 'automatic' },
  resolve: { alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) } },
  test: {
    environment: 'jsdom',
    include: ['src/**/*.test.{ts,tsx}'],
    clearMocks: true,
  },
});
