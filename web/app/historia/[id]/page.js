// TRAMA — Expediente de historia (clúster de Fase 2 + análisis de Fase 3).
// Server Component: solo lectura, revalidación c/5 min.
//
// CAMBIOS DE ESTA UNIDAD (frontend de Fase 3, Tier 1):
//  + Q5 a resumenes_dia: síntesis / hechos corroborados / solo_un_medio por día.
//  + Síntesis del día más reciente bajo el título (mitiga el título obsoleto).
//  + Sección "Lo que reportaron los medios": corroborado (fuerte) y un-solo-medio (débil).
//  + Modal por día, disparado desde chips y desde el separador de día del hilo.
//  – ELIMINADO el placeholder "Análisis de persuasión": el carril per-artículo está
//    cerrado y medido (Arquitectura §5, BITACORA 2026-07-17, prevalencia 0,15%). Ese
//    material NO existe y no va a existir; prometerlo en la página es prometer una
//    acusación que el proyecto decidió no hacer. Su heredero honesto es la comparación
//    inter-medio ("qué destaca cada medio"), que entra cuando `comparaciones` pase su
//    auditoría pendiente.
//  – ELIMINADO el placeholder "Reacciones": su fuente supuesta era `tipo='opinion'`,
//    que está medido como poco fiable (El Tiempo y El Colombiano dan 0% de opinión,
//    lo cual es falso). Su heredero es la extracción de citas atribuidas, unidad propia.
//  ~ Refactor: el nodo del hilo cronológico estaba duplicado literal entre la vista
//    previa y el "ver más". Se extrajo a <NodoHilo>. Presentación pura, sin cambio
//    de comportamiento; se hace ahora porque agregar el botón de día en dos copias
//    es exactamente cómo se desincronizan.
import Link from "next/link";
import { notFound } from "next/navigation";
import { supabase } from "@/lib/supabase";
import {
  colapsarCluster,
  tituloCanonico,
  etiquetarAnclas,
} from "@/lib/colapsarCluster";
import ModalDia from "@/app/components/ModalDia";

export const revalidate = 300;

// Cuántos hechos corroborados se muestran en la sección de portada antes de plegar.
// El resto vive en el modal del día, no repetido acá.
const HECHOS_VISIBLES = 3;

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

// ── Fechas de resumenes_dia: se leen como STRING, jamás con new Date() ────────
// `resumenes_dia.dia` es de tipo DATE (verificado en information_schema el
// 2026-08-22; la deuda de BITACORA que lo daba por TIMESTAMP es stale). PostgREST
// lo devuelve como "2026-07-20" pelado: ya ES el día-calendario de Bogotá que
// calculó el backend, sin hora ni zona que interpretar.
//
// Por eso NO se pasa por new Date(): una fecha sin hora no tiene zona horaria que
// convertir, y convertirla igual es un error de categoría — le resta el offset y
// la corre al día anterior. Es exactamente el bug que se encontró en
// _dia_bogota() del backend el 2026-08-22 (corrimiento de 1 día en el 87% del
// corpus). No lo repitamos en la capa de lectura: la cadena ya es la clave.
function claveDiaResumen(dia) {
  return String(dia).slice(0, 10);
}

// Para MOSTRAR esa clave en español. Se ancla al mediodía UTC a propósito: con
// "T12:00:00Z" ninguna conversión de zona (Bogotá es UTC-5) puede cruzar la
// medianoche y cambiar el día. Anclarlo a medianoche sí lo cruzaría.
function fechaLargaDesdeClave(clave) {
  const texto = new Date(clave + "T12:00:00Z")
    .toLocaleDateString("es-CO", {
      timeZone: "America/Bogota", weekday: "long", day: "numeric", month: "long",
    })
    .replace(",", "");
  return texto.charAt(0).toUpperCase() + texto.slice(1);
}

function fechaCortaDesdeClave(clave) {
  return new Date(clave + "T12:00:00Z").toLocaleDateString("es-CO", {
    timeZone: "America/Bogota", day: "numeric", month: "short",
  });
}

