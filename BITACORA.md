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

### [2026-07-29] Esquema Fase 3: drop analyses vieja + create comparaciones/resumenes
- `analyses` (carril per-artículo, columnas tecnicas/omisiones/resumen_neutral, article_id
  único) confirmada VACÍA (count=0) -> DROP limpio, sin backup.
- Creadas `comparaciones` (por par, unique hash_a/hash_b + CHECK hash_a<hash_b) y
  `resumenes` (por clúster, unique cluster_key = sha256 del set ordenado de member_hashes).
  Ambas con FK SET NULL a articles/stories (no CASCADE: no destruir análisis caro).
- Aplicado a mano en editor de Supabase por Jota; espejado en /supabase/migrations/ por
  Claude Code (doble migración). El archivo del repo es documental, NO re-ejecutable.
- Nombres nuevos a propósito (no reusar `analyses`): esquema totalmente distinto, evitar
  confusión futura.

### [2026-07-22] GLM-5.2 SELLADO como modelo de Fase 3 — bake-off de v1-resumen

Prototipamos v1-resumen (2 pasadas: corroboración por spans verificados + síntesis que
solo ve los spans, no los artículos). El baseline Llama-3.3-70B falló el CASO TESTIGO
Pizarro con DERIVA CAUSAL: combinó spans todos verdaderos en la frase falsa "el 26 de
abril de 1990 la Fiscalía decidió no imponer medida" (1990 = fecha del magnicidio; la
decisión es de 2026). Invisible al verificador mecánico (números y nombres existían).
5/5 corridas.

Bake-off (diag_bakeoff2.py, 4 clústeres incl. Pizarro como testigo, 3 corridas):
- **Llama-3.3-70B:** desc 26.3%, cae en Pizarro, inestable. Descartado.
- **Qwen3.5-122B:** PASA Pizarro (no deriva) PERO se niega a procesar noticias de 2026
  ("no existe registro, mi conocimiento tiene fecha de corte") -> DESCALIFICADO para una
  hemeroteca que archiva material reciente. Además infra inestable (429, HTTP 400
  mrope, corrida de 279s).
- **GLM-5.2:** GANA las 4 dimensiones. desc 2.1%, estabilidad 0.0 (12/12 dieron 5
  hechos), 12/12 síntesis, 17s prom, 0 fallos, y NO rechaza fechas futuras. Pizarro
  limpio 3/3. Lectura humana de las síntesis: fieles y claras.

DECISIÓN: GLM-5.2 sellado para corroboración + síntesis + comparación. Baseline 70B
retirado de Fase 3. Groq (decomisión 2026-08-16) resuelto de facto.

HALLAZGO de método: éxito concluyente, fracaso no — la deriva del 70B era techo del
modelo, no de la tarea. Antes de matar un diseño de generación, probar un modelo mejor.

CAVEAT honesto: bake-off sobre 4 clústeres; GLM degradó "la Corte"->"una autoridad" en
1 corrida (correcto pero impreciso). El verificador valida procedencia, no fidelidad
semántica. Leer muestra a escala antes de publicar.

### [2026-07-21] v1-comparación FIRMADA — solo-spans elimina la fabricación de raíz

Prototipamos la comparación inter-medio en 4 corridas medidas (pares atómicos, 5x c/u,
grounding verbatim mecánico + control Ñeque).

Trayecto: (1) v1 con campos de texto libre -> grounding 24/24 OK pero contaminado por
opinión y desfase temporal. (2) Compuerta es_mismo_hecho + regla temporal -> no probables
(0 pares atómicos de opinión / gap ancho en el corpus; hallazgo: el confound temporal vive
en clústeres GRANDES, no en pares). (3) Estabilidad 5x -> fabricación RECURRENTE (5/5) en
salvedad del par Lorduy. (4) Endurecer salvedad -> la fabricación se DESPLAZÓ a agrega/
enfoque (fantasma de encuadre: el error se mueve, no muere).

DECISIÓN DE DISEÑO (raíz): la fabricación vive en la tarea de REDACTAR. Se quitó todo campo
de texto libre; la salida es {medio, categoria, span VERBATIM}. El modelo SEÑALA, no redacta;
el frontend explica. Resultado: 105 spans OK, 0 fabricación en 20 corridas. Confirmado leyendo
el span: antes el modelo escribía "César Lorduy ha sido acusado..." (añadía "César", no literal,
el filtro lo tumbaba); en solo-spans copió "Lorduy ha sido acusado..." (literal). No fue el
filtro cazando: fue el modelo dejando de fabricar al no tener dónde.

FIRMADO: enfoque + agrega (sólidas, groundeadas). Control Ñeque conserva salvedad 5/5.
BETA: salvedad (dos grietas — ver deuda). NO probado: el RESUMEN.

Contrato LLM v1 (congelado): unidad = PAR; per-artículo NO tiene LLM (Fase 3 vieja cerrada);
ent_div (sin LLM) es la compuerta resumen/comparación.

### [2026-07-21] Lectura inductiva — 5 patrones, v1 definida, corrección de método

Leí 16 clústeres reales (diag_lectura_inductiva.py → lectura_inductiva.txt; 3 grupos:
divergentes ≥3 medios, pares atómicos, control réplica). Jota leyó a mano el clúster
electoral (calibración); yo induje sobre el resto. Patrones consolidados:

1. **SELECCIÓN/ÉNFASIS** (dominante, groundeable, columna FUERTE): mismo hecho, cada
   medio pone al frente otro hecho/reacción/cita. Ej. Informe ONU: mismo documento,
   El Espectador titula la crisis y las críticas a la paz total; La Silla, la transición
   "fluida" y los progresos. Beto Coral: El Espectador enmarca persecución de Trump;
   El Colombiano destaca al republicano burlándose. ESTE es el payload de "leer entre
   líneas".
2. **PROFUNDIDAD/SALVEDAD** (aditivo, columna fuerte): quién añade contexto/advertencia.
   Ñeque: El Espectador afirma la muerte; El Tiempo la marca "presunta, en verificación,
   un video lo da por vivo". Diferencia epistémica real.
3. **EVOLUCIÓN TEMPORAL disfrazada de divergencia** (CONFOUND): buena parte del ent_div
   alto es la historia moviéndose. Usaquén pasa de "un hombre abusó" a "señalado
   falsamente". Comparar nota temprana vs tardía = afirmar divergencia falsa. → guardarraíl
   obligatorio de v1.
4. **VALORACIÓN EN VOZ DEL MEDIO** (real, con patrón por medio — El Colombiano
   editorializa más: "volvió a contradecirse", "agitó una narrativa de fraude"): juicio
   normativo, columna débil, cementerio del FP. DIFERIDA.
