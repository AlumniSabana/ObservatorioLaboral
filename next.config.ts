import type { NextConfig } from "next";

// Configuración de Next.js orientada a desplegar el sitio en Vercel.
//
// Antes esto era una exportación 100% estática para GitHub Pages (output:
// 'export' + basePath '/ObservatorioLaboral'), lo que dejaba las rutas API de
// Next (src/app/api/chat) SIN correr como servidor — el chat no funcionaba en
// producción. Vercel sirve Next.js nativo (SSR + funciones serverless), así
// que ya no hace falta ni el export ni el basePath: el sitio vive en la raíz
// de su propio dominio y /api/chat corre de verdad.
const nextConfig: NextConfig = {};

export default nextConfig;
