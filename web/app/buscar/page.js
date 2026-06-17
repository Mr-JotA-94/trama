// TRAMA — Lookup de artículo por URL.
// Cuatro estados posibles; ningún error se traga en silencio.
//
// variantesUrl cubre con/sin www × con/sin trailing slash (4 combinaciones).
// Deuda documentada: variantes AMP (amp.medio.com), móvil (m.medio.com) y
// subdominios inusuales fallan silencioso — el archivo almacena la URL exacta
// que entregó el RSS/sitemap, sin normalización previa.

import Link from "next/link";
import { redirect } from "next/navigation";
import { supabase } from "@/lib/supabase";
import { normalizarUrl, variantesUrl } from "@/lib/normalizarUrl";
import { Buscador } from "@/app/components/Buscador";

export const revalidate = 0;

export default async function Buscar({ searchParams }) {
  const rawUrl = (searchParams?.url ?? "").trim();

  // Sin URL: formulario vacío
  if (!rawUrl) {
    return (
      <>
        <h1 className="articulo-titulo">Buscar por URL</h1>
        <Buscador action="/historias" labelTexto="Buscar en historias" />
      </>
    );
  }

  const { url: normalized, error: urlError } = normalizarUrl(rawUrl);

  if (urlError) {
    return (
      <>
        <h1 className="articulo-titulo">Buscar por URL</h1>
        <Buscador action="/historias" url={rawUrl} labelTexto="Buscar en historias" />
        <p className="buscar-aviso">{urlError}</p>
      </>
    );
  }

  const variantes = variantesUrl(normalized);

  // Q1: buscar el artículo entre las 4 variantes de URL exacta del archivo
  const { data: captures, error: errorCaptures } = await supabase
    .from("articles")
    .select("id, fecha_captura")
    .in("url", variantes)
    .order("fecha_captura", { ascending: false });

  if (errorCaptures) {
    return (
      <>
        <Buscador action="/historias" url={rawUrl} labelTexto="Buscar en historias" />
        <p className="buscar-aviso">
          Error al consultar el archivo: {errorCaptures.message}
        </p>
      </>
    );
  }

  // URL fuera del archivo
  if (!captures?.length) {
    return (
      <>
        <h1 className="articulo-titulo">Buscar por URL</h1>
        <Buscador action="/historias" url={rawUrl} labelTexto="Buscar en historias" />
        <div className="buscar-resultado">
          <p className="buscar-resultado-titulo">
            Esta URL no está en el archivo de Trama (aún).
          </p>
          <p className="buscar-resultado-sub">
            El crawler cubre 5 medios y corre cada 6 horas. Si la nota es
            reciente, de un medio no incluido, o su URL es una variante AMP o
            móvil, puede que no esté archivada.
          </p>
        </div>
      </>
    );
  }

  // Q2: verificar si alguna captura está en un clúster
  const captureIds = captures.map(c => c.id);

  const { data: sa, error: errorSa } = await supabase
    .from("story_articles")
    .select("story_id")
    .in("article_id", captureIds)
    .limit(1)
    .maybeSingle();

  if (errorSa) {
    return (
      <>
        <Buscador action="/historias" url={rawUrl} labelTexto="Buscar en historias" />
        <p className="buscar-aviso">
          Error al buscar en historias: {errorSa.message}
        </p>
      </>
    );
  }

  // En archivo y en historia → redirect directo
  if (sa?.story_id) {
    redirect(`/historia/${sa.story_id}`);
  }

  // En archivo, sin historia (caso frecuente)
  const latest = captures[0]; // ya ordenado desc por fecha_captura
  return (
    <>
      <h1 className="articulo-titulo">Buscar por URL</h1>
      <Buscador action="/historias" url={rawUrl} labelTexto="Buscar en historias" />
      <div className="buscar-resultado">
        <p className="buscar-resultado-titulo">
          Esta nota está archivada, pero aún no forma parte de ninguna historia.
        </p>
        <p className="buscar-resultado-sub">
          El clustering agrupa artículos cuando 2+ medios cubren el mismo hecho.
          Esta nota no tiene cobertura cruzada en el archivo todavía.
        </p>
        <Link href={`/articulo/${latest.id}`} className="enlace-original">
          Ver la nota archivada →
        </Link>
      </div>
    </>
  );
}