5. **VOCABULARIO (#1)**: muerto como feature. Lo real ("Casa de la Moneda"/"Imprenta
   Nacional") es escaso; los verbos jugosos ("muere"/"habrían abatido") están enredados
   con 1 y 3 y no se separan fiable.

**Control validó la compuerta:** réplica (Catalina/eutanasia, pastor Lora, Metro) salió
calcado (~0.72, misma cita textual de DescLab en los 3); divergentes ~0.97. ent_div separa
aunque el absoluto esté inflado por NER + impureza.

**Corrección de método (importante):** Claudio había afirmado que "leer entre líneas"
exigía el patrón 4 (columna débil, peligroso). FALSO. El grueso lo da el patrón 1
(selección), seguro y de columna fuerte. La comparación no es premio de consolación: es la
misión, y es lo fácil para el LLM.

**Decisión — v1:**
- Features: resumen de lo corroborado [ent_div bajo] + "qué destaca cada medio / qué añade"
  [ent_div alto].
- Guardarraíles OBLIGATORIOS: ventana temporal/fase, filtro de rol, limpieza de boilerplate.
- Diferido: patrones 4 y 5.
- FALTA: validar el OUTPUT del LLM (solo se validó que el material existe). Es lo próximo.

### [2026-07-20] Gate del carril inter-medio (a) — MEDIDO, dirección ratificada con alcance

Corrí diag_divergencia.py (Tier 0, read-only, desechable) sobre stories/story_articles de
PRODUCCIÓN — NO sobre cache_corpus.jsonl: la divergencia ya está calculada en el derivado,
y leer la tabla es más veraz que recomputar desde un volcado de esquema no verificable.
Sin ilike/seq-scan: solo selects por PK + paginación (no repite el 1101 del 2026-07-17).
400 clústeres, 1682 arts clusterizados.

**(a) RATIFICADA, con ALCANCE recortado.** Eje real: El Tiempo (76%), El Espectador (65%),
El Colombiano (65%) — editorialmente distintos, hay qué comparar. PERO ≈69% de los
clústeres son SOLO esos tres. NO se puede prometer "espectro completo": el producto compara
el eje mainstream y hay que decirlo así.

**Q1 — el proxy semántico está muerto por construcción.** score_divergencia p50=0.19: la
compuerta coseno≥0.70 SELECCIONA por similitud, no queda dispersión semántica intra-clúster.
La señal viva es divergencia de ENTIDADES (p50=0.80): separa réplica (ejemplos 0.29–0.44)
de divergente (1.00) y RASTREA TIPO DE HECHO — institucional (cumbre, decreto, condena) =
réplica; político/seguridad (Abelardo, operativo ACSN, Chalá, empalme) = divergente.
Decisión de diseño servida por el dato: **la feature NO es uniforme.** Anuncio → resumen;
hecho contestado → comparación.

**El "17.028 pares" es un espejismo de agregación.** El 71% viene de 2 clústeres (128 y 90
art = beats: empalme, elección). Excluyéndolos, el trabajo real sobre hechos discretos es
~2.000 pares. El 55.8% de los clústeres es un solo par (2 art, 2 medios) — el caso atómico,
el más limpio para construir/validar primero.

**Orden de features por EVIDENCIA:** (1) resumen de lo corroborado [réplica]; (2) qué AÑADE
cada versión [divergentes] — aditivo, nunca "qué omitió B"; (3) alineación de citas (74% con
≥2 medios citando, ejemplos reales CNE-Abelardo, SGC-sismo — medir mismo-hablante);
(4) vocabulario — NO probado (ver deuda).

**Próxima unidad = lectura inductiva** (no un prompt): leer ~15 clústeres divergentes
(titulares + párrafos), preguntar "¿qué hacen estos medios que un lector debería ver?".
La taxonomía sale del corpus. Es el paso que la §5 nunca dio.

### [2026-07-20] Mega-clústeres (beats) — MEDIDO, fix identificado, DIFERIDO por prioridad

**Síntoma (Jota):** clústeres que "arrastran" un tema de dos semanas; el título de
un artículo puntual no engloba. Ej: 4f3b3736 (empalme De la Espriella).

**No fue regresión.** Compuertas intactas (IDF≥20 AND coseno≥0.70, ventana 72h);
params de relación en valores validados. Ya fichado como "mega-historia" el 2026-06-27.

**Causa raíz (medida, no supuesta):** el ALGORITMO, no el umbral. Componentes
conexas (union-find) no tiene noción de densidad: una cadena de enlaces débiles a
través de notas SINÓPTICAS DE ESTADO (grado 15–17: "¿Qué viene para el empalme…",
"comenzó empalme…") funde 14 días en un nodo. Transitividad + notas-puente.
Hipótesis del DIGEST como puente: FALSADA (los "Diario del empalme" salen grado 2).
Diag: cluster_puentes.py — 128 nodos, 276 aristas, 34 puntos de articulación (27%),
grafo ralo. NO es masa densa; es beat encadenado.

**Alcance real (dry_run_comunidades.py, read-only, snapshot 6387 noticias):**
Solo 2 de 400 clústeres son beats (>50 art). El resto ya son hechos limpios (mediana=2).
Bug QUIRÚRGICO, no sistémico. La mediana global lo esconde — señal local, no agregada.

**Fix identificado:** detección de comunidades (Louvain) sobre el MISMO grafo/compuertas.
Parte los 2 beats en sub-hechos legibles y validados a ojo (De la Espriella → 5:
designación/transición, 6 ministros, suspensión, Bula canciller, desobediencia Cepeda).

**Bloqueador previo DERRIBADO:** el churn de uuid_estable que se temía (Tier 3 pesado)
NO ocurre a esta escala. Louvain preserva los 400 ids (rotos=0), añade 5–6 nuevos,
deja 381/381 clústeres sanos (≤12) intactos, en resoluciones 1.0–2.0.

**DECISIÓN: diferido a backlog por PRIORIDAD, no por riesgo.** Bajo impacto medido
(2/400, cosmético, no toca el pipeline per-artículo de Fase 3). Foco = salir de Fase 3
con técnicas per-artículo. Prerrequisito del carril de divergencia inter-medio; retomar
ahí. Receta lista: Louvain resolución ~1.6, seed fijo, mismas compuertas; re-validar
churn en el snapshot del momento (crece ~1000 filas/día → el "rotos=0" puede cambiar).

**Método (para el yo-futuro):** mis umbrales pre-fijados fallaron 2 sesiones seguidas
por elegir métricas que promedian el fenómeno (proxy componentes-a-K; mediana global).
Fijar umbral antes de correr sigue siendo correcto; elegir la métrica que AÍSLA la
señal local es la parte que hay que cuidar.

### [2026-07-06] RTVC validado en vivo + filtro de teasers en crawler
- Validación read-only de RTVC (57 art.): extraccion=trafilatura, es_parcial=0,
  secciones correctas, sin_procesar=0. Banco de 7 medios cerrado.
- Hallazgo: 35/57 con teasers de notas relacionadas (Lee además:/Te puede interesar:/
  etc.), 15/57 con embeds de tweets. El marcador COLA_PROMOCIONAL de RTVC no los cubría.
- Fix (rama fix/rtvc-teasers-crawler): tupla TEASERS + drop-line por PREFIJO (startswith,
  con colon) en limpiar_contenido. NO corte-a-fin, NO substring. Medido antes: 0
  colisiones en los otros 6 medios (4459 art.) → seguro como global. Validado local.
  Solo hacia adelante: los 57 existentes conservan cola (inmutabilidad).
- Tweets incrustados: NO se filtran (pueden ser evidencia legítima — citas de actores).
  Vigilancia.

### FK de analyses.story_id: creado con ON DELETE SET NULL (migración 000013, 2026-07-05)

Migración `20260705000013_analyses_story_id_set_null.sql` ejecutada en el editor de
Supabase y espejada en /supabase/migrations/ (doble flujo). Cambia esquema, no borra
datos (analyses estaba vacía).

Hallazgo que motivó la migración: `analyses.story_id` NO tenía FK a día de hoy. La
migración 000001 lo creó apuntando a la `stories` vieja (esquema pre-Fase-2); la 000008
hizo `drop table stories cascade` para reemplazar esa tabla, y el CASCADE se llevó por
delante el FK de analyses. Nadie lo volvió a enlazar. Estado real antes del fix: peor
que la landmine RESTRICT original — una story borrada dejaba story_id apuntando a un id
inexistente EN SILENCIO, sin error.

La migración usa un bloque DO auto-descubridor: busca en pg_constraint cualquier FK de
analyses.story_id→stories (con el nombre que tenga), lo dropea si existe, y agrega
siempre `analyses_story_id_fkey ... ON DELETE SET NULL`. Correcto sin importar cuál de
los dos estados (FK viejo residual o sin FK) tuviera la base viva. Sin IF NOT EXISTS.

Por qué SET NULL y no CASCADE: `clustering_fase2.py` recomputa stories cada 6h. CASCADE
borraría todos los analyses (Fase 3, caros de generar vía LLM) cada vez que su story se
re-semilla o disuelve — inaceptable. SET NULL conserva el texto del análisis; solo
pierde el enlace, re-derivable por article_id.

Precheck ejecutado antes del ADD (analyses vacía → cero huérfanas → ADD CONSTRAINT
válido sin fallar la validación de filas). Verificado post-migración:
`confdeltype='n'` para analyses_story_id_fkey.

NOTA lateral verificada, no un descuido: analyses_article_id_fkey quedó en 'a' (NO
ACTION). Es correcto — el artículo es inmutable y nunca se borra, así que el análisis
debe morir con su artículo o impedir su borrado, no quedar huérfano. Consciente, para
cuando se diseñe Fase 3.

### La Silla Vacía: activado, verificado y confiable (2026-06-29)
6º medio. Verificación post-cron (8 capturas reales) confirmó la config: trafilatura,
nivel_paywall abierto (es_parcial=false en todas), regla_seccion primer_segmento
(en-vivo→'en-vivo', red-de-expertos→null por el guard de ≤1 guion). Cuerpo real limpio.
La columna `final` del query reveló dos textos repetidos —footer de Cruz Roja (RCF) en notas
de desastre/migración y disclaimer de opinión en columnas red-de-expertos— que en una primera
lectura clasifiqué como boilerplate a quitar. CORRECCIÓN (Jota): son contenido editorial
legítimo (el RCF es un servicio real publicado en cobertura de desastre; el disclaimer es propio
de las columnas). Archivarlos es coherente con "archivar lo públicamente visible"; quitarlos haría
el archivo MENOS fiel. No se tocan. La preocupación residual (texto idéntico ligando clústeres
distintos) quedó como vigilancia, no deuda: sub-umbral del gate n_especificas≥3, sin medición que
indique cruce. Aplica el propio aprendizaje del proyecto: no clasificar señal como ruido sin leer
el contenido. La Silla Vacía queda CONFIABLE, unidad cerrada.

- **2026-06-27** — recómputo de story_relations con criterio recalibrado (NO es truncate
  de archivo). Al correr clustering_fase2.py con las capas nuevas (canon/ALIAS/GEO_EXTRA +
  FRAC_GENERICA=0.08), story_relations se reconstruyó (delete-then-insert, caché derivada):
  ~101 pares / 202 filas espejo sobre 149 clústeres. El crecimiento vs la medición offline
  (68 pares) es real, no bug: dos mega-historias estallaron entre corridas (terremoto de
  Venezuela y formación de gabinete de De la Espriella). Validado: hub Pastrana grado 4,
  control de andamiaje = 0 pares. articles jamás se toca; story_relations es reconstruible.

- **2026-06-27** — APRENDIZAJE (regresión de cronología de ediciones). Colapsar en
  el pipeline no exime de verificar qué capas leían las capturas SIN colapsar. El
  colapso por URL del 2026-06-23 documentó "el historial de capturas se preserva
  intacto" — cierto para `articles`, pero indujo a no revisar que `story_articles`
  (lo que la vista de cronología leía) sí perdía las capturas intermedias. Resultado:
  la cronología dejó de mostrar ediciones sin que nadie lo notara hasta semanas
  después. Regla para el yo-futuro: cuando se introduzca una deduplicación/colapso en
  una capa, auditar TODAS las capas aguas abajo que dependían del dato sin colapsar
  (aquí: la vista esperaba N capturas por URL para detectar ediciones). El dato nunca
  se pierde si el archivo es inmutable; lo que se rompe es el CAMINO del dato a la
  vista. Buscar el camino roto, no el dato.

- **2026-06-25** — migración 000010 (crea story_relations; NO toca datos de archivo).
  Tabla nueva, vacía al crear; el clustering la pobló en su corrida (137 clústeres →
  289 pares / 578 filas espejo). story_relations es CÁLCULO DERIVADO reconstruible
  desde stories; se borra/recomputa cada corrida igual que stories/story_articles.
  articles jamás se toca. RLS activo + policy de SELECT pública explícita (lección
  migración 000009: tabla nueva con RLS sin policy = web ve cero filas en silencio).

- **2026-06-23** — colapso por URL en el backend del clustering (NO es truncate de
  archivo). Al implementar colapsar_por_url() en clustering_fase2.py, el pipeline pasó
  a operar sobre artículos únicos (1904) en vez de capturas (2055): 151 capturas de
  notas editadas dejaron de contarse como artículos separados. Afecta SOLO el cómputo
  derivado (stories/story_articles): conteo, centroide y compuertas. articles
  (contenido_visible, hash) jamás se toca — la inmutabilidad y el historial de
  capturas se preservan intactos. Validado: determinismo del uuid confirmado (dos
  corridas idénticas → misma huella md5 7a9844b9...); diff vs estado sin colapsar
  (diag_colapso_diff.py, read-only) → 99 clústeres con identidad intacta, 4 viejos
  desaparecidos / 6 nuevos aparecidos (todos re-semillas limpias de origen único), 1
  disolución legítima (f0ac7e42: clúster de 2 medios que solo alcanzaba el segundo
  medio por contar una recaptura → al colapsar deja de calificar; correcto por diseño).
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

### [2026-07-29] Costo cuadrático del análisis por pares — BLOQUEANTE del backfill
C(n,2): 11=55, 90=4005 (~36h), 128=8128 (~73h). Necesita: (1) split de beats o agrupación
por ventana temporal antes del backfill; (2) tope de tamaño de clúster como guardarraíl del
cron (un clúster grande no puede colgar la corrida de 6h).

### [2026-07-29] Síntesis: causalidad no respaldada (versión suave del error Pizarro)
GLM une hechos verdaderos con conectores causales que los spans no sustentan. El verificador
(números/nombres) no lo detecta. Mitigación futura: prohibir conectores causales en
SYS_SINTESIS ("implicará", "debido a", "por lo que") o disclaimer visible en la UI.

### [2026-07-29] Fallos de JSON transitorios de GLM (~0-3.6%)
No sistemáticos (los 2 pares que fallaron se guardaron al reintentar). Absorbidos por
try/except + retry. Vigilar la tasa en el backfill a escala.

### [2026-07-22] Python 3.14 cuelga sockets SSL (httpx y requests) — BLOQUEANTE de prod
- Síntoma: el `recv` del socket no respeta el timeout; una llamada colgó 57 min. Pasa con
  httpx (streaming y no-streaming) y con requests. Traceback termina en `_sslobj.read`.
- No es del código: es incompatibilidad de la versión de Python (3.14, recién salida) con
  el stack. Mitigado en diags con POST no-streaming + timeout total + checkpoint jsonl,
  pero puede colgar igual esporádicamente.
- FIX: venv con Python 3.12 (LTS) para todo el stack, ANTES de correr cualquier LLM en el
  pipeline de producción. Prompt para Claude Code cuando se aborde.

### [2026-07-22] v1-resumen: la síntesis es la capa menos garantizable
- El verificador (substring de números/nombres) valida PROCEDENCIA, no equivalencia
  semántica ni relación causal. La deriva de Pizarro fue invisible a él.
- Con GLM-5.2 el riesgo baja mucho pero no a cero (degradó un sujeto en 1/12). Regla:
  leer una muestra de síntesis a escala antes de exponer en la web. La corroboración
  (pasada 1) sí es 100% verificable; la síntesis (pasada 2) no.

### [2026-07-21] salvedad es BETA: el filtro valida el span, no la categoría + caduca
- Grieta 1 (categoría): el grounding verbatim garantiza que el span es literal, NO que la
  categoría sea correcta. Un span con "preliminar" puede ser cita de fuente, no divergencia
  de certeza entre los dos medios. Visto en el par del dron.
- Grieta 2 (caducidad temporal, la señaló Jota): "presunto/en verificación" es un ESTADO
  que cambia (día 0 presunto -> día 2 confirmado). Una salvedad mostrada tarde queda
  desactualizada y deja mal parado al medio. enfoque/agrega son permanentes; salvedad no.
- Condición de la beta: mostrar salvedad SIEMPRE con su fecha ("al 18-jul, en verificación")
  -> registro histórico, no afirmación presente. Validación de la categoría (¿hay divergencia
  real de certeza?) queda para v1.1.

### [2026-07-21] Boilerplate se reporta como diferencia
- El modelo devuelve "Lea más:", "En contexto:" (teasers de navegación) como `agrega`.
  Groundeado -> el filtro verbatim NO lo tumba, pero es ruido, no divergencia editorial.
- Guardarraíl obligatorio de v1: limpiar boilerplate del texto ANTES de mandarlo al LLM.

### [2026-07-21] Bug de red: timeout read=None cuelga el proceso
- En streaming, httpx.Timeout(read=None) espera indefinidamente si el proveedor no manda
  [DONE]; el retry nunca dispara (no hay excepción). Colgó una corrida 40+ min.
- Fix: read=30.0 -> ReadTimeout (TransportError) -> el retry existente lo maneja. Aplicar
  en cualquier código de streaming, incluido el pipeline futuro y diag_fase3_articulo.py.

### [2026-07-21] Impureza de clúster: roles y fases mezclados inflan ent_div
- **Síntoma (leído en 16 clústeres):** un mismo "clúster" une explainer + resultado +
  reacción + logística (clúster electoral) y fases temporales distintas (Usaquén: acusación
  → exoneración). El ent_div alto mezcla divergencia editorial real con impureza.
- **Consecuencia:** comparar dos artículos de fases/roles distintos produce "divergencia"
  falsa. Es la causa raíz de los guardarraíles de v1 (ventana temporal + filtro de rol).
- **Decisión:** no se arregla el clustering; se COMPARA con guardarraíl (misma ventana/fase,
  mismo rol). El filtro de rol NO puede confiar solo en `tipo` (poco fiable entre medios).

 ### [2026-07-21] Duplicación intra-medio en clústeres beat
- **Síntoma:** clúster Javi (8 arts) = 5 notas de El Tiempo, URLs distintas pero
  casi-duplicadas por ángulo. `colapsar_por_url` no las une (son URLs distintas).
- **Consecuencia:** infla el conteo de pares y ensucia la comparación inter-medio (una nota
  se "compara" contra 4 versiones casi iguales del mismo medio).
- **Decisión:** evaluar dedup por similitud intra-medio al construir el split de beats. No
  urgente hasta el pipeline; registrado para no re-descubrirlo.

### [2026-07-20] Vorágine=0 y RTVC 4.2% en cobertura cruzada — deuda de PIPELINE
- **Síntoma (medido):** en el grafo de clústeres (400), Vorágine aparece en 0 y RTVC en 17
  (4.2%). Los ángulos que Arquitectura §4 justifica como "los que ningún otro cubre" están
  AUSENTES de la cobertura cruzada — peor que su ~1.5% del corpus.
- **Por qué importa:** afecta la premisa misma de divergencia, justo el carril al que se
  pivota. "Espectro completo" con estos medios sería falso hoy.
- **Causa: SIN medir (candidatas):** feed pobre / crawler que trae poco / hechos que no
  coinciden por entidades+embeddings (nota independiente ≠ mismo hecho por las compuertas).
- **Decisión:** NO se arregla a ciegas. Medir el porqué (Tier 0) antes de apoyar el producto
  en esos ángulos. No bloquea (a) sobre el eje mainstream; sí acota lo que se puede prometer.

  ### [2026-07-20] Beats = prerrequisito medido del pipeline de comparación (no cosmético)
- **Medido:** 2 de 400 clústeres (128 y 90 art) generan el 71% de los 17.028 pares.
- **Consecuencia:** un pipeline de comparación sin split trata 128 notas de 14 días como
  "un hecho". Bajo el carril (a), el split de beats (Louvain, fichado y validado 2026-07-20:
  res~1.6, seed fijo, mismas compuertas, churn=0) deja de ser diferido-cosmético y pasa a
  PRERREQUISITO del pipeline de producción.
- **Decisión/orden:** va DESPUÉS de la lectura inductiva (que decide qué feature) y ANTES de
  cualquier pipeline. Re-validar churn en el snapshot del momento (crece ~1000 filas/día).

  ### [2026-07-20] Feature #1 (vocabulario) SIN medir — el 82% fue un espejismo de canon()
- **Síntoma:** el gate reportó 82% de clústeres "con material de vocabulario" (mismo actor,
  ≥2 superficies, ≥2 medios). Al LEER los ejemplos: las superficies son variantes triviales
  del mismo nombre (procuraduría/la procuraduría/procuraduría general; registraduría/
  registraduría.; colombia/de colombia; gato negro/gato negro’).
- **Causa (medida al leer):** bajo-merge de canon() + puntuación, NO encuadre. El encuadre
  real (verbos "capturado"/"señalado", adjetivos, titulares) es INVISIBLE a la lista de
  entidades NER.
- **Decisión:** #1 sigue SIN medir. No se construye sobre este número. Se mide LEYENDO texto
  en la próxima unidad. Aprendizaje: casi repetimos el pecado de la §5 (coronar un % sin leer
  material); el volcado de ejemplos del diag fue lo que lo atrapó → mantener siempre ejemplos
  en los diags de materia prima.
  
### [2026-07-17] CRÍTICA — No existe oráculo de ground truth para Fase 3
**Síntoma:** puesto frente a los 57 casos reales del censo, Jota —**autor de la definición de
`arrastre`, autoridad de taxonomía del proyecto**— declaró no poder aplicarla con confianza.
**Causa:** no es falta de estudios. Si el autor no puede ejecutar su propia definición sobre
el archivo real, **la definición no es operacionalizable**, y la pregunta "¿el 70B la aplica
bien?" nunca tuvo referencia contra la cual medirse. El banco de 5 casos no es una muestra
del corpus: es una colección de **casos elegidos por ser claros**. FN=0/FP=0 se midió sobre
el subconjunto fácil. Poder juzgar "todos sabemos que detrás de Abelardo…" y no poder juzgar
el caso #34 no es inconsistencia: el primero fue seleccionado por nítido, el segundo es lo
que hay en la vida real.
**Antecedente:** la BITACORA ya rozó esto ("no ground-truth oracle exists for automated
evaluation") y lo parchó con "Jota juzga". El parche se rompió hoy.
**Decisión:** NO se arregla contratando anotadores ni entrenando el criterio. Se EVITA:
se elige un carril donde la verificación sea **código, no juicio** (grounding verbatim:
`in`, determinista, sin humano).
**Reactivación:** si alguna vez se necesita precisión sobre juicio humano, exige >=2
anotadores independientes y acuerdo inter-anotador reportado. Un solo anotador —y menos el
autor de la definición— no es medición.

### [2026-07-17] CRÍTICA — Banco balanceado ≠ prevalencia real (400×)
**Síntoma:** `arrastre` pasó su banco con FN=0/FP=0 y da 17.5% de precisión en el archivo.
**Causa:** banco 3 pos + 2 neg = prevalencia 60%. Archivo = 0.15%.
**Decisión:** los bancos NO se rehacen (sirven para lo que sirven: medir separabilidad). Se
RE-ETIQUETA lo que significan. Todo banco declara su prevalencia y dice explícitamente que
NO mide precisión operativa.
**Reactivación:** cualquier lectura futura de "FN=0/FP=0 -> listo para producción" es un
error; exige base rate medida primero.

### [2026-07-17] Los prompts VALIDADOS no viven en ningún artefacto versionado
**Síntoma:** al abrir la sesión, el bloque de `arrastre` (único código validado de v1) NO
estaba en `diag_fase3_articulo.py` — lo sobrescribió el de `atribucion_difusa`. Se recuperó
verbatim del historial de chat del 2026-07-12, por suerte.
**Causa:** regla del proyecto "los diag son desechables y no se commitean" aplicada a un
archivo que contenía especificación de producto.
**Decisión:** un prompt validado NO es instrumentación desechable. Debe vivir en
`/crawler/prompts/{codigo}_v{n}.txt`, versionado y commiteado. NO se hizo esta sesión (es
otra unidad). El paso "el batch reusa prompt(s) sobrevivientes" era un supuesto falso.
**Reactivación:** antes de escribir cualquier prompt nuevo de Fase 3.

### [2026-07-17] `arrastre` — el positivo #3 del banco es DUDOSO (y está DENTRO del prompt)
**Síntoma:** el ejemplo SÍ canónico ("todos sabemos que detrás de Abelardo de la Espriella
hay partes del establecimiento") aparece, con contexto completo, dentro de habla transcrita:
"…es también una puesta en escena, porque todos sabemos que […] y el muy hábilmente,
**digamos**, ha dicho bueno no se me suban a la tarima…". Es una entrevista/video, no prosa
editorial. **Por la regla de voz del propio prompt sería VOZ DE ACTOR -> N.**
**Causa:** la regla de voz define cita como "entre comillas «», o tras dijo/afirmó/sostuvo X".
Una transcripción sin comillas y sin verbo declarativo se cuela por el hueco. El banco de 5
casos nunca lo mostró porque no traía contexto suficiente.
**Gravedad:** está en el SYSTEM como EJEMPLO SÍ -> le enseña al modelo a marcar voz de actor
cuando no hay comillas. **Conecta con la vigilancia de d209382f** ("nadie en Washington quiere
responder en voz alta"): puede ser el MISMO agujero, no dos casos sueltos.
**Decisión:** NO se arregla — el carril per-artículo está cerrado. Se registra.
**Reactivación:** si se retoma `arrastre` (opción b), esto se resuelve ANTES de correr nada.

### [2026-07-17] Bugs del lexicón de `arrastre` (medidos, no arreglados)
**Síntoma:** (1) NEGACIÓN — `est[aá] claro que` captura "**no** está claro que volver a un
modelo militar vaya a ser eficaz" (n=45, n=63): el texto expresa incertidumbre y el detector
lo lee como consenso forzado. Es el opuesto exacto de arrastre. (2) PERSONALIZACIÓN — "**para
mí** está claro que…" (n=33): el autor se hace cargo en primera persona, lo contrario de
apelar al consenso.
**Causa:** el regex mira el marcador, no lo que lo rodea. Ambos son triviales de arreglar
(lookbehind).
**Decisión:** NO se arreglan. El carril está cerrado; arreglarlos sube P_lex de 0.175 a ~0.21
y no mueve ninguna decisión.
**Reactivación:** solo si se retoma la opción (b).

### [2026-07-17] Participación de medios en historias — NO MEDIDA (denominador corregido)
**Dato duro (medido):** sobre 6562 artículos únicos — el-espectador 2622 (40%), el-tiempo
2044 (31%), el-colombiano 879, las2orillas 545, la-silla-vacia 370, rtvc 81, voragine 21.
**CAVEAT que invalida la lectura directa (corrección de Jota, 2026-07-17):** ese denominador
es el corpus COMPLETO, y El Tiempo/El Espectador publican mucho contenido que nunca forma
historia (deportes, farándula, minuto a minuto — visible en el censo de arrastre: Shakira,
Dolly Parton, Mundial 2026). Los artículos de interés nacional son los que naturalmente se
agrupan. El denominador correcto para el carril de divergencia es `story_articles`, no
`articles`. **La cifra de volumen NO responde la pregunta.**
**La pregunta real, NO MEDIDA:** ¿en qué % de las historias participa cada medio?
`historias con el medio / total de historias`. Vorágine con 21 artículos puede estar en 8
historias (voz presente, volumen bajo) o en 0 (dos diagnósticos opuestos, misma cifra):
(a) publica poco de temas que otros cubren -> es su línea editorial, no un bug;
(b) publica de lo mismo pero las dos compuertas (IDF>=20 AND coseno>=0.70) no lo enganchan
    -> es un bug de clustering, y grave.
**Antecedente:** "Vorágine ausente del cross-coverage" YA estaba registrado en Ideas del
TRASPASO. Esto no es hallazgo nuevo; es la misma observación pidiendo por fin un número.
**Por qué importa (y qué NO importa):** la MECÁNICA del carril de comparación no sufre —
El Tiempo vs El Espectador sobre el mismo hecho es divergencia válida y publicable. Lo que
sufre es (1) la PROMESA de Arquitectura §4 ("cada medio aporta un ángulo que ningún otro
cubre"): si RTVC —voz institucional del Estado— aparece en el 2% de las historias, ese
ángulo vive en la tabla `outlets`, no en el producto; y (2) el CENTROIDE: si dos medios
dominan la participación, `score_neutralidad` mide de facto "parecerse a El Tiempo y El
Espectador". Conecta con las deudas ya abiertas "centroide-por-medio: sesgo direccional" y
"un voto por medio para centroides".
**Decisión:** no se ataca hoy. Se mide (Tier 0 sobre story_articles, sin LLM ni corpus)
ANTES de construir sobre divergencia.
**Reactivación:** primera unidad del carril de comparación, junto con la base rate de
divergencia. Ambas salen de la misma consulta.

### [2026-07-17] La receta "coarse ilike server-side" NO escala más allá de ~3 términos
**Síntoma:** 13 `ilike '%…%'` seguidos -> Cloudflare 1101 "Worker threw exception",
**determinista en el término #12**. El backoff (4 intentos, 2/4/8s) no ayudó: no es
transitorio.
**Causa:** cada ilike es un seq scan sobre 7k filas de texto completo, sin índice posible; el
worker de Supabase (plan gratis) acumula presión y revienta. La receta está en la BITACORA
(diag_positivos_superficie.py) validada con ~3 términos; se aplicó a 13 **sin preguntar si
escalaba**.
**Decisión:** patrón correcto para scans amplios: bajar el corpus una vez (paginado + ordenado
por id, página adaptativa), cachear a disco, filtrar en Python. Cero filtros server-side.
**Lección de método, más importante que el bug:** una receta de la BITACORA lleva implícito el
régimen en que se midió. Aplicarla fuera de ese régimen es el mismo error que leer FN=0/FP=0
de un banco balanceado como precisión operativa: usar un número fuera de sus condiciones de
validez.

### 2026-07-17 — Banco etiquetado por ARTÍCULO para un código que dispara por SPAN
**Síntoma:** el negativo a38be86f (sismo) se etiquetó `_neg` porque su span saliente es factual
("los expertos señalan que el sismo ocurrió cerca de la superficie" = hecho geológico). Pero el
mismo artículo contiene *"para muchos expertos, este doble sismo ya puede considerarse el desastre
natural más grande"* — evaluativo, positivo GENUINO. El artículo no era un negativo limpio.
**Causa:** error de diseño de Claudio al construir el banco: se etiquetó a nivel artículo un código
que dispara a nivel span.
**Decisión:** NO invalida el veredicto de atribucion_difusa — descontando a38be86f, quedan 940dcc4c,
d209382f y 80d6f651 como FP inequívocos (sourcing legítimo de hechos, y uno con fuente identificada).
El rechazo se sostiene sobre 3/3.
**Regla que se incorpora al mecanismo de probing:** el NEGATIVO debe ser un artículo donde NINGÚN
span califique — no basta con que el span saliente sea factual. Verificar leyendo el cuerpo completo,
no el snippet de 80 chars del scan de superficie.
**Reactivación:** aplica a todo banco futuro. Ya integrado al paso 1 del mecanismo en TRASPASO.

### 2026-07-17 — Desync bloque-SYSTEM ↔ banco produce corridas VOID silenciosas
**Síntoma:** se corrió el banco de atribucion_difusa con el bloque de taxonomía de `arrastre`
todavía en el SYSTEM. Los 3 positivos dieron vacío. Leído sin cuidado, eso es FN=3 y mata un
código bueno; en realidad el código ni siquiera estaba en el prompt. Se detectó porque el único
código emitido en las 7 corridas fue `arrastre` (span "nadie en Washington…" en d209382f).
**Causa:** el bloque del SYSTEM y el banco son dos artefactos que se cambian a mano, por separado,
sin nada que verifique que hablan del mismo código.
**Decisión:** NO arreglado esta sesión. Mitigación diseñada y NO implementada (~5 líneas):
constante `CODIGO_ACTIVO = "x"` junto a TECNICAS_VALIDAS + abort en `cargar_banco()` si
`{codigos derivados del banco} != {CODIGO_ACTIVO}`. Se rechazó un registro completo de códigos
(`--codigo X` que swapee bloque+banco) por scope creep: quedan ≤1 códigos por medir.
**Criterio de reactivación:** implementar el tripwire ANTES del próximo probe, si lo hay. Si el
carril per-artículo se cierra (ver decisión de alcance), la deuda muere con él.

### 2026-07-17 — VIGILANCIA: posible FP de `arrastre` en d209382f
**Síntoma:** durante la corrida VOID, `arrastre` marcó 3/3, estable y groundeado, el span
"nadie en Washington quiere responder en voz alta". Tapado el "nadie", queda RETICENCIA de
funcionarios — narrativa —, no una tesis en disputa presionada como consenso.
**Decisión:** `arrastre` sigue VALIDADO y CONGELADO. Un caso no reabre un código que pasó su banco
con FN=0/FP=0. Esto es VIGILANCIA, no reapertura, y no se re-versiona el prompt por esto.
**Criterio de reactivación:** si aparecen ≥2 casos más del mismo patrón ("nadie/todos" +
reticencia/narrativa en vez de consenso forzado), agregar d209382f al banco de arrastre como
negativo y re-medir. Antes no.

### [2026-07-12] `arrastre` VALIDADO — primer código de alta confianza de v1 (MEDIDO)
Método: banco fijo extendido (3 arrastre_pos + 2 arrastre_neg, texto real, dedup), DeepInfra
Llama-3.3-70B, temp 0.15, --repetir 3 por artículo. Umbral fijado ANTES de correr: pasa si
todos los positivos marcan y todos los negativos quedan vacíos, estable en las 3 corridas, con
grounding verbatim.
Resultado: FN=0 (los 3 positivos marcan arrastre en 3/3 corridas, spans idénticos), FP=0 (los 2
negativos vacíos en 3/3), grounding 1/1 OK en todos, 0 alucinadas. La EXCLUSIÓN DURA de `unánime`
mordió (el-tiempo "votación unánime, equivalentes a 54.743 votos" → vacío) y el color deportivo
("es evidente que se ve mejor que su rival") no disparó.
Def. congelada: prueba operativa (tapá el marcador de consenso; ¿queda HECHO verificable o TESIS
en disputa?) + exclusión dura (`unánime`-como-descriptor-de-hecho nunca es arrastre) + regla de voz
(voz del medio ≠ cita de actor) + 3 ejemplos SÍ / 3 NO de texto real.
Decisión: `arrastre` entra a v1 como código de alta confianza; puede encabezar el análisis y
disparar el termómetro. Supersede, para arrastre, la entrada 2026-07-11 "otros 5 códigos inestables
por definición floja": la inestabilidad era falta de ejemplos SÍ/NO, no límite del modelo.
Reactivar/re-medir SI: se cambia el prompt base, el proveedor, o se detecta un FP en producción.

### [2026-07-12] Predictor de supervivencia por-código CORREGIDO (aprendizaje de método)
Contexto: al abrir la unidad se agrupó a atribucion_difusa/arrastre/titular_enganoso/falsa_dicotomia/
miedo como "5 códigos de superficie (morfológicos)" que sobrevivirían por no depender del juicio
contextual que hundió a encuadre. La medición REFUTA esa premisa: arrastre EXIGE juicio contextual
(distinguir "hecho verificable" de "tesis en disputa" es contextual, no morfológico) y aun así pasó
limpio. Y atribucion_difusa, que se había descartado como "contextual → out", es en realidad el
gemelo estructural de arrastre.
Aprendizaje real: el predictor de si un código es domesticable por prompt en el 70B NO es
morfológico-vs-contextual. Es **¿el código tiene un set de exclusiones PEQUEÑO y CONVERGENTE?**
· arrastre: sí (una exclusión dura, `unánime`-como-hecho) → converge → pasa.
· encuadre: no (fenómeno natural → cultura → atrocidad, cada exclusión parcha un caso y abre otro,
  whack-a-mole) → diverge → baja-confianza.
Implicación para el triaje pendiente: atribucion_difusa (exclusión candidata: sourcing legítimo)
merece probe; miedo ("desproporción" = juicio abierto, no convergente) se predice baja-confianza;
titular_enganoso queda fuera por ser otra clase de claim (titular↔cuerpo), no por el modelo.
Nota de honestidad: el descarte previo de atribucion_difusa fue apurado; se corrige aquí con dato.

### [2026-07-12] `encuadre` no domesticable por prompt en 70B — degradado a baja-confianza
Síntoma (MEDIDO, banco fijo de 6 en banco_fase3.txt, DeepInfra Llama-3.3-70B, temp 0.15,
1 corrida/artículo): tres versiones de prompt, el error se DESPLAZA sin reducirse.
  · v3 (definición "palabras cargadas" + prueba operativa): marca la atrocidad como carga del
    medio — el-espectador 40f1846d dispara 4 encuadres sobre "torturas/asesinatos/violaciones de
    DDHH", que son el NOMBRE del delito, no color. FP grave.
  · v4 (+ exclusión de gravedad + exclusión cultural + refuerzo argumento≠encuadre): MATA la
    atrocidad (40f1846d 0) y conserva TP legítimos de RTVC ("flagelo", "defendió con vehemencia").
    PERO deja FP en fenómeno natural (Sahara 91d4ac69: 4, "ambiente más seco", "situación de
    emergencia") y en obra cultural (Calixto 4, sin bajar). La exclusión cultural NO mordió.
  · v5A (compuerta de agencia: "solo hay encuadre si se caracteriza la conducta de un actor con
    agencia"): mata clima/cultura por diseño PERO RESUCITA la atrocidad — 40f1846d 0→7, porque en
    un fallo judicial SÍ hay actores con agencia (guerrilleros, militares, tribunal), la compuerta
    da "procede" y reabre la puerta a marcar los nombres de los delitos.
Causa: el modelo aplica de forma fiable la distinción MORFOLÓGICA (¿la palabra es el nombre del
hecho o color añadido encima?) pero NO la CONTEXTUAL (¿existe un hecho público en disputa que se
esté inclinando?). Esa segunda exige un juicio de contexto que el 70B no sostiene con consistencia;
cada exclusión por dominio parcha un caso y abre otro. Confirma la predicción de TRASPASO
(2026-07-11): el enfoque per-prompt no separa fiable epíteto-que-tiñe de las demás familias.
Corolario medido: las ALUCINADA subieron con v4/v5A (citas recortadas: "macrocaso 01/03", "un paso
trascendental") — corrobora la deuda de borde-de-cita ya registrada; no es contenido inventado.
Decisión: se CONGELA el v4 como versión de referencia (es la mejor medida: mata el FP más peligroso
—atrocidad— y conserva TP reales; sus residuales clima/cultura son molestos pero mucho menos
graves). `encuadre` pasa a BAJA-CONFIANZA: NO encabeza el análisis de v1 ni dispara el termómetro.
NO se hace un v6: el umbral de corte se fijó antes de correr y el resultado lo cruzó. Reactivar SOLO
con un enfoque distinto (ver Ideas: clasificador dedicado / dos pasadas), no con otra versión de
prompt. El banco fijo queda para regresión futura.

### [2026-07-11] `encuadre` es caja de sastre — fix PARCIAL medido; necesita subtipos
Contexto: se probó la hipótesis de que el sobre-marcado venía de atribución (cita-de-actor).
REFUTADA con diag_atribucion.py: las 6 frases del caso RTVC estaban en VOZ DEL MEDIO (sin
comillas/«»/"según X"/verbo de dicción). Hallazgo real: "noticia ⇒ neutral" es FALSO — RTVC
(estatal) editorializa, que es justo lo que Trama existe para exponer. El bug verdadero: `encuadre`
absorbe cláusulas argumentativas completas en opinión (evidencia: citas largas, no epítetos).
Fix aplicado (find/replace en el SYSTEM del diag de artículo): definición con PRUEBA OPERATIVA
("quita el término valorativo; si queda un hecho neutro era encuadre, si queda una tesis/condicional
NO lo es") + 3 FP confirmados como ejemplos NO. Resultado MEDIDO (temp 0.15, banco: RTVC + opinión
La Silla + control Las2orillas/Calixto): control neutral limpio; cargados del medio sobreviven
("flagelo", "con vehemencia", "avance crucial"); PERO 2 de 3 FP de opinión SIGUEN colándose.
Conclusión honesta: mejora parcial. El enfoque per-prompt en un 70B no separa fiable epíteto-que-
tiñe-un-hecho de cláusula-argumentativa en opinión densa. NO es error de redacción; es límite.
Nota: temp=0 EMPEORA (mode collapse a encuadre, mete cláusulas enteras) → se mantiene 0.15.
Decisión: `encuadre` necesita SUBTIPOS o umbral de densidad — rediseño de taxonomía, no one-liner.
Reactivar: próximo paso #1.

### [2026-07-11] Los otros 5 códigos son inestables por definición floja
Síntoma: en opinión, miedo/falsa_dicotomia/arrastre aparecen y desaparecen entre corridas; a
temp 0.15 el rango oscila. Causa: a diferencia de `encuadre`, no tienen ejemplos SÍ/NO en el
prompt → el modelo titubea en el borde. Sospecha medida (no confirmada): parte de lo que marcan
en el borde son FP (p.ej. "no es si… sino cómo…" marcado como falsa_dicotomia es lo OPUESTO a la
definición). Decisión: reforzar definiciones (ejemplos SÍ/NO) es la sub-unidad siguiente, aparte
de encuadre (una variable a la vez). Reactivar: próximo paso #2.

### [2026-07-11] Representante por "más largo" surface el peor ejemplo (proxy tosco)
Síntoma: condensar.py con REPRESENTANTE="largo" elige, entre 5 encuadres, la cláusula más larga —
justo la que menos parece encuadre (p.ej. RTVC muestra "el mecanismo más robusto…" en vez de "un
flagelo…"). "Corto" tampoco es fiable (agarra "un complejo panorama político", el borderline).
Decisión: aceptado como default provisional; la selección fiable del representante es un mini-
problema de ranking → Idea, no esta unidad.

### [2026-07-11] `tipo` poco fiable entre medios — sub-clasificación, no realidad
Medido (query tipo×medio): El Espectador concentra el 98.3% de 'opinion'; El Tiempo y El Colombiano
salen con 0% de opinión, lo cual NO es real (publican columnas a diario) — no las capturamos/
clasificamos como tal. Impacto en Fase 3: NULO (la detección de técnicas es tipo-agnóstica; se
confirmó que una "noticia" RTVC editorializa y una opinión marca técnicas sin depender del rótulo).
Importa para: presentación/expectativa en front, features futuras que ramifiquen por tipo, y
muestreo limpio para nuestras pruebas (hoy no podemos sacar 'opinion' de casi ningún medio).
Decisión: DEUDA, no acción. Engancha con clasificador de tipo (Las2orillas/Vorágine) y filtro
opinión (La Silla). Reactivar: cuando una feature dependa de `tipo` o se quiera análisis por tipo.

### [2026-07-11] Proveedor Fase 3: DeepInfra PRIMARIO, NIM fallback — decidido y validado (con caveats)
Decisión: DeepInfra (meta-llama/Llama-3.3-70B-Instruct, precisión completa) como PRIMARIO;
NIM (meta/llama-3.3-70b-instruct) FALLBACK; Groq DEPRECADO. Supersede la decisión
NIM-primario del 2026-06-19. Motivo: NIM intermitente (504/WinError, medido); Groq con tope
diario bajo + modelo en decomisión 2026-08-16; Gemini 2.5 Flash-Lite EVALUADO y descartado
(percentil ~19 de inteligencia, insuficiente para grounding fino con FP casi-cero tolerado).
Validación (art 0c1deb55, RTVC, noticia JEP, --repetir 3, DeepInfra CONFIRMADO por print):
conteo estable 5-5-5, grounding 5/5·3/5·5/5, 0 alucinaciones de CONTENIDO, sin resets tipo
NIM. Costo efectivo medido ~$0.10/$0.32 por millón (más barato que el estimado; full
precision alcanza, NO hace falta Turbo/FP8). Pronóstico: batch incremental ~$1–2/mes,
backfill <$1 una vez → el costo NO es el gate de la fase.
CAVEAT 1 (medido): las 2 "ALUCINADA" de la corrida 2 fueron la MISMA frase groundeada pero
RECORTADA en el borde ("con vehemencia", "un mecanismo más robusto") → fallan el check de
subcadena verbatim SIN ser error de contenido. El modelo es estable en QUÉ marca, inestable
en DÓNDE corta la cita. Implicación batch: tolerancia de borde de cita o pedir la frase
completa, o habrá alucinadas fantasma. (Registrada aparte como su propia deuda.)
CAVEAT 2 (cobertura parcial): validado en UNA noticia; falta el lado "debe marcar"
(opinión/columna).
Fallback = DECISIÓN, no mecanismo: el failover automático DeepInfra→NIM NO está construido;
se implementa al construir el batch (Tier 3). Hoy solo conmutación manual por LLM_PROVIDER.
Cambio de código: diag_fase3_articulo.py recibió rama `deepinfra` (con defaults de base_url
y model) + línea `Provider: {PROVIDER} | modelo: {MODEL_ID}`, manteniendo las 3 ramas
alcanzables. (Diag desechable, no commiteado.)
Reactivar/re-medir SI: DeepInfra falla sostenido, o al construir el batch.

### [2026-07-11] Sobre-marcado voz-del-medio vs cita-de-actor — gap central de técnicas
Síntoma (medido): art 0c1deb55 es tipo=noticia y disparó 5 `encuadre` con grounding limpio.
Varias son CITA INSTITUCIONAL de la JEP reproducida por el medio ("un avance crucial en la
lucha contra la impunidad", "un paso trascendental para la consolidación de la paz estable y
duradera", "el mecanismo más robusto..."), NO voz editorial del medio. Una sí es voz del
medio ("defendió con vehemencia").
Causa: el prompt v3 marca lenguaje valorativo sin distinguir QUIÉN lo enuncia. Reproducir la
valoración de un actor citado ≠ el medio encuadrando. RTVC es estatal (parte puede ser
editorialización legítima), pero las citas institucionales son sobre-marcado.
Impacto: ALTO. Un falso positivo estable y bien-groundeado sigue siendo FP y viola "un FP
cuesta más que 10 FN". Construir el batch sobre este prompt inundaría el producto de FP.
Decisión: NO construir batch hasta cerrar este gap. Es el próximo paso #1. NO es de proveedor.
Reactivar: inmediato (próxima unidad). Banco: los 3 clústeres constantes + 1 opinión/columna.

### [2026-07-11] DeepInfra recorta la cita → ALUCINADA fantasma en el check verbatim
Síntoma: ver Caveat 1 arriba. El grounding (subcadena exacta ≥15 chars) marca ALUCINADA una
frase cuyo contenido SÍ existe, solo que el modelo la devolvió recortada.
Decisión: no arreglar en el diag (desechable). El BATCH debe manejarlo: tolerancia de borde
(p.ej. match por prefijo/ventana) o instruir "copia la frase completa". No filtrar por
verbatim estricto sin esto, o se descartan técnicas reales.
Reactivar: al construir el batch (Tier 3).

### [2026-07-11] diag_fase3_prompt.py: rama de provider rota (NIM inalcanzable)
Síntoma: líneas 30-39 — default PROVIDER="deepinfra"; el `else` comentado "# nvidia
(default)" en realidad lee DEEPINFRA_*. No hay rama NIM: cualquier valor ≠ groq cae en
DeepInfra. NIM inalcanzable desde este script.
Causa: hack previo a medias hacia DeepInfra (documentación contradice código — el patrón de
6e25379).
Impacto: no se puede sacar baseline NIM desde el script de clúster; y `resumen_neutral` (que
SOLO este script produce) no es conmutable de proveedor.
Decisión: NO tocar ahora (esta unidad usó el script de ARTÍCULO, con las 3 ramas correctas +
print). Arreglar ANTES de correr el de clúster para observar resumen_neutral.
Reactivar: al retomar resumen_neutral/omisión.

### [2026-07-11] diag_fase3_articulo.py: el veredicto de varianza mide conteo, no grounding
Síntoma: `--repetir` reporta "ESTABLE (±1)" comparando CONTEOS (5-5-5) pero ignora la
estabilidad del GROUNDING (5/5·3/5·5/5). La métrica que importa —¿las citas aguantan verbatim
entre corridas?— no se reporta.
Decisión: mejora menor pendiente del diag (desechable), no urge. Anotado para no confiar en
el veredicto a ojo.

### [2026-07-06] 2 autoref RTVC — aceptada, medida, permanente
Síntoma: 2 art. de RTVC pre-fix del filtro NER traen "RTVC Noticias" en entidades.
Causa: embebidos con el filtro roto (antes del fix 2026-07-05); el cron no los re-toca
(embedding no-nulo) ni el crawler los re-captura (hash sin cambio). Impacto MEDIDO: nulo
para clustering — solo 2 notas del MISMO medio la portan, y el motor salta pares
intra-medio antes de pesar entidades → aporte a compuertas = 0. Residual cosmético en
score_cobertura. Decisión: NO arreglar. Reactivar SI: re-NER dirigido a rtvc por otra razón.

### [2026-07-06] Omisión en Fase 3 sin validar — posible replanteo de diseño
Síntoma: el prompt v3 detectó 0 omisiones en 3 clústeres distintos (JEP 5 medios,
empalme 5, Uribe 7 art. completos), pese a grounding limpio en TÉCNICAS (4/5–6/6).
Causa probable (hipótesis, leída de Arquitectura §6): el clustering agrupa por MISMO
HECHO con dos compuertas en AND (IDF≥20 + coseno≥0.70). Esa cohesión hace que los
miembros cuenten los mismos hechos centrales → poca omisión intra-clúster. La omisión
fuerte rompe la similitud y el clustering separa esos artículos antes de que Fase 3 los
vea. Implicación: "omisión entre versiones del mismo hecho" es estructuralmente más rara
de lo que asumió la taxonomía §5. NO es bug del prompt. Decisión: replantear si "omisión"
pertenece al nivel INTER-clúster (story_relations) en vez de intra. Sin acción hasta
decidir con cabeza fría. Reactivar: al retomar Fase 3, antes de construir el batch.

### [2026-07-06] Escala de Fase 3 sin medir — gate de la fase
El batch de Fase 3 no se puede dimensionar sin medir: nº de clústeres ≥3 medios, tokens
por clúster, cabida en rate limits. MEDIDO esta sesión: NIM 40rpm sin tope de tokens
(candidato a batch completo) pero con 504 de disponibilidad intermitentes; Groq estable
y rápido pero free tier con tope diario bajo (~visto agotar a mitad con 2 corridas) →
inviable para batch completo, sí como fallback puntual. Decisión pendiente: batch-completo
vs incremental. Reactivar: es el próximo paso #1.

### [RESUELTO 2026-07-05] Filtro anti-autorreferencia de RTVC era código muerto (case-sensitivity en MEDIOS)

Síntoma: las 3 entradas de RTVC en `MEDIOS` (ner_filtro.py) — "RTVC", "RTVC Noticias",
"Señal Colombia" — se agregaron con capitalización original, pero `entidad_valida()`
compara `t.lower() in MEDIOS`. "rtvc" nunca estaba en el set (solo "RTVC" exacto), así
que el filtro no atrapaba ninguna auto-mención de RTVC. Código muerto desde el commit
que activó RTVC.

Impacto: entidades de auto-referencia de fuente sin filtrar pueden ligar clústeres por
FUENTE en vez de por hecho — mismo patrón ya resuelto para los otros 8 nombres. Insumo
del motor de n_especificas, así que ensucia los clústeres que Fase 3 analizará.

Fix (Opción B, defensiva): el set se auto-normaliza en su definición
(`MEDIOS = {m.lower() for m in {...}}`), de modo que agregar un medio nuevo con
cualquier capitalización no vuelve a escapar el filtro. Elimina la CLASE de bug, no solo
la instancia — relevante porque la propia doc instruye "al activar un medio nuevo,
agregar su nombre a MEDIOS". Fase A confirmó un único consumidor de MEDIOS (ner_filtro.py
línea 32) y que ningún uso depende de la capitalización original, así que reescribir el
set entero era seguro. Rama `fix/medios-case-insensitive`, en main.

Lección de proceso: al reescribir un set load-bearing, la validación debe cubrir TODOS
los literales, no solo los nuevos. El `git diff` autoritativo (11 literales intactos,
único cambio adicional un espacio en blanco) es el gate, no el auto-reporte de la
herramienta ni el resumen pegado en el chat (que llegó con corrupción de copy-paste).


### [RESUELTO 2026-07-05] analyses.story_id sin FK — landmine silenciosa de Fase 3

(Ver detalle de la migración en "Operaciones sobre datos", 2026-07-05.) Resumen de la
deuda: el recompute-total de clustering borraba `stories` cada 6h; el día que Fase 3
escribiera la primera fila en analyses con story_id poblado, la siguiente corrida habría
fallado al borrar stories (o, en el estado real sin FK, habría dejado story_id colgando
sin error). Determinístico. Resuelto con FK ON DELETE SET NULL + migración de
`reescribir_stories` a UPSERT.

Lección: `ON DELETE CASCADE` como respuesta refleja habría sido PEOR que el bug — en un
patrón de recompute-total, cascade borra todos los analyses cada 6h. Siempre revisar el
patrón de escritura antes de elegir la constraint.


### [PARCIALMENTE RETIRADA 2026-07-05] delete-then-insert no transaccional del clustering

Actualiza la entrada original (2026-06-23). `stories` ya NO se borra-y-reinserta: pasó a
UPSERT on_conflict=id, lo que preserva la identidad uuid5 estable y evita romper el FK de
analyses en el caso común. La poda de stories es ahora ACOTADA (solo huérfanas:
existentes − sids_actuales, en lotes de 500). La lectura de `existentes` se paginó a
~1000 filas (mismo patrón que la carga de artículos) tras detectar que un `.select()`
sin paginar truncaba la poda pasadas ~1000 stories y acumulaba historias fantasma en
silencio — misma clase de bug que la unidad venía a arreglar; lo cazó la revisión del
diff, no el dry-run (el stub in-memory no modelaba el tope de 1000 hasta que se amplió).

VIGENTE: `story_relations` y `story_articles` siguen con delete-total-then-insert cada
corrida (se recomputan enteros; ninguna tabla externa tiene FK hacia ellas). Esa parte
de la deuda no transaccional queda aceptada y fuera de alcance.


### [NUEVA 2026-07-05] Groq fallback de Fase 3 sin modelo de reemplazo

`llama-3.3-70b-versatile` (el modelo del fallback Groq documentado) se decomisiona el
2026-08-16. El primario en NVIDIA NIM (`meta/llama-3.3-70b-instruct`) es de otro catálogo
y no se ve afectado, pero el supuesto previo de "mismo model ID en ambos proveedores"
queda invalidado. Decisión: diferido hasta empezar Fase 3 o hasta acercarse al 2026-08-16,
lo que llegue primero. Al elegir reemplazo, validarlo de forma independiente (salida JSON
estricta en español, temperatura baja, sobre artículos reales) antes de adoptarlo.

### [RESUELTO 2026-06-28] Incidente CI clustering — NameError por orden de definición de canon (2026-06-28)

**Traza exacta:**
```
File "crawler/clustering_fase2.py", line 116, in <module>
    RUIDO_C = {canon(x) for x in RUIDO_DURO}
NameError: name 'canon' is not defined
```
El job `clustering` del cron falló en import, antes de cualquier escritura a Supabase.
**story_relations no fue corrompido** — el delete de `reescribir_stories` vive en
`main()`, nunca alcanzado. Estado del grafo = última corrida válida.

**Causa raíz confirmada (auditada con git blame + git show):**
Commit **6e25379** ("cambios regulares diarios de los md file", 2026-06-28) añadió
`RUIDO_C` y `GEO_C` como comprehensions a nivel de módulo en la posición incorrecta:
ANTES de `_LEAD` y `def canon`. Python evalúa el módulo top-to-bottom; al llegar
a `RUIDO_C = {canon(x) for x in RUIDO_DURO}`, `canon` aún no existe → NameError.
El mensaje del commit no mencionaba `clustering_fase2.py` (el archivo iba en el
mismo staging junto con los MD del día). **No fue un clobber de versión** (no se
perdió código entero), PERO tampoco fue solo un reorden: 6e25379 introdujo DOS
cambios sobre la versión validada 9410713 — (1) añadió `RUIDO_C`/`GEO_C` (que NO
existían en 9410713) en orden incorrecto → el NameError visible; (2) cambió
`es_especifica` de membership cruda (`RUIDO_DURO`/`GEOGRAFIA`/`GEO_EXTRA`) a
membership canonizada (`RUIDO_C`/`GEO_C`) — un cambio SEMÁNTICO al motor de
relaciones (qué cuenta como específica, base de `n_esp≥3`) que NUNCA fue medido.
Las constantes validadas (ALIAS, GEO_EXTRA, FRAC=0.08, n_esp=3, guardia=0.50,
centroide np.mean) sí seguían presentes; lo que cambió fue la LÓGICA de exclusión.

**Primer intento DESCARTADO (branch `fix/clustering-canon-order`, commit 91c8c78):**
Reorden mínimo: mover `RUIDO_C`/`GEO_C` después de `def canon`. Se RECHAZÓ porque
conservaba el cambio semántico no validado de `es_especifica` (membership canonizada).
Lo cazó `git diff 9410713 fix/clustering-canon-order`: `RUIDO_C`/`GEO_C` salían como
`+` (no existían en la versión validada) y `es_especifica` salía cambiada. El reporte
del ejecutor decía "reorden puro, todo intacto" — verificó PRESENCIA de constantes,
no EQUIVALENCIA de lógica.

**Fix aplicado (branch `fix/clustering-restore-validado`, commit ce4af7f):**
`git checkout 9410713 -- crawler/clustering_fase2.py` — restauración exacta a la
versión validada. Resultado: `RUIDO_C`/`GEO_C` ELIMINADOS, `es_especifica` revertido
a sets crudos (la forma que produjo el grafo validado de 68 aristas). Entre 9410713 y
hoy, lo único que tocó clustering fue 6e25379, así que no se pierde nada legítimo.
Diff neto: 1 insertion / 6 deletions. Mergeado a main por fast-forward (6e25379→ce4af7f).
**PENDIENTE: `git push origin main`** — al cierre de esta entrada, origin/main aún
estaba en 6e25379 (roto); el fix vivía solo en main local.

**Verificación:** el archivo restaurado es byte-idéntico a 9410713, el commit cuyas
métricas (68 aristas, hub Pastrana grado 3, andamiaje=0) ya estaban validadas. `findstr`
confirma: cero líneas `RUIDO_C`/`GEO_C`, `es_especifica` con membership cruda. No hay
nada nuevo que medir: es exactamente el estado validado. La próxima corrida del cron
reproduce el grafo conocido.

**Aprendizajes (dos; el segundo es el que evita el round 2):**
1. Commitear código junto con los MD del día sin mirar el diff staged contamina main
   con bugs silenciosos. Regla: `git diff --staged` obligatorio antes de confirmar,
   aunque el commit "parezca" solo docs; commits de docs SEPARADOS de los de código.
2. **El árbitro de un fix es el `git diff` contra la versión VALIDADA, no el "todo
   intacto" del ejecutor.** Claude Code reportó "reorden puro" verificando que las
   constantes seguían presentes; no verificó que la LÓGICA de `es_especifica` fuera
   equivalente a la validada. No lo era. Presencia ≠ equivalencia. Para todo hotfix
   sobre código load-bearing: diff explícito contra el último commit medido, y leerlo.

**Auditoría de consistencia docs↔código (2026-06-28):** ver tabla abajo.

| Afirmación (doc:sección) | Código (archivo:línea) | ¿Coincide? | Nota |
|---|---|---|---|
| "Grafo NO expuesto hasta el re-backfill de NER" (Arquitectura.md §6) | web/app/historia/[id]/page.js | **NO** | Re-backfill aplicado 2026-06-26; grafo expuesto 2026-06-27. Arquitectura.md no actualizada (solo Jota puede editarla) |
| "El clustering NO está en este workflow (sigue manual)" (BITACORA Notas de operación 2026-06-23) | .github/workflows/crawler.yml:77-95 | **NO** | Clustering ES el 3er job del workflow; encadenado desde commit 3560565. La nota era correcta en su fecha, hoy es stale |
| "FRAC_GENERICA = 0.08" (BITACORA 2026-06-27 recalibración) | clustering_fase2.py:44 | SÍ | ✓ |
| "UMBRAL_N_ESPECIFICAS = 3" (BITACORA 2026-06-27) | clustering_fase2.py:42 | SÍ | ✓ |
| "GUARDIA_COSENO_REL = 0.50" (BITACORA 2026-06-27) | clustering_fase2.py:43 | SÍ | ✓ |
| "centroide_de_cluster() = np.mean" (BITACORA 2026-06-25) | clustering_fase2.py:145 | SÍ | ✓ |
| "canon se aplica en TRES puntos: ... RUIDO_C/GEO_C canónicos" (BITACORA 2026-06-27 recalibración) | clustering_fase2.py `es_especifica` (post-restore) | **NO / CONTRADICCIÓN** | El código validado 9410713 canoniza solo DOS puntos (entrada de entidades + conteo df_cl); `es_especifica` usa sets CRUDOS. El "tercer punto" (exclusión canónica) que esa entrada describe NUNCA estuvo en el código validado — el grafo de 68 aristas se midió con exclusión cruda. 6e25379 intentó implementar ese 3er punto y rompió el import. Canonizar la exclusión es mejora SIN MEDIR (ver deuda nueva abajo), no estado validado. La entrada 2026-06-27 sobre-afirmó "3 puntos". |
| "n_esp≥3 ∧ cos≥0.50" (Arquitectura.md §6) | clustering_fase2.py:42-43 | SÍ | ✓ |
| "Centroide-por-medio: identificada, NO medida aún" (BITACORA Ideas 2026-06-25) | — | PARCIAL | Diagnóstico YA realizado (sesión posterior a esa entrada): 161 clústeres, 22 (14%) anclas cambian, sesgo direccional confirmado. El "NO medida" es stale; resultado en TRASPASO |

### Canonizar los sets de exclusión de `es_especifica` — mejora SIN MEDIR (2026-06-28)
Destapada por el incidente del 2026-06-28. Hoy `es_especifica` excluye contra sets
CRUDOS (`RUIDO_DURO`/`GEOGRAFIA`/`GEO_EXTRA`); canonizarlos (excluir contra
`{canon(x)...}`) es coherente con el resto de canon() y podría capturar formas de
superficie que hoy escapan a la exclusión. PERO no está medido: 6e25379 lo introdujo
sin medición y rompió el import; lo revertimos para reproducir el grafo validado, no
porque la idea sea mala. **Cómo entra bien:** implementar en branch, correr clustering,
comparar aristas/hub contra las 68 validadas + control de andamiaje (debe seguir en 0).
Si sostiene o mejora, entra con datos. Mismo estatus de "propuesta a medir" que el
split de centroide. NO tocar en caliente junto a otra cosa.


### Recalibración de relaciones: el problema era "qué cuenta como específica", no n_esp (2026-06-27)

Partimos de TRASPASO #1 ("la limpieza de NER baja n_esp, ¿hay que bajar el umbral a 2?").
**La pregunta estaba mal planteada.** Medido con diag_relaciones (v1→v3, read-only,
desechable): bajar a 2 sumaba 291 aristas de pura co-mención institucional; y subir tampoco
servía — el peor falso positivo tenía n_esp=15 (una lista de países: "La caída de Niño
Guerrero" ↔ "voto en el exterior"). La raíz eran TRES clases de basura en lo que el motor
contaba como específica: (1) duplicación de formas de superficie ("la procuraduría" /
"procuraduría general de la nación" = 3 formas, 1 referente), (2) geografía extranjera
contada como específica, (3) actores institucionales de DF medio (defensores de la patria,
registraduría, cne) que esquivaban FRAC=0.15.

**Fix (3 capas, ninguna toca n_esp ni la guardia), portado a la 2ª pasada de
clustering_fase2.py:** canon() + ALIAS (quita artículo inicial + dicc. acotado de siglas↔
expansión y fragmentos de nombre; NO fusiona instituciones hermanas), GEO_EXTRA (países/
regiones/ciudades extranjeras al filtro geográfico, antes solo Colombia), FRAC_GENERICA
0.15→0.08. canon se aplica en los TRES puntos: entrada de entidades, conteo df_cl (para que
las genéricas por DF se cuenten bien) y sets de exclusión (RUIDO_C/GEO_C canónicos).

**Medido (barrido de FRAC):** 0.15→191 aristas (aún madeja), 0.10→115, **0.08→68 (CORE 4/4)**,
0.06→51 (CORE 3/4: rompe Calavera↔24). Por eso 0.08 es el límite: el piso lo fija una
relación real (Calavera↔24) que descansa en {dijín, interpol, ejército nacional + el nombre
propio "elver vicente alfonso sanabria"}; en 0.06 los institucionales se vuelven genéricos y
queda solo el nombre → n_esp=1. Hub Pastrana 21→3. Andamiaje eliminado (control = 0).
**Decisión: n_esp=3 y guardia 0.50 NO se mueven** (consistente con cierre 2026-06-23 y con el
testigo Beto Coral, cos 0.589). Branch fix/relaciones-canon-frac008.

**Sub-decisiones con recibo:**
- **Air-e = FN aceptado.** Solo 2 específicas limpias (andeg + superservicios); cae bajo
  n_esp≥3. Bajar a 2 para salvarlo reabre la madeja (El Niño↔El Niño y Chalá↔Calavera también
  caen en 2, mezclados con co-mención del hub). Mismo patrón que Beto Coral para la guardia:
  costo de recall medido y aceptado, no se afloja el umbral global. Revisitar solo si Fase 3
  desambigua relaciones empresa-nombrada.
- **Retirar RUIDO_DURO (era TRASPASO #2) sigue bloqueado, ahora MEDIDO:** 9/50 términos
  sobreviven al NER limpio (incl. "match electoral de el espectador"). Viven en <11 clústeres,
  así que ni FRAC=0.08 los atrapa. Retirarlo re-contaminaría n_especificas. Disparador: mejor
  filtro de NER de cuerpo.
- **Grafo expuesto con cap de presentación.** /historia/[id]/page.js: Q3 por origen_id (espejo
  completo), top-5 por (n_especificas desc, coseno desc) + `<details>` "y N más". El cap de
  in-degree en LECTURA que se contemplaba queda SUPERSEDIDO para la vista per-historia: el
  top-5 ya contiene la densidad. Vuelve a hacer falta solo si se construye un grafo panorámico.

**Aprendizaje (autocrítica):** eyeball-ear de lejos engaña. Marqué "android/google/shakealert"
como basura de NER que tejía un FP entre dos sismos; Jota corrigió que es cobertura legítima
del sistema de alerta sísmica de Google — entidades reales y discriminantes. El criterio se
corrige con el dato concreto, no con la sospecha desde el título. NO se registró como deuda.

### Writes masivos uno-por-uno son frágiles — OBSERVADO (2026-06-26)
- **Síntoma medido:** el re-backfill (2732 UPDATE uno por uno sobre conexión HTTP/2
  persistente al pooler) se cortó a ~800 writes con WinError 10054 ("connection forcibly
  closed by remote host"). El pooler de Supabase cierra la conexión por volumen/duración.
- **Causa:** writes masivos sin resiliencia. Convierte en OBSERVADA la deuda teórica del
  delete-then-insert del clustering (registrada 2026-06-23): el modo de fallo es real.
- **Fix aplicado (en el re-backfill):** script REANUDABLE por diseño (UPDATE solo si las
  entidades cambian → re-correr salta lo ya limpio, sin archivo de checkpoint) + retry con
  backoff + reconexión ante corte + cliente fresco cada 300 writes. Criterio de
  consistencia: una corrida que diga aplicados=0.
- **Decisión:** NO robustecer el clustering ahora. Inserta por LOTES (no uno por uno) y
  aguantó esta corrida. Pero comparte el patrón; si al correrlo se corta, aplicar el mismo
  enfoque (su propia unidad de robustez, junto con la atomicidad del delete-then-insert).
- **Reactivar SI:** el clustering se corta a mitad en un run, o el banco crece y los writes
  empiezan a fallar/tardar.

### story_relations: esquema, criterio y limpieza congelada (2026-06-25)
- **Esquema (migración 000010):** grafo clúster↔clúster DIRIGIDO-ESPEJO. PK compuesta
  (origen_id, destino_id), FK a stories ON DELETE CASCADE, CHECK origen≠destino, índice
  (origen_id, n_especificas desc) para el cap de lectura, RLS + policy de SELECT pública.
  Columnas: n_especificas (MOTOR), coseno (GUARDIA), entidades_compartidas jsonb
  (EVIDENCIA, auditable + UI). Caché derivada pura: se borra/recomputa con stories.
  Dirigido-espejo (2 filas por par) elegido sobre no-dirigido: el cap de lectura es
  "top-K vecinos del foco" = índice limpio por origen, y la direccionalidad de Fase 3
  (derivada/reacción) entra sin rediseño. Costo 2× en tabla diminuta = trivial.
- **tipo_relacion OMITIDO a propósito.** DISPARADOR: al construir Fase 3, la anotación de
  LLM exige tabla aparte no-volátil (como analyses↔articles) o identidad estable de
  relación — el delete+insert del clustering la borraría. Añadir columna después es gratis.
- **Umbral VALIDADO: n_esp≥3 ∧ cos≥0.50. NO se apretó.** "Conservador = más estricto"
  rechazado con datos: cos≥0.55 tira Beto Coral (medido 0.544 en diag, 0.589 en producción),
  subir n_esp arriesga Air-e. Falso-negativo de apretar = MEDIDO; ganancia de precisión = NO
  medida. La banda n_esp=3 se audita sobre el grafo vivo; si sale basura se aprieta por n_esp
  dejando cos en 0.50.
- **Limpieza CONGELADA de diag v4 como mitigación TEMPORAL.** Excede la mitigación
  sancionada (medios + genéricas-por-DF): conectores sub-DF ("sin embargo", "hay") viven
  en <18 clústeres y genéricas-DF no los atrapa, solo el RUIDO_DURO completo. Sin él, los
  números validados no transfieren. RETIRO = re-backfill de NER (entonces la lista baja a
  medios + genéricas-DF). NO crecer la lista: ruido nuevo = señal de hacer el NER, no de
  añadir aquí. GATE: el grafo NO se expone en la web hasta el re-backfill de NER.
- **centroide_de_cluster() factorizado** (única fuente: calcular_scores + relaciones).
  ents_rel() separada de normaliza_ents (no se tocan las compuertas del clustering).
  DISPARADOR #2 (centroide-por-medio): se cambia 1 función y se REVALIDA la guardia de coseno.
- **O(clústeres²) sin ventana en la pasada 2** (a diferencia del ±72h del clustering de
  artículos). El coseno va gateado tras n_especificas, así que el cómputo es barato hoy.
  delete+insert ahora cubre 3 tablas (relations→story_articles→stories): ventana no
  transaccional más ancha, aceptada en frío a esta escala. Ver PROYECCION_ESCALA.
- **Reactivar/revisar SI:** el eyeball del grafo muestra basura (apretar n_esp), o llega
  el re-backfill de NER (retirar el RUIDO_DURO de conectores y quitar el gate de UI).

### Centroide no ponderado por medio sesga la neutralidad por volumen (2026-06-25)
- **Causa raíz (identificada, NO medida aún):** el centroide del clúster es np.mean de
  los embeddings de TODOS los artículos (calcular_scores, clustering_fase2.py), sin
  ponderar por medio. Si un medio domina en volumen dentro del clúster, el centroide se
  corre hacia su "centro de masa" → como neutralidad = cercanía al centroide, los
  artículos de ese medio salen sistemáticamente más "neutrales". Hipótesis de Jota: El
  Tiempo (alto volumen) queda anclado con frecuencia desproporcionada. Es el mismo sesgo
  de sobre-representación por volumen del feed, ahora DENTRO del clúster.
- **Fix candidato (decidido, pendiente de medir impacto):** centroide = promedio de los
  centroides-por-medio, sobre URLs colapsadas. Voto DURO: 1 medio = 1 voto, sin importar
  cuántas URLs aporte. Neutralidad pasa a medir "consenso ENTRE MEDIOS", no entre
  artículos. Ataca la causa raíz sin introducir sesgo nuevo.
- **Plan B (no de entrada):** si el voto duro da demasiado poder a medios de 1 nota
  ("poder de veto de la minoría" — un medio con 1 URL pesa 1/n_medios del centroide),
  amortiguar con peso 1/sqrt(n_notas_del_medio) en vez de voto duro. NO meterlo antes de
  medir: es optimización prematura. El efecto "voz a la minoría" se acepta de entrada
  como FEATURE (coherente con Trama: el ángulo minoritario no debe quedar aplastado),
  no como bug.
- **Lo que el fix NO toca (frontera explícita, para no esperar de más):** solo afecta la
  construcción del centroide → neutralidad. NO toca score_cobertura ni score_divergencia.
  NO resuelve el límite epistémico (si todos los medios comparten un punto ciego, el
  centroide lo hereda igual — eso es omisión, Fase 3). NO resuelve la asimetría del
  espectro mediático (curaduría, no fórmula).
- **DESCARTADO con razón:** ponderar por cobertura (idea inicial de Jota) — la cobertura
  premia mencionar muchas entidades, así que reforzaría las reacciones editorializadas
  densas (ya medido, caso Chalá 2026-06-17). Cambiaría "sesgo por volumen" por "sesgo por
  densidad de entidades". Dos males, no una solución.
- **Alcance del cambio:** la neutralidad re-ponderada es SOLO para elegir el ancla. NO se
  expone al usuario (coherente con la deuda de no exponer scores hasta que cobertura esté
  arreglada). Anotado: reevaluar ese nivel de transparencia con el usuario según evolucione.
- **Tier 2, load-bearing** (calcular_scores decide qué artículo representa el clúster en
  las cards). NO tocar sin medir impacto primero (ver diagnóstico en Ideas).
- **Reactivar/abordar SI:** el diagnóstico de impacto confirma dominancia frecuente Y que
  el ancla cambia en suficientes clústeres para mejor. Natural hacerlo ANTES de activar
  Semana/RTVC/La Silla, porque más medios con volumen asimétrico agravan el sesgo —
  medir el centroide-por-medio da la línea base.

### Relaciones inter-clúster: medición v1–v4 y decisión de criterio (2026-06-24)
- **Qué se midió (diag_relaciones v1→v4, read-only, desechables):** si existe un
  criterio para ligar clústeres relacionados (grafo de historias) sin fusionarlos.
- **Hallazgos con datos:**
  (1) El coseno entre centroides liga por TEMA, no por hecho (clima del domingo ↔
      resultados por ciudad: cos 0.86). No hay valle en su distribución. Sirve de
      GUARDIA, jamás de motor.
  (2) El peso IDF crudo estaba podrido de ruido NER: boilerplate de fuente ("match
      electoral de el espectador"), conectores ("sin embargo", "lea", "encuentre") y
      nombres de medios ("el tiempo", "el colombiano") — ligaban por FUENTE. El IDF
      premia lo raro, así que el boilerplate raro pesaba alto.
  (3) Limpieza en tres capas (ruido duro a mano + geografía clasificada-no-borrada +
      genéricas por DF de CLÚSTER) + métrica n_especificas: FUNCIONA para hechos
      discretos (Air-e, capturas, Arizabaleta, Beto Coral, Cauca, giro LatAm).
  (4) El macro-tema (campaña electoral) es un HUB IRREDUCIBLE. Medido: el cap de
      presentación NO lo desinfla (Pastrana in-degree 26 bajo cap top-5); cluster-IDF
      tampoco (26→23). Causa real: tamaño de clúster — Pastrana/Chalá tienen 125-134
      entidades específicas propias vs 31-40 de un hecho discreto → superficie de
      solapamiento gigante → tocan medio archivo por tamaño, no por relación.
  (5) mean_df (df-de-clúster promedio de las entidades propias) NO discrimina señal de
      ruido: separa "tema grande" de "hecho aislado". Hipótesis descartada con datos.
- **Decisión:** el criterio de story_relations será n_especificas ≥ umbral + coseno
  guardia. El hub se controla con CAP DE IN-DEGREE (+out-degree) en la capa de LECTURA
  (presentación, reversible), NO en la tabla. La distinción "contexto" vs "seguimiento"
  del macro-tema se DIFIERE a Fase 3 (LLM + tipo_relacion): ninguna vara de entidades la
  resuelve.
- **Reactivar/revisar SI:** al diseñar el esquema, el umbral elegido deja pasar madeja,
  o si la sobre-fusión (ver Ideas) resulta ser la causa raíz y la corrige.

### Ruido de NER contamina relaciones — el fix es upstream, no en relaciones (2026-06-24)
- **Síntoma medido:** aun con stoplist a mano, colaban "entidades" basura ("la captura",
  "según las autoridades", "los hechos") y nombres de medios. El stoplist a mano es
  perder: la cola de basura de NER es infinita.
- **Causa:** NER básico en backfill_fase2.py (ya registrado como Idea con disparador). A
  nivel artículo el IDF sobre miles de docs lo lavaba; a nivel de unión de entidades de
  clúster, el ruido se concentra y manda.
- **Decisión:** NO limpiar en la capa de relaciones (whack-a-mole). El fix de raíz es
  mejorar el filtro NER en backfill (Tier 2 load-bearing, requiere re-backfill) — su
  propia unidad. Las relaciones se protegen con genéricas-por-DF + stoplist duro acotado
  (medios) como mitigación, no como solución.
- **Reactivar SI:** se aborda la unidad de relaciones a fondo, o el ruido ensucia el
  grafo de forma visible al exponerlo.

### story_relations ensancha la ventana del delete-then-insert (2026-06-24)
- **Decisión en frío:** story_relations será caché derivada pura, recomputada en la
  misma corrida que stories (delete+insert). Coherente con "stories = caché derivada",
  pero AGREGA otra tabla a la ventana no transaccional ya documentada. A esta escala no
  muerde; registrado para no olvidarlo al hacer el clustering atómico/transaccional.
- **Reactivar SI:** se ataca la robustez del delete-then-insert (entonces cubrir ambas
  tablas), o el banco crece y la ventana de web vacía se vuelve inaceptable.

### Dependencias del clustering sin pin en CI (2026-06-23)
- **Síntoma:** ninguno aún. El job `clustering` de crawler.yml instala
  `pip install numpy supabase python-dotenv` sin versiones. El resto del proyecto
  instala desde requirements*.txt.
- **Riesgo:** un update mayor silencioso de numpy o supabase puede romper el
  clustering en un run nocturno (mismo patrón que ya mordió con `click` en backfill).
- **Decisión:** NO pinear ahora. El entorno es de 3 paquetes ligeros y a esta escala
  aguanta. Pero NO dejarlo silencioso — registrado para no repetir el olvido de
  backfill.
- **Fix de raíz (cuando muerda):** crear requirements-clustering.txt con `pip freeze`
  de un entorno limpio (solo numpy/supabase/dotenv + sus transitivas), apuntar el
  `cache-dependency-path` del job a ese archivo.
- **Reactivar SI:** un run de clustering falla por dependencia, o se actualiza numpy/
  supabase de versión mayor.

### Clustering delete-then-insert no transaccional (2026-06-23)
- **Síntoma:** ninguno medido. reescribir_stories() hace delete() de stories y
  story_articles, LUEGO inserta los clústeres nuevos. No es transaccional.
- **Riesgo:** si el script muere entre el borrado y el insert (timeout de Supabase,
  OOM, corte de red), las stories quedan vacías o parciales. La web mostraría "Fase 2
  en construcción" con datos reales en articles. Automatizado cada 6h, falla de
  madrugada y la web queda rota hasta el siguiente run o hasta que se note.
- **Por qué NO se atacó al automatizar:** a 1904 artículos el insert no falla; el
  recompute corre en ~2 min sin incidentes. Hacerlo transaccional/atómico (p. ej.
  escribir a tabla temporal y swap) es su propia unidad de robustez.
- **Decisión:** automatizar tal cual, documentar el modo de fallo.
- **Reactivar SI:** el banco crece y los inserts empiezan a tardar/fallar, o aparece
  tráfico real que haga inaceptable una ventana de web vacía.

### [VALIDADA — NO SE MOVIÓ] Umbrales provisionales del clustering (cierre 2026-06-23)
- La deuda "umbrales provisionales sin recalibrar con multitema" (abierta 2026-06-21)
  se cierra: recalibrados con datos sobre 105 clústeres multitema. Diagnóstico
  (diag_umbrales.py, read-only, recomputa la formación desde articles):
  529 aristas pasan ambas compuertas; histogramas de peso IDF y coseno densos por
  encima del corte sin valle que sugiera mover el umbral; casi-fallos por semántica
  (peso alto, coseno 0.65-0.70) son "mismo tema, distinto hecho" (captura Chalá vs
  homicidio periodista, etc.) — CORRECTOS de rechazar; casi-fallos por entidades
  (coseno alto, peso 15-20) son pares electorales genéricos — CORRECTOS de rechazar.
  Clústeres chicos (2-3) revisados a ojo: todos coherentes.
- **Conclusión:** IDF≥20 / coseno≥0.70 VALIDADOS con volumen multitema. NO se cambió
  ningún número — la metodología de dos compuertas aguantó el salto de 1 macro-tema a
  104 temas distintos. "Provisional" pasa a "validado".

### Árbol de dependencias de backfill en CI — parchado, no congelado (2026-06-23)
- **Síntoma:** al encadenar backfill a Actions, `import spacy` falló con
  ModuleNotFoundError: 'click'. click es dependencia transitiva de spaCy (vía su CLI)
  y la resolución de pip dejó el árbol inconsistente: pineamos spacy/sentence-transformers
  pero no sus transitivas.
- **Fix aplicado (camino rápido):** se agregó `click` explícito a requirements-backfill.txt.
  Funcionó. NO se hizo pip freeze del entorno local que sí funciona.
- **Decisión:** NO congelar ahora. El parche resolvió el único módulo faltante observado.
  Pero NO hay evidencia de árbol sano, solo de que click era lo único roto EN ESTE MOMENTO.
- **Riesgo:** un update transitivo de spaCy/torch/sentence-transformers puede volver a
  romper la resolución en un run nocturno silencioso (otro ModuleNotFoundError).
- **Fix de raíz (cuando muerda):** `pip freeze > requirements-backfill.txt` desde el
  entorno local validado, editando la línea de torch para dejarla sin pin (el step
  --index-url cpu la maneja antes). Replica en CI exactamente lo que funciona en local.
- **Reactivar SI:** un run de backfill vuelve a fallar por dependencia faltante, o se
  actualiza alguna de las libs ML pineadas.


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

### [2026-07-29] v2: resumen por DÍA-del-clúster + reevaluación per-artículo con GLM
(Ver TRASPASO > Ideas para el detalle completo de ambas. La primera es la dirección fuerte
post-v1: agrupación temporal que resuelve costo + confound + legibilidad, con síntesis por
día anclada al timeline. La segunda: separar las muertes por aritmética vs por capacidad
antes de reintentar cualquier pieza per-artículo con GLM.)

### [2026-07-22] Ideas de esta sesión
- Historias solo desde 3+ artículos (o 2 de medios distintos) — evaluación aparte (Jota).
- Pipeline híbrido de modelos (barato para corroborar, fuerte para síntesis): con GLM
  ganando ambas, no urge; optimización de costo futura.
- Cache de prompt en comparación ordenando pares por primer artículo (prefijo compartido).

### [2026-07-21] Patrón 4 (valoración en voz del medio) por extracción, no por juicio
Reencuadre para una fase posterior: en vez de que el LLM dictamine "este medio editorializa"
(normativo, columna débil, FP), que EXTRAIGA afirmaciones en voz del medio SIN atribución y
el lector juzgue. Punto difícil ya identificado: distinguir hecho no atribuido ("las mesas
abren a las 8am") de valor no atribuido ("el momento más emotivo") reintroduce el juicio.
Testeable, no asumible. Fuera de v1.

Sub-clustering por Louvain: cuando se retome divergencia inter-medio, es prerrequisito. Explorar si la resolución debe ser adaptativa al tamaño del clúster en vez de global.

### [2026-07-17] Taxonomía INDUCTIVA en vez de deductiva (si se reabre taxonomía)
La §5 se escribió ANTES de que existiera el corpus: son categorías de manual de retórica,
importadas de la literatura de propaganda, no inducidas de lo que los medios colombianos
realmente hacen. El archivo dice que 6 de esos 7 fenómenos, tal como se definieron, casi no
existen en él — y caen justo en los dos extremos donde nada funciona: `arrastre` demasiado
raro (0.15%), `encuadre` demasiado difuso (todo texto tiene palabras cargadas, el límite es
arbitrario). Ninguno cae en la zona donde un clasificador es posible.
**Cómo se haría bien:** muestrear 50 artículos al azar, LEERLOS, y preguntar "¿qué hacen ESTOS
medios que un lector debería ver?". La taxonomía sale del corpus, no del manual. Y la
prevalencia se mide antes de escribir una línea de prompt.

### [2026-07-17] Dónde es fuerte el 70B — guía de diseño para Fase 3+
FUERTE: comparar dos textos · distinguir cita de voz del medio · extraer, alinear, reescribir ·
detectar qué le falta a A que B sí tiene.
DÉBIL: juicios normativos abiertos · proporcionalidad ("¿es desproporcionado?") · encontrar
clases raras sin evidencia · emitir acusaciones categóricas.
**Toda la Fase 3 diseñada hasta hoy vivía en la columna derecha. Toda.** Y no hay upgrade de
modelo que lo arregle: un modelo mejor sube la especificidad de 99.28% a 99.7% y la precisión
sigue en 30%. **Cambiar de modelo es la trampa más cara disponible: cuesta semanas y no mueve
el número.**

### [2026-07-17] `regex -> LLM filtra` como arquitectura general
El regex da RECALL (barato, auditable, sin alucinación). El LLM da PRECISIÓN sobre un span ya
acotado. Tres efectos: (1) sube la base rate en el punto de decisión ~100× (0.15% -> 17.5% en
el caso de arrastre); (2) elimina la FABRICACIÓN por construcción — el span viene dado, no hay
nada que inventar; (3) baja el costo de 6562 llamadas a 57. Aplicable a cualquier código con
ancla léxica. **Es la única forma en que la opción (b) es viable** — y sigue bloqueada por la
falta de oráculo.

### [2026-07-17] Gate de grounding verbatim = FILTRO DE PUBLICACIÓN, no control de calidad
Si el output es "El Tiempo dice «X literal», El Espectador dice «Y literal»", el código
verifica que ambas citas existan verbatim en sus artículos. Si no están, **no se publica**.
Es `in`: determinista, sin humano, sin oráculo. Convierte la alucinación en estructuralmente
IMPUBLICABLE — exactamente lo que la clasificación nunca pudo tener (no hay forma mecánica de
verificar "esto es manipulación"; sí la hay para "esta frase está en este artículo").
**Es lo que permite ir rápido en el carril de comparación sin bajar el estándar.** Consecuencia:
la deuda "DeepInfra recorta cita -> alucinada fantasma" sube de detalle a load-bearing.

### [2026-07-17] El riesgo del carril de comparación: no acusa, pero puede MENTIR
"El Espectador omitió que el juez ordenó la captura" — si El Espectador SÍ lo dice, es un error
factual, publicado, **refutable por cualquiera en diez segundos**. Ante FLIP es peor que la
acusación, porque se cae solo. El gate de grounding es la mitigación, pero la asimetría cambia
de forma, no desaparece. No olvidar al diseñar.

### [2026-07-17] Matar Fase 3 entera es una opción real y defendible
Archivo inmutable + versiones lado a lado YA es un producto, YA está en producción, y no
promete nada que una IA no pueda cumplir. Si el carril de comparación tampoco mide bien, no
forzarlo. Registrado explícitamente para que el yo-del-futuro no lo lea como derrota sino como
salida legítima.

### 2026-07-17 — Carril de divergencia inter-artículo como señal (idea de Jota)
Usar el desacuerdo ENTRE medios sobre el mismo hecho para separar HECHO de TESIS sin pedirle al
LLM ese juicio: si los 7 medios dicen que el sismo fue superficial, es hecho; si uno solo dice que
"corre el riesgo de perder su carácter técnico", es tesis. Darle a la corrida per-artículo el
contexto de los ángulos de los demás artículos de la historia, sin que el modelo lea todo (ahorro
de créditos).
**Por qué se registra y no se construye hoy:** (a) es, en el fondo, el diseño original de
`omision`/`resumen_neutral`, ya diferido a v3.1 — no es idea nueva, es el plan original, y eso
sugiere que el carril inter-artículo quizá era el de valor y el per-artículo el desvío;
(b) CAVEAT MEDIDO: el fallo de hoy NO fue por falta de información — el ejemplo negativo estaba
VERBATIM en el prompt y el modelo lo marcó igual. Más contexto no arregla un problema de atención;
(c) CAVEAT MEDIDO: el modo clúster ya se degrada con contexto largo (19 art → colapsa a 4 entradas,
504s). Construir sobre ese cimiento cuesta más y ya sabemos que está rajado.
**Condición para promoverlo a scope:** unidad propia, con un diseño que NO sea "meter el clúster
entero al prompt" (p. ej. señal calculada por código —divergencia de embeddings/entidades— que se
INYECTA como dato, no como texto a leer). Decisión de alcance pendiente (TRASPASO, Próximo paso #1).

### [2026-07-12] `encuadre` por enfoque distinto — post prompt-engineering
El prompt único falló porque mezcla dos tareas que el 70B no hace juntas: EXTRAER el candidato
valorativo (lo hace bien) y JUZGAR el contexto (¿hecho público en disputa atribuible a un actor?
— no fiable). Enfoque a explorar cuando se retome: dos pasadas — (1) candidatos por léxico
valorativo, alta cobertura; (2) verificación separada del contexto, prompt corto y enfocado, o un
clasificador dedicado. NO es scope de v1. `encuadre` entra a v1 como baja-confianza o fuera del
feed público.

### [2026-07-11] Unidad de PRESENTACIÓN de Fase 3 (post-extracción, determinista)
Separación confirmada: el LLM EXTRAE átomos groundeados (exhaustivo); el CÓDIGO condensa para el
humano (span de atención corto). Prototipado hoy: condensar.py (colapso 1 representante + ×N por
código, orden por severidad; validado en 3 artículos reales). Pendientes de la unidad: técnicas
dominantes por conteo; TERMÓMETRO rojo/amarillo/verde DETERMINISTA (densidad de técnicas
groundeadas × severidad, jamás color "sentido" por el LLM — infalsificable); FRASE-RESUMEN
groundeada tipo "parece editorial argumentativo…" (derivada de las técnicas, no libre); DISCLOSURE
del prompt + disclaimer IA, ELEVADO A PRINCIPIO (publicar veredictos de IA sobre opacidad mediática
sin revelar el método sería la misma opacidad que Trama critica). Va DESPUÉS de extracción confiable.

### [2026-07-11] Selección de representante como problema de ranking
"Más largo/más corto" es proxy tosco. Elegir el epíteto más claro entre N encuadres es ranking
(p.ej. por longitud de la porción valorativa, densidad de calificativos, o score de "epíteto-idad").
Sub-problema de la unidad de presentación.

### [2026-07-11] Expansión deliberada de la taxonomía — NO es cambio de display
Un top-5 con nombres nuevos ("Framing moral", "Urgencia histórica", "Apelación a autoridad") NO es
la taxonomía actual (6 códigos) y no trae grounding → generarlo libre sería fabricación, justo lo que
Fase 3 combate. Si la taxonomía se queda corta, expandirla es proyecto calibrado: cada código con
ejemplos SÍ/NO, grounding verbatim y medición de FP/FN. No se mezcla con la capa de presentación.

### [2026-07-06] Grounding como métrica permanente + filtro de producción
El validador de grounding (evidencia debe existir verbatim en la fuente) no solo valida:
en producción, filtrar las entradas ALUCINADA antes de escribir a analyses convierte un
prompt con recall alto + precisión imperfecta en salida limpia. El sistema es robusto a
un prompt imperfecto. Idea: registrar grounding accuracy por corrida como métrica de
salud de Fase 3. (No construir framework de evaluación completo ahora — scope de más.)

### [2026-07-06] Comparación de modelos como Fase 3.5
Con el prompt v3 como banco (constante), comparar modelos free tier (NIM Llama 3.3,
Groq, Qwen, GPT-OSS) por grounding accuracy + hallucination rate + coste/latencia.
Fusionar con la decisión del sucesor de Groq (decomiso 2026-08-16). Solo DESPUÉS de
cerrar escala y omisión. Descartadas de plano: NVIDIA Blueprints (orquestación que
mata la portabilidad swappable).

### Upgrade de navegabilidad y estética (propuesta 2026-07-02, POST estructura principal)

Propuesta de auditoría, NO implementada. Para cuando la estructura principal del proyecto
esté cerrada. Priorizado por esfuerzo/impacto, todo dentro del sistema de diseño cerrado
(tokens --tinta/--papel/--hilo, Archivo Black + Source Serif 4 + IBM Plex Mono, esquinas
rectas, sin gradientes/sombras, cero-JS de cliente):

- **Filtro por medio en /historias** — esfuerzo BAJO (mismo patrón Server Component que
  ControlOrden/PresetsFecha), impacto ALTO con 7 medios activos. El candidato #1.
- **Ícono "ⓘ" contextual con `<details>`/`<summary>` nativo** — destraba explicar al
  lector los scores/técnicas de Fase 3 sin romper cero-JS. Sinergia con Fase 3.
- **Nav móvil oculto <560px** — deuda de navegación ya conocida; revisar al abordar esto.
- **Hilo rojo curvo (SVG)** — identidad visual, impacto funcional bajo. Lo último.
- **Búsqueda paginada** — ya en deudas; encaja aquí como mejora de navegación.

Cada uno es su propia unidad, con su Tier y su cierre. NO mezclar con la ruta crítica de
Fase 3.

### Destilar la vista de historia para no saturar al lector (idea, 2026-06-27)

Jota: "más adelante tendremos que destilar y limpiar para que no se sature de mucha
información y agote al lector de entrada." La vista /historia/[id] ya colapsa por defecto
(hilo: 3 visibles + resto; versiones: 2 + resto; conectadas: top-5 + N más), pero el criterio
de QUÉ mostrar primero sigue siendo crudo (las 3 primeras del hilo = las más antiguas por
orden cronológico). Cuando se llegue a esta pasada, decidir con la página enfrente: ¿primeras
en el tiempo? ¿las de medios más divergentes? ¿resumen de Fase 3 arriba y el resto plegado?
Es decisión de PRODUCTO, no de plumbing; no resolver en abstracto. (Quedó comentario-rastro
en el código del hilo.)

Micro-pendiente asociado: un segundo "ver menos" al FINAL del contenido largo desplegado
(hoy el toggle queda arriba, en la posición del "ver más", por ser <summary> nativo). Ponerlo
abajo requeriría JS de cliente — se difiere para no romper el principio cero-JS; el de arriba
cubre el 90%. Si el contenido es tan largo que molesta volver arriba, la señal es que ESE
clúster necesita destilado, no un botón más.

### Vía OR para reacciones entity-sparse en story_relations (idea, 2026-06-25)
- **Observación medida:** el motor solo-n_especificas deja fuera enlaces de cos alto y
  pocas específicas (1–2) — justo "hecho y su reacción", el corazón del grafo. Ej. extremo:
  Air-e liquidación↔pushback (cos 0.899, ~2 específicas reales tras quitar geografía).
- **Por qué es separable de la madeja:** los pares-madeja que se rechazaron (clima
  domingo↔resultados ciudad, cos 0.86) tienen ~CERO específicas (todo geografía); las
  reacciones reales sí tienen 1–2. Una vía OR "(n_esp≥3) OR (cos≥~0.85 AND n_esp≥2)"
  podría recuperarlas sin readmitir la madeja.
- **NO implementar por inferencia.** Antes: un diag del cuadrante cos-alto/n_esp-bajo para
  medir cuántas reacciones legítimas viven ahí. Solo si el eyeball del grafo vivo muestra
  que faltan. v1 va con compuerta única.

### Diagnóstico read-only: impacto del centroide ponderado por medio (2026-06-25)
- **Destraba la deuda "centroide no ponderado por medio".** Mide ANTES de tocar
  calcular_scores (Tier 2 load-bearing). Corrible sobre el snapshot estático que Jota
  monta a archivos del proyecto (no necesita la base viva).
- **Cuatro preguntas que debe responder:**
  (1) DOMINANCIA: ¿cuántos de los ~122 clústeres tienen un medio con mayoría de URLs?
      Si la mayoría son equilibrados (2-2, 3-2), el fix casi no mueve nada → no vale tocar
      load-bearing. Si muchos son 5-1-1, es real. ESTE número decide si el fix se justifica.
  (2) CORRELACIÓN: ¿el ancla principal actual correlaciona con el medio dominante en
      volumen? (¿se confirma la hipótesis de El Tiempo?).
  (3) DELTA: recalcular el centroide con voto-por-medio y contar en cuántos clústeres
      CAMBIA el ancla. Pocos → no vale; muchos → real.
  (4) CALIDAD: en los que cambian, juzgar a ojo si el ancla nuevo es más representativo
      o es una rareza de un medio de 1 nota (validación del "poder de veto de la minoría").
- **Unidad propia, measure-first.** NO mezclar con el chat del esquema story_relations ni
  con el de activar medios nuevos. Si los datos confirman impacto, recién ahí se toca
  calcular_scores en su propia unidad con Claude Code.

### Relaciones inter-clúster: medición v1–v4 y decisión de criterio (2026-06-24)
- **Qué se midió (diag_relaciones v1→v4, read-only, desechables):** si existe un
  criterio para ligar clústeres relacionados (grafo de historias) sin fusionarlos.
- **Hallazgos con datos:**
  (1) El coseno entre centroides liga por TEMA, no por hecho (clima del domingo ↔
      resultados por ciudad: cos 0.86). No hay valle en su distribución. Sirve de
      GUARDIA, jamás de motor.
  (2) El peso IDF crudo estaba podrido de ruido NER: boilerplate de fuente ("match
      electoral de el espectador"), conectores ("sin embargo", "lea", "encuentre") y
      nombres de medios ("el tiempo", "el colombiano") — ligaban por FUENTE. El IDF
      premia lo raro, así que el boilerplate raro pesaba alto.
  (3) Limpieza en tres capas (ruido duro a mano + geografía clasificada-no-borrada +
      genéricas por DF de CLÚSTER) + métrica n_especificas: FUNCIONA para hechos
      discretos (Air-e, capturas, Arizabaleta, Beto Coral, Cauca, giro LatAm).
  (4) El macro-tema (campaña electoral) es un HUB IRREDUCIBLE. Medido: el cap de
      presentación NO lo desinfla (Pastrana in-degree 26 bajo cap top-5); cluster-IDF
      tampoco (26→23). Causa real: tamaño de clúster — Pastrana/Chalá tienen 125-134
      entidades específicas propias vs 31-40 de un hecho discreto → superficie de
      solapamiento gigante → tocan medio archivo por tamaño, no por relación.
  (5) mean_df (df-de-clúster promedio de las entidades propias) NO discrimina señal de
      ruido: separa "tema grande" de "hecho aislado". Hipótesis descartada con datos.
- **Decisión:** el criterio de story_relations será n_especificas ≥ umbral + coseno
  guardia. El hub se controla con CAP DE IN-DEGREE (+out-degree) en la capa de LECTURA
  (presentación, reversible), NO en la tabla. La distinción "contexto" vs "seguimiento"
  del macro-tema se DIFIERE a Fase 3 (LLM + tipo_relacion): ninguna vara de entidades la
  resuelve.
- **Reactivar/revisar SI:** al diseñar el esquema, el umbral elegido deja pasar madeja,
  o si la sobre-fusión (ver Ideas) resulta ser la causa raíz y la corrige.

### Re-backfill de NER — fix de raíz del ruido de entidades (2026-06-26)
- **Resuelve** la deuda registrada 2026-06-24 ("Ruido de NER contamina relaciones — el
  fix es upstream"). No reescribo esa entrada (append-only); esta la cierra.
- **Diagnóstico measure-first, dos pasos:**
  (1) Diag A (snapshot CSV, read-only, lo corrió Claudio): el filtro que se barajaba
      —"descartar si el primer token es artículo/preposición"— FALLA por los dos lados.
      Mata señal real (La Guajira, La Fiscalía, los Estados Unidos, El Salvador, El
      Consejo Nacional Electoral; ~1509 ocurrencias) Y deja pasar ruido (No se pierda,
      Siga leyendo, Estamos, Gobierno nacional; ~1500+). Ningún filtro a nivel de string
      separa: el ruido viene capitalizado por inicio de oración, así que "minúscula
      inicial" no sirve.
  (2) Diag B (spaCy es_core_news_md, muestra 200, en máquina de Jota): el discriminador
      correcto es morfosintáctico — conservar la entidad si tiene ≥1 token PROPN o es
      sigla en mayúsculas. Descarta MISC 56,8%, conserva PER/ORG/LOC ~96%. El ~4% de
      PER/LOC/ORG descartado NO es señal: es ruido que spaCy MAL-ETIQUETÓ como entidad
      (Además→LOC, Según→PER, Estamos→ORG). El filtro PROPN es más robusto que el propio
      label de spaCy. Rescata siglas (CNE, DANE, CIDH, CTI). MISC se DEJA en TIPOS_ENT: el
      43% que conserva es señal con PROPN (eventos); el filtro la separa sin tratar el
      label como criterio.
- **Decisión de diseño:** filtro en ner_filtro.py como FUENTE ÚNICA, importado por
  backfill_fase2.py (futuros) y rebackfill_ner.py (banco). Una sola definición = pasado y
  futuro consistentes (evita el riesgo de divergencia de duplicar la lógica). Regla:
  ≥1 PROPN o sigla, no-medio (MEDIOS = lista CERRADA; NO crecer con boilerplate, eso es
  deuda de extracción), topes 60 chars / 8 tokens. DIVISIÓN DE TRABAJO: el filtro NER quita
  lo que NO es entidad; las genéricas reales (Petro, Gobierno nacional) las sigue manejando
  el IDF / FRAC_GENERICA, no el filtro. De paso corrige el bug viejo count(" ")>4, que
  mataba institucionales largas legítimas (Instituto Colombiano de Bienestar Familiar).
- **Dry-run (2732 art., sin escribir):** −20,2% entidades. 2 vacíos (notas cuyo NER era
  100% ruido — correcto, no anclan clúster). 80 ganancias (recuperación de largas con
  PROPN; mecanismo del bug viejo). Mayores pérdidas concentradas en horóscopos/opinión
  (ruido puro: tarot, primera persona, conectores). Ningún medio colapsa; voragine limpia
  más (26%, coherente con extracción trafilatura-only) pero queda con mediana 10,5 y cero
  vacíos.
- **Impacto en stories (medido contra snapshot _stories_pre_ner):** 151→149. uuid
  sobreviven 143 (94,7%), rotos 8, nuevos 6. El −2 neto = disolución de uniones espurias
  que existían por compartir boilerplate de alto IDF (uniones por fuente, no por hecho).
  Es el efecto buscado, no un daño. 8 enlaces /historia/[id] rotos: bajo, no dispara la
  tabla de identidad. Conexión con la sospecha de sobre-fusión (TRASPASO previo #2): el
  re-backfill atacó parcialmente esa causa (boilerplate inflando la compuerta 1).
- **Inmutabilidad:** UPDATE SOLO de entidades (campo derivado); contenido_visible/hash
  intactos. Coherente con stories = caché derivada.
- **Reactivar/revisar SI:** se cambia el filtro NER de nuevo (re-correr el re-backfill), o
  un medio nuevo se activa (agregar a MEDIOS), o aparece una clase de ruido que el filtro
  PROPN no atrapa (medir antes de tocar).

### Ruido de NER contamina relaciones — el fix es upstream, no en relaciones (2026-06-24)
- **Síntoma medido:** aun con stoplist a mano, colaban "entidades" basura ("la captura",
  "según las autoridades", "los hechos") y nombres de medios. El stoplist a mano es
  perder: la cola de basura de NER es infinita.
- **Causa:** NER básico en backfill_fase2.py (ya registrado como Idea con disparador). A
  nivel artículo el IDF sobre miles de docs lo lavaba; a nivel de unión de entidades de
  clúster, el ruido se concentra y manda.
- **Decisión:** NO limpiar en la capa de relaciones (whack-a-mole). El fix de raíz es
  mejorar el filtro NER en backfill (Tier 2 load-bearing, requiere re-backfill) — su
  propia unidad. Las relaciones se protegen con genéricas-por-DF + stoplist duro acotado
  (medios) como mitigación, no como solución.
- **Reactivar SI:** se aborda la unidad de relaciones a fondo, o el ruido ensucia el
  grafo de forma visible al exponerlo.

### story_relations ensancha la ventana del delete-then-insert (2026-06-24)
- **Decisión en frío:** story_relations será caché derivada pura, recomputada en la
  misma corrida que stories (delete+insert). Coherente con "stories = caché derivada",
  pero AGREGA otra tabla a la ventana no transaccional ya documentada. A esta escala no
  muerde; registrado para no olvidarlo al hacer el clustering atómico/transaccional.
- **Reactivar SI:** se ataca la robustez del delete-then-insert (entonces cubrir ambas
  tablas), o el banco crece y la ventana de web vacía se vuelve inaceptable.

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

### [2026-07-29] Pipeline Fase 3 v1 integrado y probado end-to-end
Módulo crawler/analisis_fase3.py (Claude Code). Contrato: 3 prompts congelados de los diag
validados. Resumen = 2 llamadas SEPARADAS (corroboración -> síntesis) para que la síntesis
solo vea spans verificados (anti-fabricación). Matching por slug. Gate verbatim sobre TODA
lista de spans (Claude Code lo extendió a solo_un_medio — correcto). Caché por hash de
contenido. Robustez: try/except por ítem + retry (lección del bake-off aplicada al módulo).

Probado sobre story 84a548f5 (11 arts, 55 pares): corre sin colgar (3.14 tolerable con
no-streaming), caché confirmado (2ª corrida 54/56 skip, reanuda incremental), fallos de
JSON transitorios de GLM (no sistemáticos, desaparecen al reintentar, ~0-3.6%).

HALLAZGO clave: costo CUADRÁTICO. 55 pares = 30 min. Beats de 90 y 128 arts = 36h y 73h.
El split de beats deja de ser "prerrequisito" y pasa a BLOQUEANTE absoluto del backfill:
sin él, una corrida no termina y el cron nunca cierra.

Síntesis leída: buena pero con causalidad no respaldada ("cierre de 14 embajadas... lo que
implicará romper relaciones únicamente con Cuba y Nicaragua"). El ojo de Jota lo cazó; el
verificador no lo cubre. Confirma que la síntesis es la capa menos garantizable.

### 2026-07-17 (2ª sesión) — CARRIL PER-ARTÍCULO CERRADO. La aritmética del falso positivo.

**Qué se midió.** Unidad Tier 0 (opción "d"): ¿el LLM se gana el puesto en el carril
per-artículo? Método: lexicón determinista de `arrastre` (12 patrones núcleo, fieles
LITERALES a la prueba operativa congelada, aprobados por Jota ANTES de correr) contra el
corpus completo. Umbral fijado ANTES: P_lex >= 0.90 -> detector determinista, batch
cancelado; P_lex < 0.90 -> el LLM es el filtro de precisión.

**Resultado.** Corpus 7046 filas / 6562 URLs únicas (recapturas 484 = 6.9%, MUY por debajo
de lo que se creía). N_hits = 57 spans en 55 artículos = **cobertura 0.84%**.
**P_lex = 10/57 = 0.175.** Control `unánime` (exclusión dura): 10/10 correctos — la
exclusión funciona. **Positivos reales estimados: ~10 artículos en TODO el archivo = 0.15%.**
Causa de los 47 FP: ~23 cita de actor, ~10 queda un hecho, ~11 trivial sin tesis en disputa,
2 bugs de regex.

**El umbral se cumplió y aun así la conclusión es la contraria a la esperada.** Formalmente:
P_lex < 0.90 -> "el LLM ES el filtro, batch justificado". Y es cierto: el lexicón solo es 82%
basura y filtrar es justo lo que un 70B hace bien. Pero se gana el puesto **para producir DIEZ
etiquetas en toda la hemeroteca**. La opción (a) del TRASPASO ("v1 = arrastre solo a
presentación + batch") muere aquí, con datos, no con opinión. El BATCH Tier 3 se CANCELA: 55
artículos son un `for` loop de 2 minutos, no un pipeline con failover y retry-backoff.

**EL HALLAZGO CENTRAL — la aritmética del falso positivo.** No es el modelo. No es el prompt.
Es que la clase es demasiado rara para que la precisión exigida sea alcanzable por NADA:
> Con prevalencia 0.15% y umbral 0.90, se exige especificidad 99.983% — un error cada 6.000
> juicios. Ningún clasificador humano ni artificial hace eso.
El lexicón logró especificidad **99.28%** (47 FP sobre 6552 negativos) y dio 17.5% de
precisión. El denominador manda, no la calidad del detector.
**Las dos premisas del proyecto eran sensatas por separado y contradictorias juntas:** "un FP
cuesta más que diez FN" (correcta, y es lo que ha protegido al proyecto) + clase al 0.15%
(medida) = imposible. Se ejecutó esa contradicción durante semanas, correctamente. Por eso
ningún código pasaba: no era mala suerte ni mala mano con los prompts.

**MATIZ que no se puede perder:** la aritmética mata la CLASIFICACIÓN A CIEGAS sobre 6562
artículos. NO mata `regex propone span -> LLM juzga sí/no`. Ahí la base rate en el punto de
decisión es **17.5%, no 0.15%** — dos órdenes de magnitud. Y la fabricación se vuelve
imposible: el span viene dado.

**ESTO EXPLICA RETROACTIVAMENTE LA FABRICACIÓN.** La entrada de esta mañana registró como
misterio que `atribucion_difusa` inventara spans y `arrastre` no. Ya no es misterio: se le
pidió cazar a ciegas una clase casi ausente con un prompt que le enseña a buscar. Un modelo
obediente mandado a buscar agujas en pajares SIN agujas **fabrica agujas**. La alucinación no
fue defecto del código: fue la respuesta correcta a una tarea mal planteada. Deja de ser
anomalía y pasa a ser **predicción**: cualquier código de baja prevalencia buscado a ciegas
fabricará.

**Por qué el banco mintió (aplica a TODA la validación de Fase 3).** Banco de arrastre: 3
positivos + 2 negativos = prevalencia 60%. Archivo real: 0.15%. **400× de diferencia.**
FN=0/FP=0 sobre banco balanceado no predice NADA sobre precisión en archivo desbalanceado. No
se midió mal — se midió otra cosa (separabilidad), con rigor. Todo banco futuro debe declarar
su prevalencia y qué mide.

**REGLA NUEVA, no negociable:** *ningún código entra a probe sin medir su BASE RATE primero.
Si es <1%, la precisión alta es inalcanzable: se cambia la TAREA, no el prompt.* Esto habría
matado `arrastre` el mismo día que se coronó como único código de v1.

**El predictor v3 sobrevive pero baja a secundario.** Sigue siendo cierto (disparador de
superficie compartido + estatus epistémico distinto = no separable), pero responde
"¿es domesticable?" — y la prevalencia responde "¿es rentable?". `arrastre` pasó v3 y es
inútil igual. Base rate PRIMERO, v3 después.

**Prueba de que el prompt no era el problema.** Ya estaba en la evidencia y no se había leído
así: en el probe de `atribucion_difusa` se puso un contraejemplo VERBATIM, carácter por
carácter, en el SYSTEM, y el modelo marcó la frase igual. Cuando el prompt perfecto no
funciona, el problema no es el prompt. El tamaño de estos prompts es la CICATRIZ de intentar
arreglar por instrucción algo que no era problema de instrucción.

**Herramienta.** `diag_arrastre_lexico.py` (Tier 0, read-only, DESECHABLE, no se commitea).
Tres versiones: v1 murió por payload (coarse ilike

### 2026-07-17 — PROBE de `atribucion_difusa`: RECHAZADO (FP=4/4). Predictor v3.

**Setup.** Banco propio: 3 positivos (57126171 "fuentes consultadas creen que… debería";
31992e94 "algunos analistas señalan… corre el riesgo"; 0c574952 "para algunos sectores no deja
de ser llamativo") + 4 negativos duros (940dcc4c fuente reservada→identidad; a38be86f expertos→
hecho geológico; d209382f fuentes familiarizadas→evento CIA; 80d6f651 ruido léxico puro).
DeepInfra, Llama-3.3-70B, temp 0.15, --repetir 3. Umbral fijado ANTES: todos los pos marcan 3/3
con grounding OK, todos los neg vacíos 3/3.

**Resultado: NO PASA.** 4/4 negativos dieron FP, estables en 3/3. 2/3 positivos pasaron;
57126171 falló por grounding (2 de 4 spans ALUCINADOS, estables).

**Por qué importa el CÓMO falló (esto cierra la puerta a iterar el prompt):**
El SYSTEM contenía, en EJEMPLOS NO, la frase *"los expertos señalan que el sismo ocurrió muy
cerca de la superficie → VACÍO"*. El modelo marcó *"los expertos señalan que el segundo sismo
ocurrió muy cerca de la superficie"* igual, con el contraejemplo casi carácter por carácter
delante. Tres de los cuatro negativos eran ejemplos NO literales del prompt. **Si un ejemplo
negativo verbatim no detiene al modelo, ningún ejemplo adicional lo va a detener.** El prior
léxico ("expertos/fuentes" + verbo declarativo) aplasta la prueba operativa de dos pasos.
Peor: en d209382f marcó *"Un analista venezolano experto en seguridad y defensa, consultado por
el diario"* — fuente IDENTIFICADA. Ni siquiera llegó al paso 2; falló el paso 1.

**Hallazgo independiente: el código induce FABRICACIÓN.** 57126171 dio 2/4 alucinadas estables
en las 3 corridas. `arrastre` nunca alucinó. Hipótesis: cuando el modelo caza un código con prior
léxico fuerte y no encuentra suficientes instancias reales, inventa spans plausibles. Es un strike
independiente del FP y aplica a cualquier código futuro con esa forma. NO confundir con la deuda
"DeepInfra recorta cita → alucinada fantasma" (2026-07-11): eso es borde recortado; esto es
invención.

**PREDICTOR v3 (v2 FALSADO por esta corrida).** Yo (Claudio) elevé atribucion_difusa apostando a
que tenía "exclusión pequeña y convergente" (v2). Los datos me refutaron: su exclusión es *todo
sourcing anónimo de cualquier hecho* — abierta e infinita en contenido. La regla nueva:
> Si el POSITIVO y el NEGATIVO comparten el mismo DISPARADOR DE SUPERFICIE y solo difieren en el
> ESTATUS EPISTÉMICO de la afirmación que sigue, ningún prompt los separa en un 70B.
`arrastre` sobrevivió porque su exclusión tiene ANCLA LÉXICA (`unánime` + cifra = hecho).
`atribucion_difusa` no tiene ninguna. **Corolario operativo:** antes de gastar un probe,
preguntar "¿hay una PALABRA que separe el positivo del negativo?". Si no, no lo corras.

**Esto valida la regla de no desplegar sin validar.** En producción, este código habría etiquetado
como "manipulación" a la Unidad Investigativa de El Tiempo por usar "fuentes cercanas al proceso"
— reportería anónima de manual — frente a la audiencia profesional que puede hundir el proyecto.
El probe hizo exactamente su trabajo. Costo: una sesión. Beneficio: no publicar esa acusación.

**Herramienta:** `resolver_ids.py` ahora ESCRIBE `banco_fase3_activo.txt` (no toca el banco de
regresión congelado). `diag_fase3_articulo.py` ganó modo `--banco [archivo] --repetir N`: corre
el banco entero, deriva el código objetivo de la etiqueta (`X_pos` → `X`) y da veredicto FN/FP
MECÁNICO contra el umbral. Modo single intacto. El runner mide si el modelo marca; NO valida que
la etiqueta esté bien puesta — ese juicio sigue siendo de Jota. Ambos siguen siendo diag
desechables: NO se commitean.

- **Mecanismo de probing de códigos Fase 3 (protocolo, 2026-07-12; referencia: arrastre):**
  Calibrar cada código de técnicas es una unidad medida, no prompt-engineering a ojo. Pasos:
  (1) BANCO por código: ≥3 positivos reales del corpus + ≥2 negativos DUROS (el caso que el léxico
  confunde y DEBE quedar vacío), sacados con diag_positivos_superficie.py (coarse ilike → fino regex
  → flags fuente?/en-cita?), dedup por texto, etiquetados {codigo}_pos/_neg en banco_fase3.txt.
  (2) PROMPT, una variable a la vez: en el SYSTEM del diag de artículo se reemplaza SOLO el bloque de
  taxonomía por QUÉ ES + PRUEBA OPERATIVA (tapá el marcador → ¿hecho o tesis?) + EXCLUSIÓN DURA +
  REGLA DE VOZ (medio≠cita) + PROCEDIMIENTO (copiá verbatim ANTES de clasificar; vacío permitido;
  prohibido inventar/parafrasear) + EJEMPLOS SÍ/NO de texto real; y se cambia `"codigo"` en el
  ejemplo del JSON. No se tocan los otros códigos.
  (3) UMBRAL fijado ANTES de correr: todos los positivos marcan, todos los negativos vacíos, estable
  en 3 corridas, grounding verbatim OK. (4) CORRER: `python diag_fase3_articulo.py <uuid> --repetir 3`
  por id; confirmar `Provider: deepinfra`. (5) LEER FN/FP/grounding; alucinada por borde recortado =
  fantasma (no cuenta como FP). (6) VEREDICTO sin punto medio: pasa → v1; falla FN → definición
  estrecha; falla FP → exclusión no convergente → baja-confianza o enfoque distinto.
  Por qué importa: garantiza resultados de alta calidad y confiables ANTES de exponerlos. Un FP no
  medido en producción es un cartel público que dice "manipulación" a periodismo legítimo frente a
  FLIP/Colombiacheck — el peor lugar para diagnosticar. El diagnóstico vive en el banco, no en prod.

- **Corpus MEDIDO 2026-07-12: 5922 filas** (no ~2700). Incluye recapturas por inmutabilidad
  (mismo texto, hash distinto → filas duplicadas por contenido). Consecuencias: (a) muestrear banco
  siempre dedup por texto; (b) el batch debe decidir su unidad (por fila vs por url/último-hash) —
  queda para la unidad de escala. `tipo` sigue poco fiable: columnas de opinión salen como 'noticia'
  (ej. las2orillas 9a86e897, el-espectador d42a8e25), lo que ensucia el muestreo de opinión del banco.
  
- **Pipeline CI encadenado (2026-06-23):** crawler.yml tiene dos jobs: crawl (cron 6h
  + dispatch) y backfill (needs:crawl). Entornos separados a propósito: crawl liviano
  (httpx+trafilatura), backfill pesado (torch CPU-only + spaCy + sentence-transformers,
  requirements-backfill.txt aparte). Caché pip + ~/.cache/huggingface (clave estática
  hf-...-minilm-l12-v2; subir sufijo si cambia el modelo en backfill_fase2.py). torch
  se instala con --index-url .../whl/cpu ANTES del requirements para evitar el build CUDA.
  El clustering NO está en este workflow (sigue manual, a la espera de recalibrar umbrales).
- **Divergencia silenciosa de git (2026-06-23):** un merge hecho en GitHub adelantó main
  remoto mientras se trabajaba local sin pull. El push pidió pull→merge commit. Mismo
  patrón de riesgo que el "manual-doble" de migraciones. Hábito: pull al EMPEZAR la unidad.
- **Remoto del repo:** github.com/Mr-JotA-94/trama (ojo: no JotaLabs/trama).

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
