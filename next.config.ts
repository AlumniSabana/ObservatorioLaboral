import type { NextConfig } from "next";

// Configuración de Next.js orientada a desplegar el sitio en GitHub Pages.
// (El workflow .github/workflows/nextjs.yml hace el build y publica la carpeta /out.)
const nextConfig: NextConfig = {
  // 'export' genera un sitio 100% estático (HTML/CSS/JS) en la carpeta /out.
  // OJO: en este modo las rutas API de Next (src/app/api/*) NO corren como
  // servidor; el frontend depende del backend FastAPI para los datos.
  output: 'export',
  // GitHub Pages sirve el sitio bajo la subruta /ObservatorioLaboral, así que
  // todas las URLs internas se prefijan con este basePath. Por eso las llamadas
  // fetch del frontend incluyen '/ObservatorioLaboral/...'.
  basePath: '/ObservatorioLaboral',
  images: {
    // La optimización de imágenes de Next requiere un servidor; en exportación
    // estática se desactiva para que las imágenes se sirvan tal cual.
    unoptimized: true,
  },
  // Genera rutas con barra final (/ruta/) — recomendado para hosting estático.
  trailingSlash: true,
};

export default nextConfig;
