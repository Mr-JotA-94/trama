// TRAMA — lógica de colapso de clúster.
// El átomo es la url, no el medio ni la captura individual.
// El pipeline entrega múltiples capturas del mismo artículo (mismo url,
// hash distinto = edición editorial o re-extracción nuestra) como filas
// separadas en story_articles. Esta función las agrupa en artículos.
//
// "editada" solo si título o bajada cambiaron entre capturas consecutivas.
// Cambio solo de cuerpo/hash → "N capturas" sin afirmar edición editorial.
// (No distinguimos edición del medio de nuestra re-extracción del 2026-06-14.)

/**
 * @typedef {{
 *   article_id: string,
 *   url: string, medio_slug: string, medio_nombre: string,
 *   hash_sha256: string, fecha_captura: string,
 *   titulo: string, subtitulo: string|null, es_parcial: boolean,
 *   es_ancla: boolean, score_neutralidad: number,
 *   score_cobertura: number, score_divergencia: number,
 *   tipo: string, seccion: string|null
 * }} Captura
 */

/**
 * Colapsa filas crudas de un clúster en artículos identificados por url.
 * @param {Captura[]} capturas
 * @returns {Array} artículos colapsados, ordenados por fecha_primera_captura asc
 */
export function colapsarCluster(capturas) {
  const porUrl = new Map();
  for (const c of capturas) {
    if (!porUrl.has(c.url)) porUrl.set(c.url, []);
    porUrl.get(c.url).push(c);
  }

  const articulos = [];
  for (const [url, caps] of porUrl) {
    caps.sort((a, b) => new Date(a.fecha_captura) - new Date(b.fecha_captura));
    const primera = caps[0];
    const ultima  = caps[caps.length - 1];

    let editada      = false;
    let titulo_cambio = false;
    for (let i = 1; i < caps.length; i++) {
      if (caps[i].titulo !== caps[i - 1].titulo) titulo_cambio = true;
      if (caps[i].titulo !== caps[i - 1].titulo ||
          caps[i].subtitulo !== caps[i - 1].subtitulo) editada = true;
    }

    articulos.push({
      url,
      article_id:            ultima.article_id,
      medio_slug:            ultima.medio_slug,
      medio_nombre:          ultima.medio_nombre,
      titulo:                ultima.titulo,
      subtitulo:             ultima.subtitulo,
      es_parcial:            ultima.es_parcial,
      tipo:                  ultima.tipo,
      seccion:               ultima.seccion,
      score_neutralidad:     ultima.score_neutralidad,
      score_cobertura:       ultima.score_cobertura,
      score_divergencia:     ultima.score_divergencia,
      dia_publicacion:       ultima.dia_publicacion,
      es_ancla:              caps.some(c => c.es_ancla),
      editada,
      titulo_cambio,
      titulo_original:       titulo_cambio ? primera.titulo : null,
      fecha_primera_captura: primera.fecha_captura,
      fecha_ultima_captura:  ultima.fecha_captura,
      n_capturas:            caps.length,
      capturas:              caps,
    });
  }

  articulos.sort((a, b) =>
    new Date(a.fecha_primera_captura) - new Date(b.fecha_primera_captura)
  );
  return articulos;
}

// Detecta titular-cita: cláusula entre comillas adyacente a ":" — el patrón
// «"cita": Actor» o «Actor afirmó: "cita"». NO usa verbo de habla suelto (eso
// sobre-disparaba con alias entre comillas, p.ej. 'Walter Mendoza'). Medido
// sobre el banco: 4/4 citas reales, 0 falsos positivos.
const RE_CITA_DELANTE = /^\s*["«“'‘].{15,}?["»”'’]\s*:/;
const RE_CITA_ATRAS   = /:\s*["«“'‘].{15,}/;

export function esTituloCita(titulo) {
  const t = (titulo || "").trim();
  return RE_CITA_DELANTE.test(t) || RE_CITA_ATRAS.test(t);
}

/**
 * Título canónico del clúster: el titular noticia más neutral que NO sea cita
 * declarativa. Un titular-cita adopta el encuadre del actor como nombre del
 * hecho — lo que Trama señala, no lo que narra. Si TODAS las noticias son cita,
 * cae al de mayor neutralidad (degradación elegante: no inventa títulos).
 * @param {ReturnType<typeof colapsarCluster>} articulos
 * @param {string} fallback
 */
export function tituloCanonico(articulos, fallback = "Historia sin título") {
  const noticias = articulos.filter(a => a.tipo === "noticia");
  if (!noticias.length) return fallback;
  const noCita = noticias.filter(a => !esTituloCita(a.titulo));
  const pool = noCita.length ? noCita : noticias;
  return pool.reduce((max, a) =>
    a.score_neutralidad > max.score_neutralidad ? a : max
  ).titulo;
}

/**
 * Asigna etiquetas de rol a las cards ancla:
 *   argmax(neut × cob) → "más neutral + completa"
 *   argmax(div)        → "mayor divergencia"
 * Devuelve Map<url, string>. Solo incluye urls con es_ancla=true.
 * @param {ReturnType<typeof colapsarCluster>} articulos
 */
export function etiquetarAnclas(articulos) {
  const anclas = articulos.filter(a => a.es_ancla);
  if (!anclas.length) return new Map();

  const conNeutCob = anclas.reduce((max, a) =>
    (a.score_neutralidad * a.score_cobertura) >
    (max.score_neutralidad * max.score_cobertura) ? a : max
  );
  const conDiv = anclas.reduce((max, a) =>
    a.score_divergencia > max.score_divergencia ? a : max
  );

  const labels = new Map();
  labels.set(conNeutCob.url, "más neutral + completa");
  if (conDiv.url !== conNeutCob.url) labels.set(conDiv.url, "mayor divergencia");
  return labels;
}
