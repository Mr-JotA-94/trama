# BITÁCORA — TRAMA

Registro de decisiones, operaciones sobre datos y deuda técnica conocida.
No es documentación de arquitectura (eso vive en ARQUITECTURA.md) ni migraciones
(esas viven en supabase/migrations/). Aquí va lo que pasó y por qué, para que el
yo-del-futuro entienda el estado actual sin tener que reconstruirlo de memoria.

---

## Operaciones sobre datos (truncates y borrados)

Regla de Trama: el archivo es inmutable, nada se borra. Los truncates de abajo
ocurrieron SOLO durante la fase de calibración (Fase 1), cuando el archivo aún no
tenía valor histórico. A partir de Fase 2, truncar deja de ser aceptable: los
cambios de esquema se hacen con migraciones que preservan datos.

- **2026-06-21** — backfill + reclustering de los 663 pendientes (NO es truncate).
  Los ~663 artículos capturados por el crawler desde 06-18 tenían embedding NULL;
  backfill los rellenó (entidades + embedding) vía UPDATE idempotente. Banco:
  982 → 1645 artículos, todos embebidos. Tras esto, clustering reconstruyó
  stories/story_articles (derivado, no archivo): 48 → 83 clústeres / 329 noticias.
  contenido_visible y hash intactos. Inmutabilidad respetada.
- **2026-06-21** — última regeneración de uuids de stories (NO es truncate de archivo).
  Al implementar UUID estable, los 83 uuid aleatorios pasaron a su valor uuid5
  determinista en una corrida. Churn final aceptado (sin enlaces compartidos en
  producción aún). De aquí en adelante, estables. Solo afecta stories (caché derivada),
  jamás articles.

- **2026-06-18** — backfill de Fase 2 sobre artículos nuevos (NO es truncate).
  395 artículos nuevos (capturados por el crawler desde el último backfill) tenían
  embedding NULL; backfill los rellenó (entidades + embedding) vía UPDATE. Banco:
  587 → 982 artículos. Idempotente, solo campos de procesamiento; contenido_visible
  y hash intactos. Tras esto, clustering reconstruyó stories/story_articles (derivado,
  no archivo): 20 → 48 clústeres. Inmutabilidad respetada.

- **2026-06-17** — migración 000009_rls_lectura_stories (NO toca datos; es RLS).
  stories y story_articles (creadas en 000007/000008) nacieron con row level
  security ACTIVO pero SIN policy de SELECT. La clave publishable veía cero filas
  SIN error (RLS no falla: filtra todo en silencio) → la web mostraba "Fase 2 en
  construcción" con datos reales presentes. Fix: policy `lectura_publica` (SELECT
  to public using(true)) en ambas, copia literal de la de articles/outlets. La
  escritura sigue siendo solo del crawler con clave secreta (ignora RLS).
  **Lección:** toda tabla nueva con RLS necesita su policy de lectura pública
  explícita. El hueco pasó inadvertido porque el crawler (secret) nunca la necesitó;
  solo se vio al ponerle la web (publishable) encima. Verificar policies al crear
  tablas, no al consumirlas.
- **2026-06-16** — backfill de Fase 2 (NO es truncate ni borrado de archivo).
  Se poblaron las columnas nuevas entidades (jsonb) y embedding (vector 384) de
  los 587 artículos vía UPDATE. Es UPDATE sobre articles PERO solo de campos de
  procesamiento nuevos que estaban NULL; NO se tocó contenido_visible ni hash.
  La inmutabilidad del snapshot se respeta: añadir un campo derivado no altera
  el archivo, igual que un índice no altera los datos.
- **2026-06-16** — stories/story_articles se borran y reconstruyen en cada corrida
  del clustering (recalcular-todo). Esto NO viola la regla de Fase 2 de no-truncar:
  los clústeres son CÁLCULO DERIVADO reconstruible desde articles, no son archivo.
  articles (la fuente de verdad) jamás se toca.
- **2026-06-14** — cambio de extractor v1→v2 (NO es truncate). Se migró la
  extracción de cuerpo a esquema por bucket (columna outlets.extraccion, migración
  000006): 'articlebody' (El Tiempo, El Colombiano, El Espectador) con trafilatura
  de respaldo; 'trafilatura' sola (Vorágine, Las2orillas). Consecuencia sobre el
  archivo: en las próximas corridas, las notas que reaparezcan en los feeds se
  re-extraen con cuerpo más limpio → hash distinto → entran como fila nueva (no se
  borra ni se actualiza nada; la inmutabilidad se respeta). Estas filas nuevas
  reflejan un cambio NUESTRO de extractor, no editorial del medio; se acepta como
  evento único documentado, hecho aún en Fase 1 (antes de que el archivo tenga
  valor histórico y antes de la regla de Fase 2 de no-tocar). Las notas viejas con
  cuerpo sucio quedan como su versión; no se fuerza recrawl ni truncate.
- **2026-06-11** — truncate de articles/audit_log. Primera limpieza por
  contaminación de boilerplate (cookies, chatbot) en la corrida inicial.
- **2026-06-11** — delete solo de El Espectador, por contenido de reproductor de
  audio y caricaturas mal extraídas.
- **2026-06-12** — truncate completo. Mejoras de limpieza (cola promocional,
  parcial por marcador) + nueva columna sección.
- **2026-06-13** — truncate completo. Mejoras de extracción (quitar
  favor_precision recupera cuerpo en El Tiempo) + rescate de subtítulo vía
  twitter:description (El Colombiano). ÚLTIMA cirugía de calidad antes de Fase 2.

---

## Deuda técnica conocida

### UUID estable de stories — RESUELTO (2026-06-21)
- **Contexto:** reescribir_stories hacía delete()+insert() dejando que Postgres
  generara gen_random_uuid → uuid nuevo cada corrida → todo enlace /historia/[uuid]
  compartido se rompía. Para una hemeroteca forense cuyo valor es "comparte este link
  como prueba", era una herida en la propuesta. Era prerequisito de automatizar el
  pipeline (automatizado, la rotura se multiplica a cada corrida).
