/**
 * Layout raíz de la aplicación (App Router de Next.js).
 *
 * Es el "marco" que envuelve a TODAS las páginas: define el <html>/<body>, carga
 * las fuentes (Geist) y los estilos globales, y fija la metadata (título de la
 * pestaña del navegador). Todo lo que renderiza cada página llega aquí como
 * `children`.
 */

import type { Metadata } from "next";
import { Libre_Franklin, Playfair_Display, Geist_Mono } from "next/font/google";
import "./globals.css";

// Fuentes de Google cargadas vía next/font; se exponen como variables CSS
// (--font-geist-sans / --font-geist-mono) que usa globals.css.
// Cuerpo y títulos siguen la tipografía de AlumniCV: Libre Franklin para el
// texto y una serif ligera para los títulos (allá es Publico Banner, de pago;
// Playfair Display es su respaldo gratuito).
const libreFranklin = Libre_Franklin({
  variable: "--font-body",
  subsets: ["latin"],
  weight: ["300", "400", "500", "600", "700"],
});

const playfair = Playfair_Display({
  variable: "--font-heading",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Alumni Sabana - Observatorio Laboral",
  description: "Observatorio Laboral de Alumni Sabana",
};

// Se ejecuta antes de pintar (evita el parpadeo claro→oscuro): usa la elección
// guardada con el botón de la barra lateral o, si no hay, la del sistema.
const SCRIPT_TEMA = `(function(){var t;try{t=localStorage.getItem('tema')}catch(e){}if(t!=='light'&&t!=='dark')t=matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light';document.documentElement.dataset.theme=t})()`;

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="es"
      className={`${libreFranklin.variable} ${playfair.variable} ${geistMono.variable} h-full antialiased`}
      suppressHydrationWarning
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: SCRIPT_TEMA }} />
      </head>
      <body className="min-h-full">{children}</body>
    </html>
  );
}