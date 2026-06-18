// TRAMA — Expediente de historia (clúster de Fase 2).
// Server Component: solo lectura, revalidación c/5 min.
import Link from "next/link";
import { notFound } from "next/navigation";
import { supabase } from "@/lib/supabase";
import {
  colapsarCluster,
  tituloCanonico,
  etiquetarAnclas,
} from "@/lib/colapsarCluster";

export const revalidate = 300;

// ── Helpers de formato ────────────────────────────────────────────────────────

function horaCO(ts) {
  return new Date(ts).toLocaleTimeString("es-CO", {
    timeZone: "America/Bogota", hour: "2-digit", minute: "2-digit",
  });
}

function fechaRango(inicio, fin) {
  const fmt = (ts) =>
    new Date(ts).toLocaleDateString("es-CO", {
      timeZone: "America/Bogota",
      day: "numeric", month: "long", year: "numeric",
    });
  if (!inicio) return "fecha desconocida";
  const dI = fmt(inicio);
  const dF = fin ? fmt(fin) : null;
  return dF && dF !== dI ? `${dI} – ${dF}` : dI;
}

// ── Sub-componentes (Server, misma página) ────────────────────────────────────

function CardAncla({ articulo: a, label }) {
  return (
    <article className={`card-ancla medio-${a.medio_slug}`}>
      <div className="card-header">
        <div className="card-header-tags">
          <Link
            href={`/medio/${a.medio_slug}`}
            className={`tag tag-medio medio-${a.medio_slug}`}
          >
            {a.medio_nombre}
          </Link>
          {a.seccion && <span className="tag tag-seccion">{a.seccion}</span>}
          {a.es_parcial && <span className="tag tag-parcial">captura parcial</span>}
        </div>
        {label && <span className="ancla-label">{label}</span>}
      </div>

      <h3 className="card-titulo">
        <Link href={`/articulo/${a.article_id}`}>{a.titulo}</Link>
      </h3>
      {a.subtitulo && <p className="card-sub">{a.subtitulo}</p>}

      <dl className="card-scores">
        <dt>neutralidad</dt><dd>{a.score_neutralidad?.toFixed(2) ?? "—"}</dd>
        <dt>cobertura</dt> <dd>{a.score_cobertura?.toFixed(2) ?? "—"}</dd>
        <dt>divergencia</dt><dd>{a.score_divergencia?.toFixed(2) ?? "—"}</dd>
      </dl>

      <div className="card-footer">
        <span className="captura-meta" title="SHA-256 de la captura representante">
          {a.capturas[a.capturas.length - 1].hash_sha256.slice(0, 12)}…
        </span>
        <a
          href={a.url}
          target="_blank"
          rel="noopener noreferrer"
          className="enlace-original"
        >
          Leer original en {a.medio_nombre} →
        </a>
      </div>
    </article>
  );
}

function CardSecundaria({ articulo: a }) {
  return (
    <article className="card-secundaria">
      <div className="card-header-tags">
        <Link
          href={`/medio/${a.medio_slug}`}
          className={`tag tag-medio medio-${a.medio_slug}`}
        >
          {a.medio_nombre}
        </Link>
        {a.seccion && <span className="tag tag-seccion">{a.seccion}</span>}
        {a.es_parcial && <span className="tag tag-parcial">captura parcial</span>}
      </div>
      <h3 className="card-titulo card-titulo-sm">
        <Link href={`/articulo/${a.article_id}`}>{a.titulo}</Link>
      </h3>
      <div className="card-footer-sm">
        <p className="card-hora">{horaCO(a.fecha_primera_captura)}</p>
        <a
          href={a.url}
          target="_blank"
          rel="noopener noreferrer"
          className="enlace-original"
        >Leer original ↗</a>
      </div>
    </article>
  );
}

// ── Página ────────────────────────────────────────────────────────────────────