- **Decisión de diseño (challenge-first):** entre las 3 opciones registradas, se
  eligió la #1 (semilla determinista) sobre la #2 (tabla story_identity persistente).
  Criterio que decidió: la #2 reintroduce ESTADO (matching difuso entre corridas),
  justo lo que se rechazó al descartar clustering incremental — convertiría stories de
  caché derivada pura a estado. La #1 COMPUTA el id desde datos (no lo almacena-y-busca),
  preservando stories como caché pura. Coherencia arquitectónica ya pagada.
- **Implementación:** uuid5(NAMESPACE_STORIES, url_del_más_antiguo). Corrección de
  granularidad sobre la idea original: se siembra del URL (átomo permanente de Trama),
  NO del article_id (cambia con cada re-captura). Determinismo total: el "más antiguo"
  se elige con min por (cuando(a), url) — el url como segundo criterio garantiza ganador
  único ante empates de fecha (sin esto, lo decidía el orden de iteración de Python →
  uuid inestable). NAMESPACE_STORIES es constante de módulo, NUNCA cambiar.
- **Validado:** dos corridas consecutivas sobre datos idénticos → los 83 uuids
  IDÉNTICOS (huella md5 del string_agg coincide). uuids son v5. Tier 2 load-bearing
  (escribe stories), no toca articles/esquema/umbrales/scores. Sin migración.
- **Residual aceptado (con disparador):** la #1 ata la identidad a UN artículo (el más
  antiguo). Flaquea en 3 casos RAROS, no medidos aún en frecuencia:
  (1) FUSIÓN: dos clústeres se unen; el más joven hereda el uuid del más viejo → su
  enlace se rompe. (2) EL MÁS ANTIGUO ABANDONA el clúster (recalibración le quita
  aristas): re-semilla con otro url → uuid nuevo (el caso más molesto). (3) SPLIT: la
  pieza sin el url-semilla original toma uuid nuevo. La opción #2 (matching por
  solapamiento) es robusta a los tres, pero pagar esa complejidad ahora es optimización
  prematura contra frecuencias no medidas. La #1 ES el instrumento que permite MEDIR
  esas frecuencias (con ids estables se observa qué historias persisten/fusionan entre
  corridas) — medir-antes-de-arreglar al meta-nivel.
