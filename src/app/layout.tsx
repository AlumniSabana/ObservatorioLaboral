/**
 * Layout raíz de la aplicación (App Router de Next.js).
 *
 * Es el "marco" que envuelve a TODAS las páginas: define el <html>/<body>, carga
 * las fuentes (Geist) y los estilos globales, y fija la metadata (título de la
 * pestaña del navegador). Todo lo que renderiza cada página llega aquí como
 * `children`.
 */

import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

// Fuentes de Google cargadas vía next/font; se exponen como variables CSS
// (--font-geist-sans / --font-geist-mono) que usa globals.css.
const geistSans = Geist({
  variable: "--font-geist-sans",
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

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="es"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full">{children}</body>
    </html>
  );
}