export default async function Historia({ params }) {
  const { data: story, error } = await supabase
    .from("stories")
    .select(`
      id, titulo, fecha_inicio, fecha_fin, n_articulos, n_medios, created_at,
      story_articles (
        score_neutralidad, score_cobertura, score_divergencia, es_ancla,
        articles (
          id, url, titulo, subtitulo, fecha_captura,
          es_parcial, tipo, seccion, hash_sha256,
          outlets ( slug, nombre )
        )
      )
    `)
    .eq("id", params.id)
    .single();

  if (error || !story) notFound();

  // Aplanar filas anidadas al shape que espera colapsarCluster
  const capturas = (story.story_articles ?? []).map((sa) => ({
    article_id:        sa.articles.id,
    url:               sa.articles.url,
    medio_slug:        sa.articles.outlets.slug,
    medio_nombre:      sa.articles.outlets.nombre,
    hash_sha256:       sa.articles.hash_sha256,
    fecha_captura:     sa.articles.fecha_captura,
    titulo:            sa.articles.titulo,
    subtitulo:         sa.articles.subtitulo,
    es_parcial:        sa.articles.es_parcial,
    tipo:              sa.articles.tipo,
    seccion:           sa.articles.seccion,
    es_ancla:          sa.es_ancla,
    score_neutralidad: sa.score_neutralidad,
    score_cobertura:   sa.score_cobertura,
    score_divergencia: sa.score_divergencia,
  }));

  const articulos  = colapsarCluster(capturas);
  const tituloH    = tituloCanonico(articulos, story.titulo);
  const anclas     = articulos.filter((a) => a.es_ancla);
  const secundarias = articulos.filter((a) => !a.es_ancla);
  const labels     = etiquetarAnclas(articulos);

  return (
    <>
      {/* Breadcrumb */}
      <p className="breadcrumb">
        <Link href="/historias">← Historias</Link>
      </p>

      {/* ── HEADER ── */}
      <div className="historia-header">
        <h1 className="articulo-titulo">{tituloH}</h1>
        <div className="historia-header-meta">
          <span className="tag">
            {story.n_medios} {story.n_medios === 1 ? "medio" : "medios"}
          </span>
          <span className="tag">
            {story.n_articulos} {story.n_articulos === 1 ? "captura" : "capturas"}
          </span>
          <span className="historia-fecha">
            {fechaRango(story.fecha_inicio, story.fecha_fin)}
          </span>
        </div>
      </div>

      {/* ── RESUMEN — PLACEHOLDER ── */}
      <div className="placeholder-fase">
        <span className="placeholder-fase-label">Fase 3 · generado por LLM por clúster</span>
        <p className="placeholder-fase-texto">
          Resumen del hecho: el pipeline de análisis de Fase 3 sintetizará
          aquí lo que todos los artículos tienen en común, sin el encuadre
          de ningún medio en particular.
        </p>
      </div>

      {/* ── HILO CRONOLÓGICO ── */}
      <section className="historia-seccion">
        <h2 className="seccion-titulo">Línea de tiempo</h2>
        {/* Nota: el hilo arranca como lista CSS. SVG con curvas Bézier
            ("hilo que cuelga entre clavos") es el siguiente refinamiento visual. */}
        <ol className="hilo-cronologico">
          {articulos.map((a) => (
            <li key={a.url} className="hilo-nodo">
              <div className="hilo-nodo-meta">
                {a.editada ? (
                  <>
                    <span className="hilo-hora hilo-hora-tachada">
                      {horaCO(a.fecha_primera_captura)}
                    </span>
                    <span className="hilo-hora hilo-hora-nueva">
                      {horaCO(a.fecha_ultima_captura)}
                    </span>
                    <span className="tag tag-editada">editada</span>
                  </>
                ) : (
                  <span className="hilo-hora">
                    {horaCO(a.fecha_primera_captura)}
                  </span>
                )}
                <Link
                  href={`/medio/${a.medio_slug}`}
                  className={`tag tag-medio medio-${a.medio_slug}`}
                >
                  {a.medio_nombre}
                </Link>
                {a.seccion && (
                  <span className="tag tag-seccion">{a.seccion}</span>
                )}
              </div>

              <div className="hilo-nodo-titulo">
                {a.titulo_cambio ? (
                  <>
                    <span className="hilo-titulo-tachado">{a.titulo_original}</span>
                    {" "}
                    <Link href={`/articulo/${a.article_id}`}>{a.titulo}</Link>
                  </>
                ) : (
                  <Link href={`/articulo/${a.article_id}`}>{a.titulo}</Link>
                )}
              </div>

              {/* Popup de historial de capturas (sin JS: <details>) */}
              {a.n_capturas > 1 && (
                <details className="hilo-historial">
                  <summary>
                    {a.n_capturas} capturas
                    {!a.editada && " · solo cuerpo/hash"}
                  </summary>
                  <ul className="hilo-historial-lista">
                    {a.capturas.map((c, i) => (
                      <li key={c.hash_sha256}>
                        <span className="hilo-hora">{horaCO(c.fecha_captura)}</span>
                        <Link href={`/articulo/${c.article_id}`} className="hilo-hash">
                          {c.hash_sha256.slice(0, 12)}…
                        </Link>
                        {i > 0 && c.titulo !== a.capturas[i - 1].titulo && (
                          <span className="hilo-cambio-label"> · título cambiado</span>
                        )}
                      </li>
                    ))}
                  </ul>
                </details>
              )}
            </li>
          ))}

          {/* Nodo placeholder: historia relacionada (Fase 2 avanzada) */}
          <li className="hilo-nodo hilo-nodo-relacionada" aria-label="Historia relacionada pendiente">
            <span className="hilo-nodo-rel-puntos">· · ·</span>
            <span className="hilo-nodo-rel-label">
              Historias relacionadas · Fase 2 avanzada · requiere{" "}
              <code>story_relations</code>
            </span>
          </li>
        </ol>
      </section>

      {/* ── VERSIONES (BENTO) ── */}
      <section className="historia-seccion">
        <h2 className="seccion-titulo">Versiones</h2>

        {/* Deuda visible solo en clústeres grandes: en clústeres de ≥6 artículos
            score_cobertura se vuelve baja y plana (la unión de entidades es enorme),
            y puede hacer ancla a una reacción que nombra muchos actores en lugar
            del artículo más factual. En clústeres chicos el efecto no se manifiesta.
            (Documentado en BITACORA 2026-06-16.) */}
{anclas.length > 0 ? (
          <div className="bento-anclas">
            {anclas.map((a) => (
              <CardAncla key={a.url} articulo={a} label={labels.get(a.url)} />
            ))}
          </div>
        ) : (
          <p className="gris-archivo">
            El pipeline no marcó anclas para este clúster.
          </p>
        )}

        {secundarias.length > 0 && (
          <div className="bento-secundarias">
            {secundarias.map((a) => (
              <CardSecundaria key={a.url} articulo={a} />
            ))}
          </div>
        )}
      </section>

      {/* ── ANÁLISIS DE PERSUASIÓN — PLACEHOLDER ── */}
      <section className="historia-seccion">
        <h2 className="seccion-titulo">Análisis de persuasión</h2>
        <div className="placeholder-fase">
          <span className="placeholder-fase-label">Fase 3 · Groq + Llama por clúster</span>
          <p className="placeholder-fase-texto">
            Las técnicas de persuasión detectadas (encuadre, omisión, miedo,
            falsa dicotomía…) aparecerán aquí como acordeón por artículo,
            con evidencia textual citable.
          </p>
        </div>
      </section>

      {/* ── REACCIONES — PLACEHOLDER ── */}
      <section className="historia-seccion">
        <h2 className="seccion-titulo">Reacciones</h2>
        <div className="placeholder-fase">
          <span className="placeholder-fase-label">Fase 2 · sin datos</span>
          <p className="placeholder-fase-texto">
            El clustering de Fase 2 agrupa solo noticias. Las columnas de
            opinión, análisis y editoriales sobre este hecho aparecerán aquí
            cuando el pipeline las adjunte como reacciones.
          </p>
        </div>
      </section>

      {/* ── GRAFO PANORÁMICO — PLACEHOLDER ── */}
      <section className="historia-seccion">
        <h2 className="seccion-titulo">Historias conectadas</h2>
        <div className="placeholder-fase">
          <span className="placeholder-fase-label">
            Fase 2 avanzada · requiere tabla story_relations
          </span>
          <p className="placeholder-fase-texto">
            El grafo de historias relacionadas (mismo tema, distinto hecho)
            aparece aquí. Aún no existe la tabla{" "}
            <code>story_relations</code> — implementar después de validar el
            clustering simple con volumen.
          </p>
        </div>
      </section>
    </>
  );
}
