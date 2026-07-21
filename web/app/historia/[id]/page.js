// TRAMA — Expediente de historia (clúster de Fase 2).
// Server Component: solo lectura, revalidación c/5 min.
import { Fragment } from "react";
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

// Clave de fecha-calendario (yyyy-mm-dd) en America/Bogota. Es la base de toda
// comparación "¿cambió el día?": nunca comparar los timestamp crudos (UTC),
// porque el corte de medianoche no coincide con el de Bogotá.
function claveDiaCO(ts) {
  return new Date(ts).toLocaleDateString("en-CA", { timeZone: "America/Bogota" });
}

// Diferencia en días de calendario (Bogotá) entre dos timestamps.
function diffDiasCO(desde, hasta) {
  const d1 = new Date(claveDiaCO(desde) + "T00:00:00Z");
  const d2 = new Date(claveDiaCO(hasta) + "T00:00:00Z");
  return Math.round((d2 - d1) / 86400000);
}

// Etiqueta del separador de día del hilo, ej. "Jueves 18 de julio".
function separadorDiaCO(ts) {
  const texto = new Date(ts)
    .toLocaleDateString("es-CO", {
      timeZone: "America/Bogota", weekday: "long", day: "numeric", month: "long",
    })
    .replace(",", "");
  return texto.charAt(0).toUpperCase() + texto.slice(1);
}

// Empareja cada artículo del hilo con su separador de día (null si cae el
// mismo día-calendario Bogotá que el artículo anterior). El primero siempre
// lleva separador. Se calcula UNA vez sobre la lista completa y ordenada para
// que el corte de día no se pierda entre la vista previa y "ver más".
function construirHilo(articulos) {
  let diaAnterior = null;
  return articulos.map((a) => {
    const dia = claveDiaCO(a.fecha_primera_captura);
    const separador = dia !== diaAnterior ? separadorDiaCO(a.fecha_primera_captura) : null;
    diaAnterior = dia;
    return { articulo: a, separador };
  });
}

