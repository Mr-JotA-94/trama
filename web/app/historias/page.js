// TRAMA — Feed de historias (clústeres de Fase 2).
// Server Component: consulta en servidor, revalidación c/5 min.
// Con searchParams la página se renderiza dinámicamente en cada request.
//
// Filtros disponibles: q (texto por título de artículo), desde/hasta (fecha_inicio).
// Medio/tipo/sección no se exponen aquí: son atributos de artículo, no de historia.
//
// Sin búsqueda — dos queries explícitas y acotadas:
//   Q1. stories con filtro de fecha
//   Q2. story_articles + articles — solo títulos, acotado a esos story_ids
//
// Con búsqueda — tres queries en serie:
//   Q1. articles.ilike(titulo, %q%) → article_ids
//   Q2. story_articles.in(article_id) → story_ids
//   Q3. stories.in(id, story_ids) con filtro de fecha
import Link from "next/link";
import { supabase } from "@/lib/supabase";
import { tituloCanonico } from "@/lib/colapsarCluster";
import { Buscador } from "@/app/components/Buscador";
import ArticuloSinHistoria from "@/app/components/ArticuloSinHistoria";

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

function resolverTitulos(stories, saRows) {
  const rowsByStory = new Map();
  for (const row of saRows ?? []) {
    if (!rowsByStory.has(row.story_id)) rowsByStory.set(row.story_id, []);
    rowsByStory.get(row.story_id).push({
      tipo:              row.articles?.tipo,
      titulo:            row.articles?.titulo,
      score_neutralidad: row.score_neutralidad,
    });
  }
  const titulos = new Map();
  for (const s of stories) {
    titulos.set(s.id, tituloCanonico(rowsByStory.get(s.id) ?? [], s.titulo));
  }
  return titulos;
}

function ListaHistorias({ stories, titulos }) {
  return (
    <div className="historias-lista">
      {stories.map((story) => (
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
            <Link href={`/historia/${story.id}`}>{titulos.get(story.id)}</Link>
          </h2>
        </article>
      ))}
    </div>
  );
}

// Aplica filtros de fecha a un query builder de stories
function aplicarFechas(query, desde, hasta) {
  if (desde) query = query.gte("fecha_inicio", `${desde}T00:00:00`);
  if (hasta) query = query.lte("fecha_inicio", `${hasta}T23:59:59`);
  return query;
}

export default async function Historias({ searchParams }) {
  const q     = (searchParams?.q     ?? "").trim();
  const desde = (searchParams?.desde ?? "").trim();
  const hasta = (searchParams?.hasta ?? "").trim();

  const filtros = { desde, hasta };

  const buscadorProps = {
    action: "/historias",
    labelTexto: "Buscar en historias",
    conFecha: true,
    filtros,
  };

  // ── CON BÚSQUEDA ──────────────────────────────────────────────────────────
  if (q) {
    const { data: matchArticles, error: errA } = await supabase
      .from("articles")
      .select("id, titulo")
      .ilike("titulo", `%${q}%`)
      .limit(200);

    if (errA) {
      return (
        <>
          <Buscador {...buscadorProps} q={q} />
          <p>Error al buscar artículos: {errA.message}</p>
        </>
      );
    }

    if (!matchArticles?.length) {
      return (
        <>
          <Buscador {...buscadorProps} q={q} />
          <p className="buscar-resultado-sub">Sin resultados para «{q}».</p>
        </>
      );
    }

    const articleIds = matchArticles.map((a) => a.id);
    const { data: saMatch, error: errSa } = await supabase
      .from("story_articles")
      .select("story_id")
      .in("article_id", articleIds);

    if (errSa) {
      return (
        <>
          <Buscador {...buscadorProps} q={q} />
          <p>Error al buscar historias: {errSa.message}</p>
        </>
      );
    }

    if (!saMatch?.length) {
      return (
        <>
          <Buscador {...buscadorProps} q={q} />
          <ArticuloSinHistoria articulos={matchArticles} />
        </>
      );
    }

    const storyIds = [...new Set(saMatch.map((r) => r.story_id))];
    let q3 = supabase
      .from("stories")
      .select("id, titulo, fecha_inicio, fecha_fin, n_articulos, n_medios, created_at")
      .in("id", storyIds)
      .order("created_at", { ascending: false });
    q3 = aplicarFechas(q3, desde, hasta);

    const { data: stories, error: errS } = await q3;
    if (errS) {
      return (
        <>
          <Buscador {...buscadorProps} q={q} />
          <p>Error al cargar historias: {errS.message}</p>
        </>
      );
    }

    if (!stories?.length) {
      return (
        <>
          <Buscador {...buscadorProps} q={q} />
          <p className="buscar-resultado-sub">
            Sin historias para «{q}»{desde || hasta ? " en ese rango de fechas" : ""}.
          </p>
        </>
      );
    }

    const { data: saRows } = await supabase
      .from("story_articles")
      .select("story_id, score_neutralidad, articles(titulo, tipo)")
      .in("story_id", stories.map((s) => s.id));

    const titulos = resolverTitulos(stories, saRows);

    return (
      <>
        <Buscador {...buscadorProps} q={q} />
        <p className="buscar-resultado-sub">
          {stories.length} {stories.length === 1 ? "historia" : "historias"} para «{q}»
        </p>
        <ListaHistorias stories={stories} titulos={titulos} />
      </>
    );
  }

  // ── SIN BÚSQUEDA ─────────────────────────────────────────────────────────
  let q1 = supabase
    .from("stories")
    .select("id, titulo, fecha_inicio, fecha_fin, n_articulos, n_medios, created_at")
    .order("created_at", { ascending: false })
    .limit(30);
  q1 = aplicarFechas(q1, desde, hasta);

  const { data: stories, error: errorStories } = await q1;

  if (errorStories) {
    return (
      <>
        <Buscador {...buscadorProps} />
        <p>El archivo de historias no respondió. Recarga para reintentar.</p>
      </>
    );
  }

  if (!stories?.length) {
    return (
      <>
        <Buscador {...buscadorProps} />
        {desde || hasta ? (
          <p className="buscar-resultado-sub">Sin historias en ese rango de fechas.</p>
        ) : (
          <div className="placeholder-fase">
            <span className="placeholder-fase-label">Fase 2 · en construcción</span>
            <p className="placeholder-fase-texto">
              El clustering aún no ha corrido. Las historias aparecen cuando el
              pipeline conecta 2+ artículos del mismo hecho en 2+ medios.
            </p>
          </div>
        )}
      </>
    );
  }

  const storyIds = stories.map((s) => s.id);
  const { data: saRows } = await supabase
    .from("story_articles")
    .select("story_id, score_neutralidad, articles(titulo, tipo)")
    .in("story_id", storyIds);

  const titulos = resolverTitulos(stories, saRows);
  const hayFiltroActivo = desde || hasta;

  return (
    <>
      <Buscador {...buscadorProps} />
      <p className="dia-titulo">
        {stories.length} {stories.length === 1 ? "historia" : "historias"}
        {hayFiltroActivo ? " en el rango seleccionado" : " detectadas"}
      </p>
      <ListaHistorias stories={stories} titulos={titulos} />
    </>
  );
}
