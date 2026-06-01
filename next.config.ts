import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* config options here */
  output: 'export',           // ← Esto es lo más importante
  basePath: '/ObservatorioLaboral/src/app/page.tsx',  // Nombre exacto de tu repositorio
  images: {
    unoptimized: true,        // Necesario para GitHub Pages
  },
  trailingSlash: true,        // Recomendado
};

export default nextConfig;