- **Reactivar (escalar a opción #2) SI:** usuarios reportan enlaces rotos a historias
  que sí existen, rastreado a fusión/re-semilla frecuente.

  ### Búsqueda en /historias no paginada (2026-06-21)
- **Síntoma:** al agregar paginación al feed, la rama CON búsqueda (q3 en page.js)
  quedó SIN .limit()/.range() — devuelve todas las stories que matchean el texto. Hoy
  con 83 stories totales no muerde. La paginación de esta unidad cubrió solo el feed
  sin búsqueda (que era el problema del límite-30 reportado).
- **Decisión:** NO arreglar ahora. Acotado y visible. La búsqueda sí recibió el mismo
  orden (fecha_fin/n_medios/n_articulos) para no quedar con el created_at roto.
- **Reactivar SI:** la búsqueda empieza a devolver decenas de stories de forma habitual.

### Fix título-cita en el feed (display) — APLICADO 2026-06-21
- **Contexto:** la deuda titular-cita (2026-06-18) se volvió visible en producción
  (criterio de reactivación cumplido: 2 títulos-cita en el feed). Al investigar el
  punto #1 del TRASPASO (disconnect feed↔ancla) se halló la causa estructural: el
  título de display se computa en TRES lugares con criterios distintos —es_ancla
  (gate p75, backend), stories.titulo (hereda del ancla), y tituloCanonico
  (frontend, lib/colapsarCluster.js)—. El feed usa el tercero: máxima neutralidad
  PURA, justo la fórmula que el arreglo del ancla del 2026-06-18 descartó. Por eso
  ese arreglo era invisible en el feed.
- **Medido (diag_titulos.py sobre 48 clústeres):** 5 títulos-cita detectados, pero
  1 era falso positivo de la heurística inicial: «Comandante… anunció que 99
  disidentes de 'Walter Mendoza'…» — comillas envuelven un ALIAS, y el fallback
  "comillas + verbo de habla" sobre-disparó. Lección: en español la señal real es
  la cláusula entre comillas ADYACENTE a dos puntos (`"cita":` o `:"cita"`), no el
  verbo suelto. Heurística afinada a solo ese patrón (RE_CITA_DELANTE/RE_CITA_ATRAS,
  cláusula ≥15 chars): 4/4 citas reales, 0 falsos positivos.
- **Fix:** tituloCanonico (lib/colapsarCluster.js) ahora descarta titulares-cita;
  elige el titular noticia más neutral del subconjunto no-cita. Si todas las
  noticias son cita, cae a la más neutral (degradación elegante, no inventa título).
  Tier 2, presentación, NO toca scoring ni es_ancla — la cita puede seguir siendo
  es_ancla de las cards del bento; lo que cambia es solo el NOMBRE de la historia.
- **Validado (diag_fix_titulos.py, réplica de la heurística en Python sobre los 48):**
  3 títulos cambian (Petro b56729d8, Gaona 974f9571, Medicina Legal 3ce9745f), los
  tres a no-cita; 0 clústeres fuera de esos se mueven; residual = solo Germán
  656a7e6c (sus 2 noticias son ambas cita, sin alternativa); 0 caídas a fallback.
  Las alternativas elegidas eran tipo=noticia (confirmado: no cayeron a residual).
- **Residual aceptado:** Germán (1/48). Único caso donde generar título sería el
  único recurso; por 1 clúster NO se rompe inmutabilidad. Confirma parar en heurística.
- **Reactivar SI:** aumenta el % de clústeres sin alternativa no-cita con volumen, o
  se decide que el residual es inaceptable de cara al público.

### Doble-cómputo del título de historia — deuda estructural (2026-06-21)
- **Síntoma:** "qué texto representa el clúster" se decide en dos capas con criterios
  que pueden divergir: backend (stories.titulo, hereda del ancla por gate p75) y
  frontend (tituloCanonico, máx neutralidad no-cita). Hoy COINCIDEN de facto porque
  ambos sanean, pero el día que cambie el criterio de ancla otra vez, se
  desincronizan silenciosamente (ya pasó una vez: el arreglo del ancla 2026-06-18
  no surfaceó en el feed por esto mismo).
- **Decisión:** NO arreglar ahora. Documentar. El fix sería una fuente única de
  verdad para el título de display, pero hoy no hay divergencia visible.
- **Reactivar SI:** se cambia el criterio de selección de ancla, o aparece un título
  de feed que no concuerda con el ancla del expediente /historia/[id].

### [SUPERADO 2026-06-21 → ver "Fix título-cita en el feed"] Titular-cita de alta neutralidad ancla el clúster — el gate no la atrapa (2026-06-18)
- **Medido** al correr el banco 2× (48 clústeres): el gate p75 resuelve la
  *reacción de baja neutralidad* (Chalá) pero NO la *cita declarativa de alta
  neutralidad*. Caso "gringo" (n=6): ancla principal = «"Al parecer no violó a
  ninguno de sus hijos": presidente Petro…» (neut 0.920, cob 0.465). ACTUAL, p50 y
  p75 coinciden los tres: el gate no la corrige porque la cita SÍ pasa el piso de
  neutralidad (el embedding la ve central) y tiene la cobertura más alta.
- **Patrón, no caso único:** también n=2 "Germán le entregó sus programas bandera"
  y "No era una campaña cualquiera, fue una cruzada nacional". Titulares-cita de
  actor político anclando clústeres. Casi invisible con 20 clústeres, visible con 48.
- **Causa:** ninguna de las dos compuertas ni los tres scores miden "el titular es
  una cita declarativa, no una descripción del hecho". Es ortogonal a neutralidad y
  cobertura. Para Trama es justo el encuadre que el producto debe *señalar*, no
  adoptar como voz neutral del clúster.
- **Decisión:** NO arreglar ahora. Medido (existe) pero el fix es caro y riesgoso:
  detectar cita declarativa es heurística de lenguaje (comillas en titular, verbo
  de habla "dijo/aseguró/señaló", NER de actor como sujeto), toca el scoring
  (load-bearing). Es su propia unidad de trabajo con su propio diagnóstico.
- **Reactivar SI:** se decide priorizar calidad de anclas antes que volumen, o si
  al exponer scores/anclas al público el patrón se vuelve embarazoso de forma visible.
- **Matiz honesto:** el arreglo del ancla de hoy cerró UNA falla (reacción de baja
  neutralidad), no las dos. Esta es la otra cara del mismo problema de anclaje.
  
### [RESUELTO 2026-06-18] Ancla por cobertura — DISPARADOR CUMPLIDO (2026-06-17)
- Re la deuda "score_cobertura no comparable entre clústeres" (2026-06-16): su
  criterio de reactivación era "si el ancla por cobertura elige mal de forma
  visible". **Se cumplió, medido al renderizar.** En el clúster de Chalá el ancla
  "más neutral + completa" (mayor neutralidad×cobertura) salió siendo la reacción
  política "Alcalde de Medellín… hombre de Calarcá protegido por Petro"
  (neut 0.82 × cob 0.22 = 0.183, el máximo del clúster), no la nota factual de la
  captura. Causa: cobertura premia mencionar muchas entidades; una reacción que
  nombra a todos los actores puntúa alto pese a estar editorializada.
- **Decisión:** el fix es de BACKEND (renormalizar cobertura por tamaño de clúster,
  o recomputar es_ancla), su propia unidad de trabajo, medida — NO se maquilla en
  la vista. La vista lo muestra fiel con aviso visible.
- **Decisión ligada:** NO exponer los scores (neutralidad/cobertura/divergencia)
  al público hasta que cobertura esté arreglada y sea explicable. Mostrar a un
  público de verificadores un número que sabemos roto resta credibilidad. Hoy
  quedan como diagnóstico (mono pequeño), no prominentes. No invertir en tooltips
  sobre un score provisional.
- **[RESUELTO 2026-06-18]** El fix candidato registrado (renormalizar cobertura por
  tamaño / pesar por frecuencia) se MIDIÓ y se DESCARTÓ: pesar la cobertura por
  frecuencia dentro del clúster *reforzaba* la reacción en vez de castigarla
  (cob_frq de la reacción del Alcalde = 0.49 > cob actual 0.22). La reacción no gana
  por nombrar actores periféricos sino por saturar densamente las entidades
  centrales. Diagnóstico real: `neutr` es casi constante en un clúster (~0.80–0.95)
  y `cob` de alta varianza, así que el producto `neutr*cob` ordenaba de facto por
  cobertura. El bug no estaba en la cobertura sino en MULTIPLICAR dos scores de
  escalas incomparables.
- **Fix aplicado:** separar las preguntas. Gate de neutralidad (piso p75 del clúster)
  + desempate por cobertura entre los que pasan, para el ancla PRINCIPAL. El ancla
  secundaria sigue siendo la de mayor divergencia. Enmienda a ARQUITECTURA §6.
- **Validado sobre la base** (no sobre predicción): Chalá ancla "Legalizan captura"
  (neut 0.913), la reacción del Alcalde (neut 0.823) queda es_ancla=false. Sin
  regresión en clústeres ya sanos (Niño Guerrero, Air-e). Confirmado de nuevo con
  banco 2× (48 clústeres). Umbral p75 PROVISIONAL, calibrado sobre días dominados
  por macro-temas; recalibrar con volumen multitema.

### Lookup por URL — best-effort, no garantía (2026-06-17)
- **Medido:** el id del artículo vive siempre en el PATH en los 5 medios (sufijo
  -3564106, -EK37683689); ningún query param es significativo → la normalización
  quita TODOS los params (allowlist vacía). Pero el archivo guarda la URL exacta
  del feed RSS/sitemap sin normalizar, y eso es inconsistente por medio: El
  Espectador y Las2orillas con trailing slash, los demás sin; voragine.co sin www,
  los demás con www.
- **Mitigado:** variantesUrl() prueba 4 combinaciones (con/sin www × con/sin slash)
  en un solo .in() — query visible, no match difuso. Cubre el caso frecuente (pegar
  una nota de El Espectador sin el slash final).
- **NO cubierto (deuda aceptada):** variantes AMP (amp.medio.com), móvil
  (m.medio.com), o canónicas inconsistentes. Fallan silencioso ("no encontré tu
  noticia" cuando sí está).
- **Decisión:** NO arreglar más allá del fallback de 4 variantes.
- **Reactivar SI:** usuarios reportan no encontrar notas que sí están archivadas,
  o si AMP/m. se vuelven comunes en lo que pega la gente.
### es_parcial en El Espectador — investigado, NO es bug (2026-06-16)
- **Reporte:** notas de El Espectador (y algunas de El Tiempo) marcadas
  es_parcial=true viéndose completas y largas. Sospecha de falso positivo.
- **Hipótesis descartadas con datos:** (1) umbral de caracteres — es_parcial no
  mira longitud; (2) regex global de detectar_paywall_jsonld agarrando un nodo
  JSON-LD ajeno — el diagnóstico mostró que el nodo PRINCIPAL (mismo titular/URL)
  declara isAccessibleForFree=false; (3) enlace "Lea más:" incrustado como causa —
  una nota sin ningún "Lea más:" salió parcial igual.
- **Medido (% es_parcial por medio):** El Espectador 48.1% (115/239), El Tiempo
  15.6% (28/180), El Colombiano 1.1%, Las2orillas 0%, Vorágine 0%. El 48% (ni ~0%
  ni ~90%) indica que El Espectador distingue activamente abiertas vs restringidas:
  señal real, no ruido.
- **Conclusión:** el crawler lee correctamente isAccessibleForFree del nodo correcto.
  No hay bug. Confirma lo ya documentado en Ideas/"Paywall por isAccessibleForFree":
  El Espectador declara false aunque el cuerpo completo viaje en el HTML público
  (muro = overlay JS). es_parcial=true NO implica cuerpo recortado en este medio.
- **Doble semántica a recordar para Fase 2:** es_parcial funde "el medio declara
  la nota restringida" (detectar_paywall_jsonld) y "el cuerpo archivado está
  recortado" (detectar_parcial por marcador). NO usarlo como proxy de "incompleto"
  en el clustering — descartaría ~115 notas de El Espectador que están enteras.
- **Decisión:** NO tocar el crawler. El uso del flag es visual (badge "de pago"),
  para el que sirve tal cual.
### score_cobertura no comparable entre clústeres de distinto tamaño (2026-06-16)
- **Síntoma (medido sobre clústeres reales):** la cobertura (fracción de entidades
  del clúster que un artículo menciona) sale baja y plana en clústeres grandes
  (0.05–0.22 en el de 18 notas) y alta en chicos (0.5–0.8 en los de 2). Causa: en
  clústeres grandes la unión de entidades es enorme, así ninguna nota cubre gran
  parte. Matemáticamente correcto, pero el score no discrimina bien "cuál es la
  más completa" en clústeres grandes.
- **Decisión:** NO arreglar ahora. Para Fase 2 temprana el criterio de ancla
  funciona (verificado: las anclas elegidas tienen sentido). Es deuda de robustez,
  no de corrección.
- **Reactivar SI:** al construir la vista, el ancla por cobertura elige mal de
  forma visible, o se quiere comparar cobertura entre historias distintas.
- **Fix candidato:** normalizar cobertura por tamaño del clúster, o medirla solo
  contra las entidades de las anclas en vez de la unión total.

### [RESUELTO] Esquema vivo manda — verificar antes de escribir código (2026-06-16)
- **Qué pasó:** el clustering encadenó 4 errores de insert porque su código
  asumía el esquema de la migración 000007 dictada en chat, pero la base tenía
  un esquema distinto de stories/story_articles (boceto previo: titulo_descriptivo,
  articulo_origen_id, estado, todo uuid).
- **Causa raíz doble:** (1) se escribió el código sin leer el esquema real de la
  base primero; (2) la 000007 usó `create table IF NOT EXISTS`, que sobre tablas
  preexistentes NO hizo nada y NO avisó — fallo silencioso. El alter de articles
  sí corrió (por eso entidades/embedding quedaron bien).
- **Lección:** antes de escribir código que dependa del esquema, leer
  information_schema de la base, no confiar en el .sql dictado. Y en componentes
  load-bearing, evitar defensas que fallan en silencio (IF NOT EXISTS, try/except
  mudos): preferir el error ruidoso que delata el desajuste.
- **Fix:** migración 000008_corregir_esquema_stories (drop+create con uuid
  consistente con articles.id). 000007 se deja en disco como historia, con
  comentario que apunta a 000008 (migraciones son append-only, no se reescriben).

### articleBody plano y con enlaces incrustados (2026-06-14)
- **Síntoma 1 (formato):** articleBody del JSON-LD viene como string plano, sin
  saltos de párrafo (verificado con repr() sobre El Colombiano: \n=0). El cuerpo
  se archiva como muro de texto en los medios del bucket articlebody.
- **Síntoma 2 (enlaces incrustados):** articleBody incluye enlaces del medio en
  mitad del cuerpo ("Lea: ...", "Puede leer: ...") que no son contenido del
  artículo. limpiar_contenido no los corta porque van en el medio, no en la cola.
- **Decisión:** NO arreglar. El formato es irrelevante para Fase 2 (embeddings) y
  Fase 3 (sumario); el expediente web es archivo de respaldo, no experiencia de
  lectura. Los enlaces incrustados meten ruido leve, no rompen el clustering.
- **Reactivar SI:** el clustering de Fase 2 sale visiblemente ruidoso y se rastrea
  a estos enlaces, o si se decide hacer la lectura del original dentro de Trama.

### Respaldo trafilatura corta al lead (~10% El Tiempo) (2026-06-14)
- **Síntoma:** notas del bucket articlebody cuyo nodo JSON-LD no expone
  articleBody caen a trafilatura, que a veces extrae solo el lead + firma
  ("PERIODISTA / Actualizado: / LEA TAMBIÉN"). Caso: nota de la Registraduría.
- **Medido:** script de calidad sobre el archivo guardado → 'corto' (<600 chars)
  10% en El Tiempo, 7% en El Espectador, 0% en El Colombiano. 'residuo_firma' 7%
  en El Tiempo. Es la vieja deuda del embed/corte, ahora acotada por articleBody.
- **Decisión:** NO arreglar. Bajo impacto, es el respaldo haciendo su trabajo
  imperfecto en el residuo donde articleBody falta.
- **Reactivar SI:** 'corto' en El Tiempo supera ~20%, o afecta notas relevantes.

### Nota sobre el medidor de calidad (2026-06-14)
- El script de calidad agregado (banderas: corto / enlaces / residuo_firma /
  teasers / fuga_boilerplate) tiene falsos positivos en dos columnas por el texto
  plano de articleBody: 'teasers' se dispara por líneas largas sin puntuación de
  cierre (no son videos), y 'c/enlaces' cuenta "lea:" como substring (matchea
  palabras legítimas). Señal CREÍBLE del medidor: fuga_boilerplate=0% (limpieza
  sólida) y 'corto' (deuda real arriba). Las otras columnas, leer con pinza.

### Clasificador de tipo en Las2orillas y Vorágine (2026-06-12)
- Ninguno usa /opinion/ en el path, así que si publican columnas de opinión las
  marcamos como 'noticia'. Bajo volumen, bajo impacto. Vigilar.

### Feed plano silencia medios de baja frecuencia (2026-06-12)
- El feed muestra los 80 más recientes; El Tiempo (alto volumen) desplaza a
  Vorágine (baja frecuencia) fuera de la ventana. Irónico para un proyecto sobre
  representación.
- **Fix candidato:** paginación, o feed que garantice presencia de todos los
  medios. Resolver en iteración de web.
---

## Ideas registradas (no son deuda, son evolución futura)

### [RESUELTO 2026-06-21 → ver Deuda técnica/"UUID estable de stories"] Estabilidad de enlaces de historias (UUID estable) — prerequisito de automatización (2026-06-21)
- **Problema:** reescribir_stories (clustering_fase2.py) hace delete()+insert() de
  stories en cada corrida → uuid nuevo cada vez → todo enlace /historia/[uuid] que
  alguien comparta (redes, evidencia, cita) se ROMPE tras la siguiente corrida. Para
  una hemeroteca forense cuyo valor es "comparte este link como prueba", es una
  herida en la propuesta, no un detalle.
- **NO es optimización de cuota** (no hay cuota: el clustering es coseno en numpy
  sobre embeddings ya calculados, cero API). Es identidad + escala. Se aclara porque
  surgió de una idea de "recalcular solo lo reciente para ahorrar" que se descartó
  (ver abajo).
- **Por qué importa el ORDEN:** es prerequisito de automatizar clustering. Hoy se
  corre a mano y esporádico, daño bajo; automatizado, se multiplica. Ids estables
  ANTES de automatizar, no al revés. Reordena la cola por encima de "automatizar".
- **Opciones a evaluar (sin decidir):**
  * ID determinista por semilla estable: derivar el id del artículo más antiguo del
    clúster (primera captura casi nunca cambia). Robusto al crecimiento; borde =
    fusiones de clústeres (¿qué semilla gana?).
  * Tabla story_identity persistente que sobreviva los truncates y mapee
    firma-de-clúster → uuid estable, reusándolo entre corridas. Más robusto, más complejo.
  * Hash del conjunto de artículos: DESCARTADO de entrada — si el clúster gana un
    artículo (lo esperado), el hash cambia. No sirve.

### Clustering incremental (recalcular solo lo reciente) — DESCARTADO como optimización (2026-06-21)
- Idea: no recalcular clústeres viejos cada corrida, solo los recientes, para
  "ahorrar consumo/tiempo".
- **Descartada con tres razones:** (1) lo caro (embeddings + NER) YA es incremental
  vía backfill idempotente; el clustering NO recalcula embeddings, solo hace coseno
  en numpy sobre vectores existentes — cero API, cero cuota, segundos a 982 arts.
  Optimizar es prematuro (el O(n²) real aparece a decenas de miles, 10-14 meses
  lejos). (2) Convertiría stories de CACHÉ DERIVADA PURA (reconstruible) a ESTADO,
  con casos borde feos (artículo nuevo a clúster viejo: ¿re-ancla?; artículo puente
  fusiona clústeres: ¿qué uuid sobrevive?). (3) FOSILIZA umbrales provisionales:
  hoy cada recompute total es la oportunidad de re-juzgar el banco al recalibrar
  IDF/coseno/p75; incremental congela decisiones con umbrales viejos — justo lo que
  el TRASPASO bloquea hasta tener volumen multitema.
- **El grano de verdad de la intuición** se rescató como deuda aparte: la
  inestabilidad de UUID (arriba). Esa SÍ es real; la optimización de cómputo no.

### Generar título de historia por LLM — DESCARTADO (2026-06-21)
- Idea: usar NVIDIA NIM para generar el título de cada clúster. Cuota viable (48
  requests, ~1-2 min, sin créditos que gastar — la cuenta es rate-limited 40rpm).
- **Descartado pese a viabilidad de cuota**, por cuatro razones de fondo: (1)
  inmutabilidad/honestidad forense — un título generado es texto que ningún medio
  escribió, en el elemento más prominente del feed, sin etiqueta de IA (distinto del
  resumen LLM de Fase 3, que va ETIQUETADO como análisis). (2) no-determinismo
  rompe reproducibilidad. (3) alucinación en la cara del producto. (4) no es el
  arreglo rápido — monta media infra de Fase 3 dentro de Fase 2.
- **Jerarquía registrada:** heurística de selección (lo hecho hoy) < selección por
  LLM (el modelo ELIGE entre titulares reales, no inventa, no alucina, mantiene
  inmutabilidad) < generación por LLM (escribe título nuevo, rompe inmutabilidad).
  Si la heurística alguna vez se queda corta, el escalón siguiente es SELECCIÓN por
  LLM, no generación. Probablemente ese es el óptimo para Trama.
  
### Proveedor LLM de Fase 3 — DECIDIDO: NVIDIA NIM (2026-06-19)
- Cambio: el plan era Groq + Llama 3.3. Se adopta NVIDIA NIM (catálogo hosted
  build.nvidia.com), endpoint OpenAI-compat (https://integrate.api.nvidia.com/v1),
  modelo default meta/llama-3.3-70b-instruct.
- Por qué NVIDIA sobre Groq: variedad de modelos para evaluar (Nemotron Super 49b,
  Qwen, etc. bajo un mismo endpoint) y verificado que devuelve JSON estricto en
  español a temp baja. NO se eligió por potencia: reasoning models (DeepSeek,
  Nemotron Ultra) quedan descartados para esta tarea — más lentos, más cuota, cero
  ganancia en un clasificador conservador con JSON.
- Verificación de sostenibilidad (lo que destrababa la decisión): el panel de la
  cuenta muestra rate-limit (Up to 40 rpm), NO un balance de créditos que se agota.
  Para un job batch recurrente como Fase 3, eso es lo que se necesitaba. La
  ambigüedad "créditos vitalicios vs rate-limit" de la documentación pública NO
  aplica a esta cuenta. (Headers de respuesta NO exponen el límite; vive solo en
  el panel UI.)
- Es llamada API pura: NO se hostea nada, la GPU local (AMD) es irrelevante. El
  cómputo corre en datacenters NVIDIA. El "Downloadable NIM" (contenedor self-host
  + licencia AI Enterprise) es OTRO producto, fuera de alcance.
- Decisiones de implementación atadas:
  * Cliente SWAPPABLE: base_url + api_key + model_id en config/.env, nunca hardcode.
    Razón dura: el catálogo NIM rota casi a diario (doc "updated 10h ago") y no hay
    SLA — un model_id hardcodeado rompe Fase 3 cuando NVIDIA jubile el modelo.
  * JSON forzado por PROMPT + parse/validate/retry, NO por extensión propietaria de
    NVIDIA (nvext/guided). La extensión rompería la portabilidad a Groq y mataría el
    cliente swappable. El wrapper de validación se quería igual (sin SLA).
  * Modelo síncrono a propósito: los modelos grandes del catálogo usan patrón async
    (202 + status-polling); llama-3.3-70b-instruct es POST directo. Elegir un async
    es trabajo extra consciente, no default.
  * Retry con backoff en 429 (throttling por tráfico compartido, sin SLA).
- Groq + Llama 3.3 70B queda como FALLBACK documentado, mismo cliente OpenAI-compat.
- Reactivar/conmutar a Groq SI: las corridas empiezan a dar 402/403 por créditos
  agotados, o el throttling de NIM hace inviable el batch. Es cambio de config, sin
  reescritura.
  
### Iconos "ⓘ más información" contextuales en la UI (2026-06-18)
- Idea de Jota al recortar el aviso de "artículo sin clúster" en /buscar: el texto
  largo invadía el UI de entrada. Se recortó a una frase. La idea futura es añadir
  un icono "ⓘ" junto a textos breves que, al interactuar, revele el contexto
  completo bajo demanda — sin saturar la vista inicial.
- Patrón general, no solo para /buscar: aplicable a cualquier punto donde haga
  falta explicación secundaria (badges es_parcial, scores, etc.).
- NO implementar ahora. Es mejora de UX transversal; merece decidirse como patrón
  (¿tooltip hover? ¿popover tap-friendly en móvil? ¿accesibilidad/foco?) en vez de
  parchear caso por caso. Registrar para no perderla.
  
### Pequeños arreglos pendientes del buscador (2026-06-18)
- Iteración B quedó funcional y con tests verdes, pero Jota detectó arreglos
  menores a trabajar en chat aparte. (Detalle cuando se aborden — no se anticipan
  aquí para no inventar alcance.)

### JSDoc para chequeo de tipos sin migrar a TS (2026-06-17)
- El único valor que TS aportaría es tipar el contrato de los 3 scores (que es_ancla
  sea bool, scores números) para avisar si el shape de Supabase cambia. No justifica
  meter TypeScript a un proyecto JS. Si alguna vez el shape del backend muerde,
  JSDoc da chequeo en editor/CI sobre .jsx puro. No urgente.

### Política de archivado de bitácora (acordada 2026-06-16)
- BITACORA es append-only y NO se condensa (condensar pierde el "por qué"
  original, que es justo lo que la bitácora preserva). Cuando una entrada se
  resuelve, se le antepone marcador `[RESUELTO fecha]` sin borrarla.
- Al cerrar cada fase, las entradas de esa fase se mueven EN BLOQUE (sin
  reescribir) a `/archive/BITACORA_faseN.md`, dejando en la viva un puntero +
  las reglas de esa fase que sigan vigentes.
- **Disparador del primer corte:** cierre de Fase 2. No hacer antes (el costo de
  tokens de un MD largo es bajo; el riesgo real es dilución de señal, que el
  marcador [RESUELTO] ya mitiga sin necesidad de cortar).

### Filtro anti-basura de NER (2026-06-16)
- spaCy marca como entidad cosas que no lo son ("Además", "Asimismo", frases
  largas tipo "Un millón de personas deben inscribirse..."). El backfill ya aplica
  un filtro mínimo (longitud 2–40, ≤4 espacios, stopwords de conectores). Funcionó
  (ents_promedio sano = 16.9), pero es básico.
- **Mejora futura:** filtro más fino si el ruido de NER infla pesos IDF de pares
  aislados y ensucia clústeres. No urgente — los clústeres del 2026-06-16
  salieron limpios con el filtro mínimo.

### Feeds de cola verificados — RTVC y La Silla Vacía (2026-06-16)
- Verificados con script de feeds (diligencia previa, NO activados):
  - La Silla Vacía → https://www.lasillavacia.com/feed/ (rss, WordPress)
  - RTVC Noticias → https://www.rtvcnoticias.com/rss.xml (rss; su /feed/ da 404)
- **Pendiente antes de admitirlos:** diagnosticar su bucket de extracción
  (articlebody vs trafilatura) — no heredan el de nadie. La Silla es WordPress
  con paywall parcial (fuerte en análisis, bajo volumen de minuto a minuto); RTVC
  es estatal. Activarlos solo tras decidir construir sobre 7 medios — hoy se
  mantiene el banco de 5 validados.
  
### ⭐ articleBody — RESUELTO/IMPLEMENTADO (2026-06-14)
- La hipótesis de "migrar TODO a articleBody" se descartó con datos. El
  diagnóstico (muestra fresca + casos conocidos) mostró complementariedad:
  articleBody al 100% en El Tiempo y El Colombiano, 83% en El Espectador (donde
  trafilatura sufría boilerplate), AUSENTE en Vorágine (sin JSON-LD) y Las2orillas
  (donde trafilatura ya extrae limpio). Decisión: híbrido por bucket, no reemplazo.
- El premio real NO fue la deuda de El Tiempo (el corte midió 0: ya mitigada al
  quitar favor_precision la sesión anterior), sino cuerpos limpios (boilerplate 0%)
  como materia prima para el clustering de Fase 2.
- Riesgo ético del paywall: medido y descartado. El cuerpo de notas de pago de El
  Espectador ya lo capturaba trafilatura (muro = overlay JS, cuerpo en HTML
  público). articleBody no da acceso a nada nuevo.
- Se consideró REVERTIR a solo-trafilatura (corazonada de simplicidad) pero se
  mantuvo el híbrido: el dolor de articleBody es cosmético (formato), el beneficio
  es de contenido (boilerplate 0%). No re-evaluar desde cero sin un motivo nuevo.

### Filtro de notas-video de El Tiempo (2026-06-14)
- Decisión de alcance (no es deuda): se saltan notas cuyo título de feed empieza
  con "Video |". Son piezas de video sin cuerpo de texto archivable; no aportan
  snapshot ni materia para clustering. Filtro por convención de titulación de El
  Tiempo (no global). Si cambian el patrón, se colarían y caerían al filtro de
  longitud — vigilar.

### ⭐ articleBody del JSON-LD — posible cambio de enfoque de extracción (2026-06-13)
- **Hallazgo:** El Espectador expone "articleBody" dentro del JSON-LD (verificado
  con probar_paywall2.py). Es el cuerpo del artículo completo y estructurado,
  inmune a los problemas de maquetación que confunden a trafilatura.
- **Hipótesis de alto valor:** si los demás medios (sobre todo El Tiempo) también
  exponen articleBody, podríamos pasar de "trafilatura adivina el cuerpo" a "leer
  el cuerpo del JSON-LD". Resolvería de raíz la deuda de extracción de El Tiempo
  (Cartagena, El Poblado) y mejoraría la calidad general.
- **Por qué NO se hizo ahora:** es un cambio grande en el componente más delicado
  (extracción). Merece su propia sesión: diagnóstico de cobertura por medio
  (¿quién tiene articleBody?), validar que viene completo y limpio, decidir si
  reemplaza o complementa a trafilatura, y probar antes de tocar producción.
- **Primer paso cuando se retome:** correr un probador de articleBody sobre los 5
  medios (similar a probar_extraccion.py) y comparar largo/calidad vs trafilatura.

### Paywall por isAccessibleForFree — RESUELTO PARCIALMENTE (2026-06-13)
- El Espectador declara "isAccessibleForFree":"false" en su JSON-LD para notas de
  pago. Se agregó detectar_paywall_jsonld() al crawler; es_parcial ahora combina
  esa señal (OR) con detectar_parcial por marcador.
- **Limitación aceptada:** no se recrawleó (para no truncar de nuevo). Las notas
  de paywall ya capturadas siguen marcadas como completas; solo las nuevas entran
  bien marcadas. Impacto bajo, es solo un flag de honestidad.
- El muro visible ("CONTINÚA LEYENDO... $9.000") es un overlay JS que NO llega al
  crawler — por eso buscar su texto no sirve; isAccessibleForFree es la señal real.

### Grafo de historias relacionadas (idea de Jota, 2026-06-12)
- Más allá de clústeres aislados: artículos que no son la misma noticia pero
  están ligados (una nota y su derivada, un hecho y su reacción). Relación
  ENTRE clústeres, no solo dentro. Mejora el modelo original de Fase 2.
- Implementar después de validar que el clustering simple funciona.

### Expansión de medios (criterios acordados)
- Cola actual: Colombia+20, La Silla Vacía (Fase 2); Semana, Caracol/W Radio,
  RTVC (Fase 3). RTVC aporta ángulo de medio público estatal.
- **Criterios de admisión:** (1) cada medio nuevo debe aportar un ángulo que los
  actuales no cubren; (2) verificar feed con verificar_feeds.py antes de
  prometerle lugar. Medios de paywall duro aportan solo titulares/ledes.

### [RESUELTO 2026-06-18]Nav en móvil — diseño pendiente (2026-06-17)
- `.masthead-nav` se oculta con `display:none` en pantallas <560px (globals.css).
  Funciona en desktop; en móvil no hay acceso a /historias desde el masthead.
- **Diseño pendiente:** decidir entre menú hamburguesa, barra secundaria bajo
  el masthead, o integrar las rutas principales en el pie. No diseñar antes de
  tener usuarios móviles reales — priorizar por datos de uso.
- **No bloquea Fase 2:** la ruta /historias es accesible en móvil por URL directa.

### Filtros y navegación en la web (pendiente)
- Falta: filtrar por medio, por tipo, por sección; búsqueda. La búsqueda por
  texto conviene dejarla para Fase 2 (aprovechar entidades/embeddings). El filtro
  por medio/tipo/sección se puede hacer ya sobre datos actuales.

### Perfiles de medios (Fase 3, espacio ya reservado)
- Columnas en outlets listas (propietario, grupo_economico, etc.). UI mostrará
  lista de secciones por medio + filtro. Cada dato de propiedad/financiación
  necesita fuente citable; será lo más atacado del proyecto.

### Vista de clúster Fase 2 — diseño cerrado (2026-06-15)
- Sesión dedicada a prototipar la UI de la vista de historia (expediente de
  clúster). Todas las decisiones visuales están aprobadas y documentadas en
  TRASPASO.md bajo "DISEÑO DE FASE 2 — decisiones cerradas".
- **Decisiones que afectan el modelo de datos / backend:**
  - El criterio de anclas (neutralidad + cobertura + divergencia semántica)
    requiere que el pipeline de clustering produzca tres scores por artículo
    dentro del clúster. No es solo un dato de display — es un contrato con
    el algoritmo. Definir cómo se calculan antes de implementar la vista.
  - El historial de versiones por nodo del hilo requiere que `story_articles`
    pueda devolver todas las capturas de un mismo medio para una historia,
    ordenadas por fecha_captura. Verificar que el esquema lo soporte sin
    migración adicional.
  - El grafo panorámico requiere una tabla o vista de relaciones entre clústeres
    (stories). No existe aún. Es Fase 2 avanzada, no Fase 2 temprana.

### Hilo rojo curvo — pendiente de precisar (2026-06-15)
- **Idea aprobada, implementación pendiente:** el hilo cronológico no debe ser
  línea recta. Usar SVG `<path>` con curvas de Bézier para simular la física
  de un hilo real (cuelga levemente entre nodos). El nodo de historia relacionada
  se desvía hacia una esquina con el hilo curvándose hacia allá.
- **Restricción de diseño:** un solo desvío visible por historia. Las demás
  conexiones viven en el grafo panorámico. Elegancia sobre dramatismo.
- **Por qué no se implementó ahora:** es detalle de implementación visual, no
  de arquitectura. Se precisa cuando se construya la vista real en Next.js.
  En SVG: `<path d="M x0,y0 C cx1,cy1 cx2,cy2 x1,y1">` con puntos de control
  calculados dinámicamente según posición de los nodos.

### Grafo de historias relacionadas — modelo de datos implicado (2026-06-15)
- La vista panorámica del grafo (idea original de Jota, registrada 2026-06-12)
  ya tiene diseño aprobado. Lo que falta es la tabla de relaciones entre stories.
- **Propuesta de esquema mínimo cuando se implemente:**
  `story_relations(id, story_id_a, story_id_b, tipo_relacion, score, created_at)`
  donde `tipo_relacion` puede ser: 'derivada', 'reaccion', 'contexto', 'seguimiento'.
- Calcular con entidades compartidas entre clústeres + similitud semántica entre
  los embeddings promedio de cada clúster. Implementar DESPUÉS de validar
  clustering simple — no antes.
---

## Notas de operación

- **Capitalización de archivos (convención fijada 2026-06-17):** directorios de
  ruta lowercase (app/buscar/, app/components/), archivos de componente PascalCase
  (Buscador.js), archivos de ruta/lib lowercase (page.js, normalizarUrl.js).
  Windows NO distingue mayúsculas pero Vercel (Linux) SÍ: un import que funciona en
  local puede romper en producción. **Pendiente de limpieza:** revisar duplicados
  por capitalización en la raíz (Cierre.md vs CIERRE.md, Arquitectura.md vs
  ARQUITECTURA.md) — decidir UNA forma y alinear, o git los tratará como archivos
  distintos.
- **Flujo de migraciones es manual-doble:** pegar el SQL en el editor de Supabase
  ES lo que cambia la base (fuente de verdad); copiar el archivo a
  /supabase/migrations es solo espejo en git, NO se aplica solo. Riesgo: divergencia
  silenciosa si se pega algo y no se guarda igual. Pegar SIEMPRE exactamente lo que
  se guarda. Idea futura (otra sesión): invertir el flujo con `supabase db push`.

- GitHub Actions: crons no son puntuales (corren con retraso variable). Normal en
  tier gratis. También: Actions desactiva crons tras 60 días sin commits del repo.
- Vercel cachea el feed (revalidate 300s) y artículos (3600s). Tras un truncate,
  los enlaces viejos dan 404 hasta redeploy. En operación normal (solo agregar,
  no borrar) esto no molesta.
- WinError 10054 ocasional en el crawler = el servidor del medio cerró la
  conexión (throttling transitorio). El try/except lo aísla; el artículo entra
  en la siguiente corrida. Solo preocupa si es en cascada.
