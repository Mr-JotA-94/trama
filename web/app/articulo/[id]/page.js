// TRAMA — Página de artículo: el expediente.
// Muestra la captura archivada con sus metadatos forenses completos.
import Link from "next/link";
import { notFound } from "next/navigation";
import { supabase } from "@/lib/supabase";

export const revalidate = 3600; // las capturas son inmutables: cache larga

function fechaCO(ts) {
  if (!ts) return "no declarada";
  return new Date(ts).toLocaleString("es-CO", {
    timeZone: "America/Bogota",
    day: "numeric", month: "long", year: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

export default async function Articulo({ params }) {
  const [{ data: a, error }, { data: sa }] = await Promise.all([
    supabase.from("articles").select("*, outlets(nombre, slug)").eq("id", params.id).single(),
    supabase.from("story_articles").select("story_id").eq("article_id", params.id).maybeSingle(),
  ]);

  if (error || !a) notFound();

  return (
    <>
      {sa?.story_id && (
        <p className="historia-ref">
          <Link href={`/historia/${sa.story_id}`}>Parte de una historia →</Link>
        </p>
      )}
      <h1 className="articulo-titulo">{a.titulo}</h1>
      {a.subtitulo && <p className="articulo-sub">{a.subtitulo}</p>}

      {/* El expediente: los metadatos son evidencia, no decoración */}
      <dl className="expediente">
        <dt>medio</dt>
        <dd><Link href={`/medio/${a.outlets.slug}`}>{a.outlets.nombre}</Link></dd>
        <dt>tipo</dt>
        <dd>{a.tipo}</dd>
        <dt>sección</dt>
        <dd>{a.seccion || "no declarada"}</dd>
        <dt>autoría</dt>
        <dd>{a.autor || "no declarada"}</dd>
        <dt>publicado</dt>
        <dd>{fechaCO(a.fecha_publicacion)}</dd>
        <dt>capturado</dt>
        <dd>{fechaCO(a.fecha_captura)} (hora de Colombia)</dd>
        <dt>sha-256</dt>
        <dd>{a.hash_sha256}</dd>
      </dl>

      <a href={a.url} target="_blank" rel="noopener noreferrer" className="enlace-original enlace-superior">
        Leer el original en {a.outlets.nombre} →
      </a>

      {a.es_parcial && (
        <p className="aviso-parcial">
          Captura parcial: el medio limita este contenido a suscriptores.
          TRAMA archiva únicamente lo que era visible públicamente al momento
          de la captura.
        </p>
      )}

      <div className="articulo-cuerpo">
        {a.contenido_visible.split("\n").filter(Boolean).map((parrafo, i) => (
          <p key={i}>{parrafo}</p>
        ))}
      </div>

      <a href={a.url} target="_blank" rel="noopener noreferrer" className="enlace-original">
        Leer el original en {a.outlets.nombre} →
      </a>
    </>
  );
}