// Rango + duración del clúster para el encabezado, ej. "Del 16 al 21 de julio
// · 5 días". Si inicio y fin caen en el mismo día-calendario Bogotá, no hay
// rango que mostrar: se cae a la fecha única.
function rangoConDuracion(inicio, fin) {
  if (!inicio) return "fecha desconocida";
  const finEfectivo = fin || inicio;

  if (claveDiaCO(inicio) === claveDiaCO(finEfectivo)) {
    return new Date(inicio).toLocaleDateString("es-CO", {
      timeZone: "America/Bogota", day: "numeric", month: "long", year: "numeric",
    });
  }

  const soloDia = (ts) =>
    new Date(ts).toLocaleDateString("es-CO", { timeZone: "America/Bogota", day: "numeric" });
  const conMes = (ts) =>
    new Date(ts).toLocaleDateString("es-CO", {
      timeZone: "America/Bogota", day: "numeric", month: "long",
    });
  const mesDe = (ts) =>
    new Date(ts).toLocaleDateString("es-CO", { timeZone: "America/Bogota", month: "long" });

  const mismoMes = mesDe(inicio) === mesDe(finEfectivo);
  const dias = diffDiasCO(inicio, finEfectivo);

  return `Del ${mismoMes ? soloDia(inicio) : conMes(inicio)} al ${conMes(finEfectivo)} · ${dias} ${dias === 1 ? "día" : "días"}`;
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

function CardRelacionada({ historia: h }) {
  return (
    <article className="card-secundaria card-relacionada">
      <div className="card-header-tags">
        <span className="tag">
          {h.n_medios} {h.n_medios === 1 ? "medio" : "medios"}
        </span>
        <span className="tag">
          {h.n_articulos} {h.n_articulos === 1 ? "captura" : "capturas"}
        </span>
        <span className="historia-fecha">
          {fechaRango(h.fecha_inicio, h.fecha_fin)}
        </span>
      </div>
      <h3 className="card-titulo card-titulo-sm">
        <Link href={`/historia/${h.id}`}>{h.titulo}</Link>
      </h3>
      <p className="card-rel-meta">
        {h.n_especificas} {h.n_especificas === 1 ? "actor" : "actores"} en común
      </p>
    </article>
  );
}

// ── Página ────────────────────────────────────────────────────────────────────

export default async function Historia({ params }) {
  // ── Q1: la historia + sus representantes por URL (story_articles) ──
  // story_articles es caché derivada del clustering: 1 fila por URL (la última
  // captura), única fuente de los scores y es_ancla. Trae el representante
  // COMPLETO para servir de piso si la Q2 del historial falla.
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

  // Scores + es_ancla viven SOLO en story_articles, indexados por URL (el átomo
  // del clustering). Guardamos también el representante completo como fallback.
  const metaPorUrl = new Map();
  const representantes = [];
  for (const sa of story.story_articles ?? []) {
    const art = sa.articles;
    if (!art) continue;
    const meta = {
      medio_slug:        art.outlets?.slug,
      medio_nombre:      art.outlets?.nombre,
      es_ancla:          sa.es_ancla,
      score_neutralidad: sa.score_neutralidad,
      score_cobertura:   sa.score_cobertura,
      score_divergencia: sa.score_divergencia,
    };
    metaPorUrl.set(art.url, meta);
    representantes.push({
      article_id:    art.id,
      url:           art.url,
      hash_sha256:   art.hash_sha256,
      fecha_captura: art.fecha_captura,
      titulo:        art.titulo,
      subtitulo:     art.subtitulo,
      es_parcial:    art.es_parcial,
      tipo:          art.tipo,
      seccion:       art.seccion,
      ...meta,
    });
  }

  // ── Q2: el historial completo de ediciones ──
  // articles es inmutable y conserva TODAS las capturas (mismo url, hash
  // distinto = edición editorial o re-extracción nuestra). El colapso por URL
  // del clustering (BITACORA 2026-06-23) las dejó fuera de story_articles, lo
  // que rompió la cronología de ediciones. Las recuperamos AQUÍ, en la capa de
  // presentación, sin tocar clustering ni esquema: colapsarCluster.js ya sabe
  // agrupar capturas por url y detectar el cambio de título/subtítulo. Los
  // scores se heredan del representante de cada URL (no existen por captura).
  // Si la query falla o no devuelve nada, caemos a `representantes`.
  const urls = [...metaPorUrl.keys()];
  let capturas = representantes;

  if (urls.length) {
    const { data: historial, error: errH } = await supabase
      .from("articles")
      .select("id, url, titulo, subtitulo, fecha_captura, es_parcial, tipo, seccion, hash_sha256")
      .in("url", urls);

    if (!errH && historial?.length) {
      const recon = historial
        .filter((c) => metaPorUrl.has(c.url))
        .map((c) => {
          const m = metaPorUrl.get(c.url);
          return {
            article_id:        c.id,
            url:               c.url,
            medio_slug:        m.medio_slug,
            medio_nombre:      m.medio_nombre,
            hash_sha256:       c.hash_sha256,
            fecha_captura:     c.fecha_captura,
            titulo:            c.titulo,
            subtitulo:         c.subtitulo,
            es_parcial:        c.es_parcial,
            tipo:              c.tipo,
            seccion:           c.seccion,
            es_ancla:          m.es_ancla,
            score_neutralidad: m.score_neutralidad,
            score_cobertura:   m.score_cobertura,
            score_divergencia: m.score_divergencia,
          };
        });
      if (recon.length) capturas = recon;
    }
  }

  const articulos   = colapsarCluster(capturas);
  const tituloH     = tituloCanonico(articulos, story.titulo);
  const anclas      = articulos.filter((a) => a.es_ancla);
  const secundarias = articulos.filter((a) => !a.es_ancla);
  const labels      = etiquetarAnclas(articulos);
  // colapsarCluster ya devuelve articulos ordenados por fecha_primera_captura
  // asc (verificado arriba); el hilo se arma sobre ese mismo orden.
  const hilo        = construirHilo(articulos);

  // ── Q3: historias conectadas (story_relations, espejo dirigido) ──
  // El grafo es espejo: reescribir_stories inserta ambas direcciones, así que
  // filtrar por origen_id basta para traer todos los vecinos sin duplicar.
  // Tope 50 = guarda de cordura (el hub más denso medido tiene grado 13); el
  // recorte a 5 es de PRESENTACIÓN y vive en el render, no acá. Dos queries al
  // estilo de la casa para no depender del hint de FK (story_relations tiene dos
  // claves a stories).
  const { data: relRows } = await supabase
    .from("story_relations")
    .select("destino_id, n_especificas, coseno")
    .eq("origen_id", story.id)
    .order("n_especificas", { ascending: false })
    .order("coseno", { ascending: false })
    .limit(50);

  let relaciones = [];
  if (relRows?.length) {
    const destinoIds = relRows.map((r) => r.destino_id);
    const { data: relStories } = await supabase
      .from("stories")
      .select("id, titulo, n_medios, n_articulos, fecha_inicio, fecha_fin")
      .in("id", destinoIds);
    const byId = new Map((relStories ?? []).map((s) => [s.id, s]));
    relaciones = relRows
      .map((r) => {
        const s = byId.get(r.destino_id);
        return s ? { ...s, n_especificas: r.n_especificas, coseno: r.coseno } : null;
      })
      .filter(Boolean); // preserva el orden de relRows (n_esp desc, coseno desc)
  }

  const relPrincipales = relaciones.slice(0, 5);
  const relResto       = relaciones.slice(5);

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
            {rangoConDuracion(story.fecha_inicio, story.fecha_fin)}
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
        {/* Editorial: las 3 visibles son las más antiguas (orden cronológico asc);
            cuándo destilar qué mostrar primero es decisión de producto futura. */}
        <ol className={`hilo-cronologico${articulos.length > 3 ? " hilo-preview-fade" : ""}`}>
          {hilo.slice(0, 3).map(({ articulo: a, separador }) => (
            <Fragment key={a.url}>
              {separador && (
                <li className="hilo-separador-dia">{separador}</li>
              )}
              <li className="hilo-nodo">
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
            </Fragment>
          ))}
        </ol>
        {articulos.length > 3 && (
          <details className="timeline-mas">
            <summary>Ver {articulos.length - 3} momentos más</summary>
            <ol className="hilo-cronologico">
              {hilo.slice(3).map(({ articulo: a, separador }) => (
                <Fragment key={a.url}>
                  {separador && (
                    <li className="hilo-separador-dia">{separador}</li>
                  )}
                  <li className="hilo-nodo">
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
                </Fragment>
              ))}
            </ol>
          </details>
        )}
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
          <>
            <div className="bento-secundarias">
              {secundarias.slice(0, 2).map((a) => (
                <CardSecundaria key={a.url} articulo={a} />
              ))}
            </div>
            {secundarias.length > 2 && (
              <details className="versiones-mas">
                <summary>Ver {secundarias.length - 2} versiones más</summary>
                <div className="bento-secundarias">
                  {secundarias.slice(2).map((a) => (
                    <CardSecundaria key={a.url} articulo={a} />
                  ))}
                </div>
              </details>
            )}
          </>
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

      {/* ── HISTORIAS CONECTADAS ── */}
      <section className="historia-seccion">
        <h2 className="seccion-titulo">Historias conectadas</h2>
        {relaciones.length === 0 ? (
          <div className="placeholder-fase">
            <span className="placeholder-fase-label">Fase 2 · sin conexiones</span>
            <p className="placeholder-fase-texto">
              El pipeline no halló otras historias que compartan suficientes
              actores propios con esta. Una conexión aparece cuando dos historias
              del mismo tema (distinto hecho) comparten 3+ entidades específicas.
            </p>
          </div>
        ) : (
          <>
            <div className="bento-secundarias bento-relacionadas">
              {relPrincipales.map((h) => (
                <CardRelacionada key={h.id} historia={h} />
              ))}
            </div>
            {relResto.length > 0 && (
              <details className="relacionadas-mas">
                <summary>
                  y {relResto.length}{" "}
                  {relResto.length === 1 ? "historia más" : "historias más"}
                </summary>
                <ul className="relacionadas-mas-lista">
                  {relResto.map((h) => (
                    <li key={h.id}>
                      <Link href={`/historia/${h.id}`}>{h.titulo}</Link>
                      <span className="rel-mas-meta">
                        {h.n_especificas} en común
                      </span>
                    </li>
                  ))}
                </ul>
              </details>
            )}
          </>
        )}
      </section>
    </>
  );
}
