// TRAMA — Feed de historias (clústeres de Fase 2).
// Server Component: consulta en servidor, revalidación c/5 min.
// Con searchParams la página se renderiza dinámicamente en cada request.
//
// Filtros disponibles: q (texto por título de artículo), desde/hasta (fecha_inicio).
// Orden: sort=reciente|medios|cobertura (default: reciente → fecha_fin desc)
// Paginación: page=N, 20 por página (solo rama SIN BÚSQUEDA).
//
// Sin búsqueda — dos queries explícitas y acotadas:
//   Q1. stories con filtro de fecha + count + range
//   Q2. story_articles + articles — solo títulos, acotado a esos story_ids
//
// Con búsqueda — tres queries en serie:
//   Q1. articles.ilike(titulo, %q%) → article_ids
//   Q2. story_articles.in(article_id) → story_ids
//   Q3. stories.in(id, story_ids) con filtro de fecha + orden
import Link from "next/link";
import { supabase } from "@/lib/supabase";
import { tituloCanonico } from "@/lib/colapsarCluster";
import { Buscador } from "@/app/components/Buscador";
import ArticuloSinHistoria from "@/app/components/ArticuloSinHistoria";

export const revalidate = 300;

const POR_PAGINA = 20;

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

// Orden del feed. Default fecha_fin (actividad real del clúster), con
// desempate determinista — sin él, dentro de un mismo valor vuelve a colar
// el ruido de created_at.
function aplicarOrden(query, sort) {
  switch (sort) {
    case "medios":
      return query.order("n_medios",    { ascending: false })
                  .order("n_articulos", { ascending: false });
    case "cobertura":
      return query.order("n_articulos", { ascending: false })
                  .order("n_medios",    { ascending: false });
    case "reciente":
    default:
      return query.order("fecha_fin",    { ascending: false })
                  .order("fecha_inicio", { ascending: false });
  }
}

function construirHref(params) {
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v) sp.set(k, String(v));
  const qs = sp.toString();
  return qs ? `/historias?${qs}` : "/historias";
}

function ControlOrden({ sort, filtros }) {
  const opciones = [
    { val: "reciente",  txt: "Más reciente" },
    { val: "medios",    txt: "Más medios" },
    { val: "cobertura", txt: "Más cobertura" },
  ];
  return (
    <nav className="historias-orden" aria-label="Ordenar historias">
      {opciones.map((o) => (
        <Link
          key={o.val}
          href={construirHref({ ...filtros, sort: o.val })}
          className={sort === o.val ? "activo" : ""}
          aria-current={sort === o.val ? "true" : undefined}
        >
          {o.txt}
        </Link>
      ))}
    </nav>
  );
}

function Paginacion({ page, totalPaginas, filtros, sort }) {
  if (totalPaginas <= 1) return null;
  const nums = Array.from({ length: totalPaginas }, (_, i) => i + 1);
  return (
    <nav className="paginacion" aria-label="Paginación">
      {page > 1 ? (
        <Link href={construirHref({ ...filtros, sort, page: page - 1 })}>‹ Anterior</Link>
      ) : <span className="disabled">‹ Anterior</span>}
      {nums.map((n) =>
        n === page ? (
          <span key={n} className="actual" aria-current="page">{n}</span>
        ) : (
          <Link key={n} href={construirHref({ ...filtros, sort, page: n })}>{n}</Link>
        )
      )}
      {page < totalPaginas ? (
        <Link href={construirHref({ ...filtros, sort, page: page + 1 })}>Siguiente ›</Link>
      ) : <span className="disabled">Siguiente ›</span>}
    </nav>
  );
}

export default async function Historias({ searchParams }) {
  const q     = (searchParams?.q     ?? "").trim();
  const desde = (searchParams?.desde ?? "").trim();
  const hasta = (searchParams?.hasta ?? "").trim();
  const sort  = (searchParams?.sort  ?? "reciente").trim();
  const page  = Math.max(1, parseInt(searchParams?.page ?? "1", 10) || 1);

  const filtros = { q, desde, hasta, sort };

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
      .select("id, titulo, fecha_inicio, fecha_fin, n_articulos, n_medios")
      .in("id", storyIds);
    q3 = aplicarFechas(q3, desde, hasta);
    q3 = aplicarOrden(q3, sort);

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
        <ControlOrden sort={sort} filtros={filtros} />
        <ListaHistorias stories={stories} titulos={titulos} />
      </>
    );
  }

  // ── SIN BÚSQUEDA ─────────────────────────────────────────────────────────
  const offset = (page - 1) * POR_PAGINA;
  let q1 = supabase
    .from("stories")
    .select("id, titulo, fecha_inicio, fecha_fin, n_articulos, n_medios",
            { count: "exact" });
  q1 = aplicarFechas(q1, desde, hasta);
  q1 = aplicarOrden(q1, sort);
  q1 = q1.range(offset, offset + POR_PAGINA - 1);

  const { data: stories, count, error: errorStories } = await q1;

  const totalPaginas = Math.max(1, Math.ceil((count ?? 0) / POR_PAGINA));

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
        {count ?? 0} {(count ?? 0) === 1 ? "historia" : "historias"}
        {hayFiltroActivo ? " en el rango seleccionado" : " detectadas"}
      </p>
      <ControlOrden sort={sort} filtros={filtros} />
      <ListaHistorias stories={stories} titulos={titulos} />
      <Paginacion page={page} totalPaginas={totalPaginas} filtros={filtros} sort={sort} />
    </>
  );
}