// Fecha corta para el índice de trama, ej. "16 jul".
function fechaCortaCO(ts) {
  return new Date(ts).toLocaleDateString("es-CO", {
    timeZone: "America/Bogota", day: "numeric", month: "short",
  });
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

// Día de publicación del artículo, YA CALCULADO POR LA BASE (vista articles_dia).
// NO se recalcula acá a propósito: el guard de medianoche vive en UN solo lugar
// del lado del servidor. Reimplementarlo en JS metería una tercera copia de una
// lógica que ya mordió dos veces, en la capa donde peor se audita.
function diaDeArticulo(a) {
  return a.dia_publicacion ? String(a.dia_publicacion).slice(0, 10) : null;
}

// Construye el hilo desde la UNIÓN de (días con artículos ∪ días con análisis).
//
// POR QUÉ UNIÓN Y NO EMPAREJAMIENTO (medido 2026-08-26): con el separador
// emparejando contra resumenPorDia, 11 análisis de 280 no encontraban día en el
// hilo y su botón simplemente no se dibujaba. Un emparejamiento tiene que
// acertar; una unión no puede perder. Consecuencia estructural: el conjunto de
// días del hilo CONTIENE a `dias` por construcción, no por medición — y eso es
// lo que autoriza (en una unidad posterior, no en esta) a retirar los chips.
//
// Devuelve también `sinDia` para que la degradación sea VISIBLE: un artículo sin
// dia_publicacion no se descarta en silencio.
function construirHiloUnificado(articulosDesc, dias) {
  const porDia = new Map();
  const sinDia = [];

  for (const a of articulosDesc) {
    const d = diaDeArticulo(a);
    if (!d) { sinDia.push(a); continue; }
    if (!porDia.has(d)) porDia.set(d, []);
    porDia.get(d).push(a);
  }

  const claves = new Set([
    ...porDia.keys(),
    ...dias.map((d) => claveDiaResumen(d.dia)),
  ]);

  // Descendente por clave ISO (yyyy-mm-dd ordena lexicográficamente = cronológicamente).
  const ordenadas = [...claves].sort((x, y) => (x < y ? 1 : x > y ? -1 : 0));

  return {
    bloques: ordenadas.map((clave) => ({ clave, articulos: porDia.get(clave) ?? [] })),
    sinDia,
  };
}

// Rango + duración del clúster para el encabezado, ej. "Del 16 al 21 de julio
// · 5 días".
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

// ── Sub-componentes de Fase 3 ─────────────────────────────────────────────────

// Insignia de medio reutilizando las tintas de archivo ya asignadas por medio.
function Medio({ slug, nombrePorSlug }) {
  return (
    <span className={`tag tag-medio medio-${slug}`}>
      {nombrePorSlug.get(slug) ?? slug}
    </span>
  );
}

// Nota de método. DISCLOSURE es principio del proyecto, no adorno: publicar
// derivados de IA sobre opacidad mediática sin declarar el método sería la misma
// opacidad que Trama critica.
function NotaMetodo({ resumen, variante = "" }) {
  return (
    <p className={`metodo-nota ${variante}`}>
      Generado automáticamente ({resumen.modelo ?? "LLM"}
      {resumen.prompt_version ? ` · prompt ${resumen.prompt_version}` : ""}) a partir
      de los artículos de ese día. Las citas se verifican como copia literal del
      original antes de publicarse.
    </p>
  );
}

// UN hecho corroborado.
//
// PROBLEMA DE DISEÑO, RESUELTO ACÁ: un "hecho" en resumenes_dia NO tiene enunciado
// propio — es solo una lista de spans verbatim de medios distintos que dicen lo
// mismo. No hay una frase "el hecho" que mostrar, y redactarla nosotros sería
// fabricación: exactamente lo que el gate verbatim existe para impedir.
// Solución: se muestra UN span como enunciado visible, entre comillas y atribuido a
// su medio, y al lado los medios que lo corroboran. La regla de selección es
// determinista (el span más corto, y a igual largo el slug menor) para que el
// mismo hecho se vea igual en cada render. Trama nunca habla en voz propia acá:
// solo dice quiénes coinciden.
function HechoCorroborado({ hecho, nombrePorSlug }) {
  const spans = (hecho?.spans ?? []).filter((s) => s?.span && s?.medio);
  if (!spans.length) return null;

  const ordenados = [...spans].sort(
    (a, b) => a.span.length - b.span.length || (a.medio < b.medio ? -1 : 1)
  );
  const principal = ordenados[0];
  const medios = [...new Set(ordenados.map((s) => s.medio))];
  const otros = ordenados.slice(1);

  return (
    <li className="hecho">
      <blockquote className="hecho-enunciado">
        «{principal.span}»
      </blockquote>
      <div className="hecho-medios">
        <span className="hecho-conteo">
          {medios.length} {medios.length === 1 ? "medio" : "medios"} coinciden
        </span>
        {medios.map((m) => (
          <Medio key={m} slug={m} nombrePorSlug={nombrePorSlug} />
        ))}
      </div>
      {otros.length > 0 && (
        <details className="hecho-citas">
          <summary>Ver las {ordenados.length} citas literales</summary>
          <ul className="hecho-citas-lista">
            {ordenados.map((s, i) => (
              <li key={`${s.medio}-${i}`}>
                <Medio slug={s.medio} nombrePorSlug={nombrePorSlug} />
                <span className="hecho-cita-texto">«{s.span}»</span>
              </li>
            ))}
          </ul>
        </details>
      )}
    </li>
  );
}

// Un ítem de solo_un_medio.
//
// FRASEO NO NEGOCIABLE: el gate verbatim verifica que el span EXISTE en ese medio.
// NO verifica que esté AUSENTE en los demás — eso el pipeline no lo prueba. Decir
// "El Tiempo omitió X" sería una afirmación refutable en diez segundos por
// cualquiera (el riesgo registrado: "no acusa, pero puede mentir"). Por eso el
// rótulo es descriptivo — dónde apareció —, nunca acusatorio — quién lo calló.
function ItemUnicoMedio({ item, nombrePorSlug }) {
  if (!item?.span || !item?.medio) return null;
  return (
    <li className="unico-item">
      <Medio slug={item.medio} nombrePorSlug={nombrePorSlug} />
      <span className="unico-texto">«{item.span}»</span>
    </li>
  );
}

// Contenido completo de UN día. Es lo que va dentro del modal: se renderiza en el
// servidor y se le pasa a ModalDia como children (ModalDia no consulta nada).
function ContenidoDia({ resumen, nombrePorSlug }) {
  const hechos = resumen.hechos_corroborados ?? [];
  const unicos = resumen.solo_un_medio ?? [];
  const medios = resumen.medios ?? [];
  const nArts  = (resumen.article_ids ?? []).length;

  return (
    <div className="dia-contenido">
      <p className="dia-medios-fila">
        {nArts > 0 && <>{nArts} {nArts === 1 ? "nota" : "notas"} de </>}
        {medios.length} {medios.length === 1 ? "medio" : "medios"} este día:{" "}
        {medios.map((m) => (
          <Medio key={m} slug={m} nombrePorSlug={nombrePorSlug} />
        ))}
      </p>

      {resumen.sintesis && (
        <div className="sintesis-bloque">
          <h3 className="sub-titulo">Qué se movió ese día</h3>
          <p className="sintesis-texto">{resumen.sintesis}</p>
        </div>
      )}

      {hechos.length > 0 ? (
        <div className="dia-seccion">
          <h3 className="sub-titulo">En lo que coinciden</h3>
          <ul className="hechos-lista">
            {hechos.map((h, i) => (
              <HechoCorroborado key={i} hecho={h} nombrePorSlug={nombrePorSlug} />
            ))}
          </ul>
        </div>
      ) : (
        <p className="gris-archivo dia-vacio">
          {medios.length < 2
            ? "Un solo medio cubrió este día: no hay con qué corroborar."
            : "Ningún hecho superó la corroboración de dos o más medios este día."}
        </p>
      )}

      {unicos.length > 0 && (
        <div className="dia-seccion">
          <h3 className="sub-titulo">Aparece en un solo medio</h3>
          <p className="sub-nota">
            Reportado por una sola de las coberturas de ese día. No significa que los
            demás lo hayan callado: significa que el análisis no lo encontró en ellos.
          </p>
          <ul className="unico-lista">
            {unicos.map((u, i) => (
              <ItemUnicoMedio key={i} item={u} nombrePorSlug={nombrePorSlug} />
            ))}
          </ul>
        </div>
      )}

      <NotaMetodo resumen={resumen} />
    </div>
  );
}

// ── Sub-componentes existentes ────────────────────────────────────────────────

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

function NodoTrama({ h, esActual }) {
  return (
    <li className={`trama-nodo${esActual ? " trama-nodo-actual" : ""}`}>
      <span className="trama-fecha">{fechaCortaCO(h.fecha_inicio)}</span>
      <div className="trama-titulo-fila">
        {esActual ? (
          <span className="trama-titulo">{h.titulo}</span>
        ) : (
          <Link href={`/historia/${h.id}`} className="trama-titulo">
            {h.titulo}
          </Link>
        )}
        {esActual && <span className="trama-tag-actual">Estás aquí</span>}
      </div>
      <span className="trama-medios">
        {h.n_medios} {h.n_medios === 1 ? "medio" : "medios"}
      </span>
    </li>
  );
}

function IndiceTrama({ tramaOrdenada, tramaColapsada, storyId }) {
  const colapsable = tramaOrdenada.length > tramaColapsada.length;
  return (
    <section className="historia-seccion trama-seccion">
      <h2 className="seccion-titulo">De la misma trama</h2>
      <p className="trama-intro">
        Esta historia es un capítulo de una trama mayor, separada en{" "}
        {tramaOrdenada.length} sub-hechos.
      </p>
      <ol className={`trama-indice${colapsable ? " trama-preview" : ""}`}>
        {tramaColapsada.map((h) => (
          <NodoTrama key={h.id} h={h} esActual={h.id === storyId} />
        ))}
      </ol>
      {colapsable && (
        <details className="trama-mas">
          <summary>Ver los {tramaOrdenada.length} sub-hechos completos</summary>
          <ol className="trama-indice">
            {tramaOrdenada.map((h) => (
              <NodoTrama key={h.id} h={h} esActual={h.id === storyId} />
            ))}
          </ol>
        </details>
      )}
    </section>
  );
}

// Nodo del hilo cronológico. Extraído de las dos copias literales que había
// (vista previa y "ver más"): con el botón de día encima, mantener dos copias
// sincronizadas a mano era cuestión de tiempo.
function NodoHilo({ a }) {
  return (
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
          <span className="hilo-hora">{horaCO(a.fecha_primera_captura)}</span>
        )}
        <Link
          href={`/medio/${a.medio_slug}`}
          className={`tag tag-medio medio-${a.medio_slug}`}
        >
          {a.medio_nombre}
        </Link>
        {a.seccion && <span className="tag tag-seccion">{a.seccion}</span>}
      </div>

      <div className="hilo-nodo-titulo">
        {a.titulo_cambio ? (
          <>
            <span className="hilo-titulo-tachado">{a.titulo_original}</span>{" "}
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
  );
}

// Un día del hilo: su encabezado, su botón de análisis si existe, y sus notas.
//
// EL CASO NUEVO (articulos.length === 0) es la contrapartida de la unión: un día
// puede tener análisis y no tener notas en ESTA historia — el clustering
// re-particiona en cada corrida y una nota puede haber quedado en otro clúster.
// Se dice explícitamente en vez de dibujar un separador huérfano: para una
// hemeroteca forense, que el agrupamiento se movió ES información, no un defecto
// que esconder.
function BloqueDia({ bloque, resumen, nombrePorSlug }) {
  const { clave, articulos } = bloque;
  const nMedios = (resumen?.medios ?? []).length;

  return (
    <>
      <li className="hilo-separador-dia">
        <span className="hilo-separador-texto">{fechaLargaDesdeClave(clave)}</span>
        <span className="hilo-separador-conteo">
          {articulos.length} {articulos.length === 1 ? "nota" : "notas"}
          {nMedios > 0 && ` · ${nMedios} ${nMedios === 1 ? "medio" : "medios"}`}
        </span>
        {resumen && (
          <ModalDia
            etiquetaBoton="Hechos del día"
            tituloModal={fechaLargaDesdeClave(clave)}
          >
            <ContenidoDia resumen={resumen} nombrePorSlug={nombrePorSlug} />
          </ModalDia>
        )}
      </li>

      {articulos.length === 0 ? (
        <li className="hilo-dia-vacio gris-archivo">
          Hay análisis de este día, pero sus notas ya no están en esta historia:
          una corrida posterior del agrupamiento las reasignó.
        </li>
      ) : (
        articulos.map((a) => <NodoHilo key={a.url} a={a} />)
      )}
    </>
  );
}

// ── Página ────────────────────────────────────────────────────────────────────

export default async function Historia({ params }) {
  // ── Q1: la historia + sus representantes por URL (story_articles) ──
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

  const metaPorUrl = new Map();
  const representantes = [];
  // Slug -> nombre legible del medio. Fase 3 devuelve SLUGS (es el contrato de sus
  // prompts); las insignias necesitan el nombre. Se arma desde los outlets que ya
  // vienen en Q1 — cero queries extra.
  const nombrePorSlug = new Map();

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
    if (meta.medio_slug) nombrePorSlug.set(meta.medio_slug, meta.medio_nombre ?? meta.medio_slug);
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
  const urls = [...metaPorUrl.keys()];
  let capturas = representantes;

  if (urls.length) {
    const { data: historial, error: errH } = await supabase
      .from("articles_dia")
      .select("id, url, titulo, subtitulo, fecha_captura, es_parcial, tipo, seccion, hash_sha256, dia_publicacion")
      .in("url", urls);

    if (!errH && historial?.length) {
      const recon = historial
        .filter((c) => metaPorUrl.has(c.url))
        .map((c) => {
          const m = metaPorUrl.get(c.url);
          return {
            article_id:        c.id,
            url:               c.url,
            dia_publicacion:   c.dia_publicacion,
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
  const articulosDesc = [...articulos].reverse();

  // ── Q3: historias conectadas (story_relations, espejo dirigido) ──
  const { data: relRows } = await supabase
    .from("story_relations")
    .select("destino_id, n_especificas, coseno")
    .eq("origen_id", story.id)
    .eq("tipo", "tematica")
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
      .filter(Boolean);
  }

  const relPrincipales = relaciones.slice(0, 5);
  const relResto       = relaciones.slice(5);

  // ── Q4: hermanas del beat-split (story_relations tipo='misma_trama') ──
  const { data: tramaRows } = await supabase
    .from("story_relations")
    .select("destino_id")
    .eq("origen_id", story.id)
    .eq("tipo", "misma_trama");

  let tramaOrdenada = [];
  let tramaColapsada = [];
  if (tramaRows?.length) {
    const hermanaIds = tramaRows.map((r) => r.destino_id);
    const { data: hermanas } = await supabase
      .from("stories")
      .select(`
        id, titulo, fecha_inicio, n_medios, n_articulos,
        story_articles ( score_neutralidad, articles ( titulo, tipo ) )
      `)
      .in("id", hermanaIds);

    const hermanasConTitulo = (hermanas ?? []).map((s) => {
      const arts = (s.story_articles ?? [])
        .map((sa) => ({
          tipo:              sa.articles?.tipo,
          titulo:            sa.articles?.titulo,
          score_neutralidad: sa.score_neutralidad,
        }))
        .filter((a) => a.titulo);
      return {
        id:            s.id,
        fecha_inicio:  s.fecha_inicio,
        n_medios:      s.n_medios,
        n_articulos:   s.n_articulos,
        titulo:        tituloCanonico(arts, s.titulo),
      };
    });

    const actual = {
      id: story.id,
      titulo: tituloH,
      fecha_inicio: story.fecha_inicio,
      n_medios: story.n_medios,
      n_articulos: story.n_articulos,
    };
    const conjunto = [actual, ...hermanasConTitulo];

    if (conjunto.length >= 2) {
      tramaOrdenada = [...conjunto].sort((a, b) => {
        const diaA = claveDiaCO(a.fecha_inicio);
        const diaB = claveDiaCO(b.fecha_inicio);
        if (diaA !== diaB) return diaA < diaB ? -1 : 1;
        if (b.n_medios !== a.n_medios) return b.n_medios - a.n_medios;
        return a.id < b.id ? -1 : a.id > b.id ? 1 : 0;
      });

      if (tramaOrdenada.length > 3) {
        const porCobertura = [...tramaOrdenada].sort((a, b) => {
          if (b.n_medios !== a.n_medios) return b.n_medios - a.n_medios;
          if (b.n_articulos !== a.n_articulos) return b.n_articulos - a.n_articulos;
          return a.id < b.id ? -1 : a.id > b.id ? 1 : 0;
        });
        const top3 = porCobertura.slice(0, 3);
        if (!top3.some((h) => h.id === actual.id)) top3[2] = actual;
        const idsColapsados = new Set(top3.map((h) => h.id));
        tramaColapsada = tramaOrdenada.filter((h) => idsColapsados.has(h.id));
      } else {
        tramaColapsada = tramaOrdenada;
      }
    }
  }

  // ── Q5: análisis de Fase 3 por día (resumenes_dia) ──
  //
  // Nota de expectativa (TRASPASO 2026-08-22): hoy solo las ~68 historias ACTIVAS
  // tienen filas acá; el histórico (~750) todavía no se ha procesado. La mayoría de
  // los expedientes va a renderizar el estado vacío, y eso es correcto, no un bug.
  //
  // `dia` es DATE (verificado 2026-08-22). Acá no hace falta filtro de fecha en
  // absoluto — se traen todos los días de la historia y se ordenan en la base.
  const { data: resumenesDia } = await supabase
    .from("resumenes_dia")
    .select("dia, sintesis, hechos_corroborados, solo_un_medio, medios, article_ids, modelo, prompt_version")
    .eq("story_id", story.id)
    .order("dia", { ascending: false });

  const dias = resumenesDia ?? [];
  const diaReciente = dias[0] ?? null;

  // Índice día-calendario -> análisis, para colgar el botón del separador del hilo.
  //
  // ADVERTENCIA MEDIDA (2026-08-22): la línea de tiempo separa por
  // fecha_primera_captura (cuándo corrió NUESTRO cron) y Fase 3 trocea por
  // fecha_publicacion (el día periodístico). Se midió 95,6% de divergencia, de la
  // cual 87,4% es un corrimiento de exactamente 1 día causado por un bug de
  // _dia_bogota() en el backend (convierte de zona una fecha sin hora). Aun
  // arreglado ese bug, los dos calendarios NO son el mismo. Por eso el botón del
  // separador es
  // OPORTUNISTA, no la única puerta: la fila de chips "Análisis por día" de más
  // abajo lista SIEMPRE los días completos. Si el matching falla, no se pierde ni
  // un día de análisis; solo se pierde el atajo. Fallar en silencio no es opción.
  const resumenPorDia = new Map(dias.map((d) => [claveDiaResumen(d.dia), d]));

  const { bloques, sinDia } = construirHiloUnificado(articulosDesc, dias);

  const hechosRecientes = diaReciente?.hechos_corroborados ?? [];
  const unicosRecientes = diaReciente?.solo_un_medio ?? [];
  const claveReciente   = diaReciente ? claveDiaResumen(diaReciente.dia) : null;

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

      {/* ── LO ÚLTIMO ──
          Mitigación del TÍTULO OBSOLETO: el título de una historia que mutó a lo
          largo de días no existe como titular de ningún artículo. No se puede
          arreglar en el frontend (haría falta el digest de arco, unidad de
          backend). Lo que sí se puede: poner el estado ACTUAL del hecho justo
          debajo, para que el lector no dependa del título. Este bloque es el
          hueco reservado del digest: cuando exista, entra acá sin rediseñar. */}
      {diaReciente?.sintesis && (
        <div className="ultimo-bloque">
          <span className="ultimo-label">
            Lo último · {fechaLargaDesdeClave(claveReciente)}
          </span>
          <p className="ultimo-texto">{diaReciente.sintesis}</p>
          <NotaMetodo resumen={diaReciente} variante="metodo-nota-compacta" />
        </div>
      )}

      {/* ── DE LA MISMA TRAMA (hermanas del beat-split) ── */}
      {tramaOrdenada.length >= 2 && (
        <IndiceTrama
          tramaOrdenada={tramaOrdenada}
          tramaColapsada={tramaColapsada}
          storyId={story.id}
        />
      )}

      {/* ── LO QUE REPORTARON LOS MEDIOS ──
          Dos niveles de confianza, en orden de fuerza: lo corroborado por 2+ medios
          (cada cita verificada literal contra su original) y lo que apareció en uno
          solo. Acotado AL DÍA MÁS RECIENTE a propósito: los días NO se fusionan.
          Mezclar hechos de días distintos en una lista sola reintroduce la deriva
          causal que el troceo por día eliminó por construcción (el modo de falla
          Pizarro). El resto de los días vive en su propio modal, con su fecha. */}
      {diaReciente && (
        <section className="historia-seccion">
          <h2 className="seccion-titulo">Lo que reportaron los medios</h2>
          <p className="seccion-alcance">
            Del {fechaLargaDesdeClave(claveReciente).toLowerCase()} — el día más
            reciente con análisis.
            {dias.length > 1 && " Los demás días, más abajo."}
          </p>

          {hechosRecientes.length > 0 ? (
            <>
              <ul className="hechos-lista">
                {hechosRecientes.slice(0, HECHOS_VISIBLES).map((h, i) => (
                  <HechoCorroborado key={i} hecho={h} nombrePorSlug={nombrePorSlug} />
                ))}
              </ul>
              {hechosRecientes.length > HECHOS_VISIBLES && (
                <details className="hechos-mas">
                  <summary>
                    Ver {hechosRecientes.length - HECHOS_VISIBLES} hechos más de este día
                  </summary>
                  <ul className="hechos-lista">
                    {hechosRecientes.slice(HECHOS_VISIBLES).map((h, i) => (
                      <HechoCorroborado
                        key={i + HECHOS_VISIBLES}
                        hecho={h}
                        nombrePorSlug={nombrePorSlug}
                      />
                    ))}
                  </ul>
                </details>
              )}
            </>
          ) : (
            <p className="gris-archivo">
              {(diaReciente.medios ?? []).length < 2
                ? "Un solo medio cubrió el día más reciente: no hay con qué corroborar."
                : "Ningún hecho superó la corroboración de dos o más medios ese día."}
            </p>
          )}

          {unicosRecientes.length > 0 && (
            <div className="unico-bloque">
              <h3 className="sub-titulo">Aparece en un solo medio</h3>
              <p className="sub-nota">
                Reportado por una sola de las coberturas de ese día. No significa que
                los demás lo hayan callado: significa que el análisis no lo encontró
                en ellos.
              </p>
              <ul className="unico-lista">
                {unicosRecientes.slice(0, 3).map((u, i) => (
                  <ItemUnicoMedio key={i} item={u} nombrePorSlug={nombrePorSlug} />
                ))}
              </ul>
            </div>
          )}
        </section>
      )}

      {/* ── ANÁLISIS POR DÍA (chips) ──
          Superficie canónica y completa: siempre están TODOS los días analizados,
          independientemente de si el separador del hilo logró emparejarlos. */}
      {dias.length > 1 && (
        <section className="historia-seccion">
          <h2 className="seccion-titulo">Análisis por día</h2>
          <p className="seccion-alcance">
            Cada día es una foto independiente: se analiza solo con lo que se publicó
            ese día, sin encadenarlo con los otros.
          </p>
          <div className="dias-chips">
            {dias.map((d) => {
              const clave = claveDiaResumen(d.dia);
              const nMedios = (d.medios ?? []).length;
              const nHechos = (d.hechos_corroborados ?? []).length;
              return (
                <ModalDia
                  key={clave}
                  claseBoton="dia-chip"
                  etiquetaBoton={`${fechaCortaDesdeClave(clave)} · ${nMedios} ${
                    nMedios === 1 ? "medio" : "medios"
                  }${nHechos ? ` · ${nHechos} ${nHechos === 1 ? "hecho" : "hechos"}` : ""}`}
                  tituloModal={fechaLargaDesdeClave(clave)}
                >
                  <ContenidoDia resumen={d} nombrePorSlug={nombrePorSlug} />
                </ModalDia>
              );
            })}
          </div>
        </section>
      )}

      {/* ── HILO CRONOLÓGICO ── */}
      <section className="historia-seccion">
        <h2 className="seccion-titulo">Línea de tiempo</h2>
        {/* NOTA DE ALCANCE — redactada A PROPÓSITO sin porcentaje.
            El primer borrador decía "el 95% del archivo no trae hora". Es cierto
            hoy y será falso pronto: medido 2026-08-26, el 98,95% de lo capturado
            en los últimos 3 días SÍ trae hora (el PR #19 funciona), y el corpus
            cruza el 50% con hora hacia finales de octubre. Una cifra que envejece
            en semanas no va en el código. Además engañaría: el 95% describe el
            archivo entero, pero en una historia RECIENTE la proporción sin hora
            es ~1%. */}
        <p className="seccion-alcance">
          Agrupada por día de publicación del medio. Las horas mostradas son de
          captura de Trama, no de publicación: buena parte del archivo histórico
          no trae hora, solo fecha.
        </p>

        <ol className={`hilo-cronologico${bloques.length > 1 ? " hilo-preview-fade" : ""}`}>
          {bloques.slice(0, 1).map((b) => (
            <BloqueDia
              key={b.clave}
              bloque={b}
              resumen={resumenPorDia.get(b.clave)}
              nombrePorSlug={nombrePorSlug}
            />
          ))}
        </ol>

        {bloques.length > 1 && (
          <details className="timeline-mas">
            <summary>
              Ver {bloques.length - 1} {bloques.length - 1 === 1 ? "día más" : "días más"}
            </summary>
            <ol className="hilo-cronologico">
              {bloques.slice(1).map((b) => (
                <BloqueDia
                  key={b.clave}
                  bloque={b}
                  resumen={resumenPorDia.get(b.clave)}
                  nombrePorSlug={nombrePorSlug}
                />
              ))}
            </ol>
          </details>
        )}

        {/* RUTA DE DEGRADACIÓN, REPORTADA. Una defensa que falla en silencio es
            peor que el bug: si la vista articles_dia no está aplicada o
            colapsarCluster no propaga el campo, estas notas se quedarían fuera
            del hilo sin que nadie lo note. */}
        {sinDia.length > 0 && (
          <>
            <p className="gris-archivo">
              {sinDia.length} {sinDia.length === 1 ? "nota" : "notas"} sin día de
              publicación resuelto. Se listan aparte para no omitirlas.
            </p>
            <ol className="hilo-cronologico">
              {sinDia.map((a) => <NodoHilo key={a.url} a={a} />)}
            </ol>
          </>
        )}
      </section>

      {/* ── VERSIONES (BENTO) ── */}
      <section className="historia-seccion">
        <h2 className="seccion-titulo">Versiones</h2>

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

      {/* Los placeholders de "Análisis de persuasión" y "Reacciones" se retiraron en
          esta unidad. Ver cabecera del archivo y BITACORA 2026-08-22 para el porqué
          y para cuáles son sus herederos. No re-agregarlos sin datos detrás. */}

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
