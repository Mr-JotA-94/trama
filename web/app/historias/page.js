// TRAMA — Feed de historias (clústeres de Fase 2).
// Server Component: consulta en servidor, revalidación c/5 min.
//
// Dos queries separadas y explícitas (no triple join anidado):
//   1. stories — metadatos de cada clúster
//   2. story_articles + articles — solo títulos y scores, acotado a esos story_ids
// El título canónico (mayor score_neutralidad entre noticias) se resuelve en JS.
import Link from "next/link";
import { supabase } from "@/lib/supabase";
import { tituloCanonico } from "@/lib/colapsarCluster";

export const revalidate = 300;

function fechaRango(inicio, fin) {
  const fmt = (ts) =>
    new Date(ts).toLocaleDateString("es-CO", {
      timeZone: "America/Bogota",
      day: "numeric", month: "short", year: "numeric",
    });
  if (!inicio) return "fecha desconocida";
  const dI = fmt(inicio);
  const dF = fin ? fmt(fin) : null;
  return dF && dF !== dI ? `${dI} – ${dF}` : dI;
}

export default async function Historias() {
  // Query 1: solo stories, sin joins
  const { data: stories, error: errorStories } = await supabase
    .from("stories")
    .select("id, titulo, fecha_inicio, fecha_fin, n_articulos, n_medios, created_at")
    .order("created_at", { ascending: false })
    .limit(30);

  if (errorStories) {
    return <p>El archivo de historias no respondió. Recarga para reintentar.</p>;
  }

  if (!stories?.length) {
    return (
      <div className="placeholder-fase">
        <span className="placeholder-fase-label">Fase 2 · en construcción</span>
        <p className="placeholder-fase-texto">
          El clustering aún no ha corrido. Las historias aparecen cuando el
          pipeline conecta 2+ artículos del mismo hecho en 2+ medios.
        </p>
      </div>
    );
  }

  // Query 2: títulos para los story_ids que acabamos de traer — join de 2 niveles,
  // explícito y acotado. Error no bloquea: los títulos caen al fallback de stories.titulo.
  const storyIds = stories.map((s) => s.id);
  const { data: saRows } = await supabase
    .from("story_articles")
    .select("story_id, score_neutralidad, articles(titulo, tipo)")
    .in("story_id", storyIds);

  // Agrupar por story_id en el shape que espera tituloCanonico
  const rowsByStory = new Map();
  for (const row of saRows ?? []) {
    if (!rowsByStory.has(row.story_id)) rowsByStory.set(row.story_id, []);
    rowsByStory.get(row.story_id).push({
      tipo:              row.articles?.tipo,
      titulo:            row.articles?.titulo,
      score_neutralidad: row.score_neutralidad,
    });
  }

  return (
    <>
      <p className="dia-titulo">{stories.length} historias detectadas</p>
      <div className="historias-lista">
        {stories.map((story) => {
          const titulo = tituloCanonico(
            rowsByStory.get(story.id) ?? [],
            story.titulo
          );
          return (
            <article key={story.id} className="historia-item">
              <div className="historia-meta">
                <span className="tag">
                  {story.n_medios} {story.n_medios === 1 ? "medio" : "medios"}
                </span>
                <span className="tag">
                  {story.n_articulos}{" "}
                  {story.n_articulos === 1 ? "captura" : "capturas"}
                </span>
                <span className="historia-fecha">
                  {fechaRango(story.fecha_inicio, story.fecha_fin)}
                </span>
              </div>
              <h2 className="historia-titulo">
                <Link href={`/historia/${story.id}`}>{titulo}</Link>
              </h2>
            </article>
          );
        })}
      </div>
    </>
  );
}
