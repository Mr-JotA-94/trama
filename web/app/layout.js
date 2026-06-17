// TRAMA — layout raíz. Carga las tres tipografías del sistema de diseño
// y pinta el membrete (masthead) presente en todas las páginas.
import "./globals.css";
import Link from "next/link";
import { Archivo_Black, Archivo, Source_Serif_4, IBM_Plex_Mono } from "next/font/google";

// Display: Archivo (fundición Omnibus-Type, Argentina). La elección es el concepto.
const archivoBlack = Archivo_Black({ weight: "400", subsets: ["latin"], variable: "--f-display" });
const archivo = Archivo({ subsets: ["latin"], variable: "--f-ui" });
// Cuerpo: serif de lectura de prensa.
const sourceSerif = Source_Serif_4({ subsets: ["latin"], variable: "--f-body" });
// Utilitaria forense: hashes, timestamps, diffs.
const plexMono = IBM_Plex_Mono({ weight: ["400", "500"], subsets: ["latin"], variable: "--f-mono" });

export const metadata = {
  title: "TRAMA — hemeroteca forense de medios colombianos",
  description:
    "Archivo verificable de cómo los medios colombianos publican y reescriben las noticias. Capturas con hash y marca de tiempo.",
};

export default function RootLayout({ children }) {
  return (
    <html lang="es">
      <body className={`${archivoBlack.variable} ${archivo.variable} ${sourceSerif.variable} ${plexMono.variable}`}>
        <header className="masthead">
          <div className="masthead-inner">
            <Link href="/" className="brand">TRAMA</Link>
            <p className="tagline">Hemeroteca forense · medios colombianos</p>
            <nav className="masthead-nav">
              <Link href="/" className="nav-link">Registro</Link>
              <Link href="/historias" className="nav-link">Historias</Link>
            </nav>
          </div>
          {/* El hilo: la línea roja de investigación que recorre el sitio */}
          <div className="hilo" aria-hidden="true" />
        </header>
        <main className="contenedor">{children}</main>
        <footer className="pie">
          <p>
            TRAMA archiva el contenido públicamente visible de cada medio, con hash
            SHA-256 y marca de tiempo de captura. Cada artículo enlaza a su original.
          </p>
          <p className="pie-fase">Fase 1 · archivo en construcción</p>
        </footer>
      </body>
    </html>
  );
}
