# TRAMA — Documento Maestro de Arquitectura
### Rastreador de noticias colombianas: origen, divergencia y técnicas de persuasión

> **Versión 2.1 — enmendado 2026-06-21 (base v2.0, 13 junio 2026) — Autor: Jota (con Claudio)**
> Fuente de verdad del proyecto. Toda sesión empieza aquí + TRASPASO.md + BITACORA.md.
> v2.0 actualizó: estado real de Fase 1 (completa/desplegada), medios nuevos
> (RTVC, La Silla Vacía), decisiones de calidad de datos, y hallazgos que cambian
> el plan (articleBody, grafo de historias relacionadas).
> v2.1 enmienda: decisión LLM Fase 3 (NVIDIA NIM, §2/§5), migración 9 (§3),
> desacople título-display↔ancla (§6). El estado volátil (números, banco) vive en
> TRASPASO.md, no aquí.

---

## 0. Declaración de Tier (Blueprint de código)

- **Tier actual: 2** (compartible públicamente, mantenedor único, presupuesto $0)
- **Camino a Tier 3** si gana tracción (usuarios reales, comunidad activa)
- **Componentes load-bearing (tratamiento defensivo):**
  1. Pipeline de ingesta (crawler + parser) — si falla, no hay datos
  2. Log de auditoría con hashes — si se corrompe, muere la propuesta de valor
  3. Esquema de base de datos — migrar después es doloroso
- **Componentes pragmáticos:** UI, clasificador de tipo, prompts de IA (iterables)

---

## 1. Qué es TRAMA (una frase)

> Una hemeroteca forense: rastrea cómo una misma noticia se origina, se replica y
> **muta** entre medios colombianos, y señala las técnicas de persuasión que cada
> versión usa sobre el lector.

**Usuario primario:** periodistas, verificadores y ciudadanos políticamente
activos en Colombia. NO el público general — ellos llegan después, amplificados.

**Momento de valor:** "Vi un titular. Entro a Trama. Veo las versiones del mismo
hecho lado a lado, qué omitió cada medio y qué técnica usó. Decido con evidencia."

**En producción:** trama-co.vercel.app

---

## 2. Stack (todo gratis)

| Capa | Herramienta | Notas |
|---|---|---|
| Crawler | Python + httpx + trafilatura | corre en GitHub Actions cada 6h |
| Base de datos | Supabase (Postgres + pgvector) | región São Paulo |
| Embeddings | sentence-transformers multilingüe | Fase 2, local, gratis |
| Análisis IA | Fase 3 — Llama 3.3 70B | DeepInfra primario / NIM fallback / Groq deprecado. Es una línea. |
| Frontend | Next.js 14 (App Router) en Vercel | Server Components, solo lectura |
| Inmutabilidad | hashes SHA-256 + log append-only | Polygon opcional Fase 4 |
| Jobs | GitHub Actions cron | gratis |

**Decisión clave:** crawler en Actions (no en Vercel), escribe a Supabase con
clave secreta; web en Vercel solo lee con clave pública. Las tres piezas
desacopladas: si una cae, las otras siguen. Se comunican solo vía Supabase.

**Claves Supabase (formato nuevo):** sb_secret_ (crawler, ignora RLS) /
sb_publishable_ (web, solo lectura por RLS). Jamás la secret en el repo.

---

## 3. Esquema de base de datos (load-bearing)

Tablas: `outlets` (medios + config + perfil reservado), `articles` (snapshots
inmutables con hash), `stories` (clústeres, Fase 2), `story_articles`,
`analyses` (persuasión, Fase 3), `audit_log`.

Columnas clave de `articles`: titulo, subtitulo, autor, fecha_publicacion,
fecha_captura, contenido_visible, es_parcial, tipo, **seccion**, hash_sha256,
entidades (Fase 2), embedding vector(384) (Fase 2).

Config en `outlets`: fuentes (jsonb: rss/sitemap), regla_seccion (jsonb:
primer_segmento/fijo/ninguno), nivel_paywall, y columnas de perfil reservadas
(propietario, grupo_economico, etc.) para Fase 3.

10. story_relations (grafo clúster↔clúster, Fase 2 avanzada; dirigido-espejo, caché
    derivada pura, RLS + policy de SELECT. Criterio y limpieza en BITACORA 2026-06-25).

**Regla inmutable:** nunca UPDATE sobre contenido_visible ni hash. Artículo que
cambia = fila nueva (mismo url, hash distinto). Deduplicación por unique(url,hash).

Migraciones aplicadas (en supabase/migrations/):
1. schema_inicial · 2. rls_lectura_publica · 3. multifeed_y_fuentes ·
4. limpiar_fuentes_espectador · 5. seccion · 6. extraccion_por_medio ·
7. fase2_clustering (agrega entidades jsonb + embedding vector(384) a articles;
   su create de stories/story_articles quedó inerte por IF NOT EXISTS — ver
   BITACORA) · 8. corregir_esquema_stories (recrea stories/story_articles con
   esquema correcto, uuid, scores y anclas) · 9. rls_lectura_stories (policy de
   SELECT público para stories/story_articles; nacieron con RLS activo pero sin
   policy → la web veía cero filas en silencio. Ver BITACORA 2026-06-17).

---

## 4. Medios

### Estructura central — Fase 1 (5 medios, EN PRODUCCIÓN)
Balanceada por ángulo editorial, para que el análisis de divergencia no nazca
sesgado. Las posiciones son hipótesis internas, NO etiquetas del producto.

| Medio | Ángulo | Fuente | Paywall |
|---|---|---|---|
| Vorágine | investigativo independiente | RSS | abierto |
| Las2orillas | digital crítico | RSS | abierto |
| El Espectador | centro tradicional | sitemap | parcial |
| El Tiempo | establishment (Sarmiento) | RSS (3 feeds) | parcial |
| El Colombiano | conservador regional (Medellín) | RSS | parcial |

### Expansión — Fases 2 y 3 (cola, con criterios)
**Criterios de admisión:** (1) cada medio debe aportar un ángulo que los actuales
no cubren — "más" sin ángulo nuevo es solo volumen; (2) verificar feed con
verificar_feeds.py antes de prometerle lugar.

| Medio | Ángulo que agrega | Fase |
|---|---|---|
| Colombia+20 | vertical de paz (El Espectador) | 2 |
| **La Silla Vacía** | análisis político independiente, foco en poder y redes | 2 |
| Semana | derecha (Grupo Gilinski) — paywall duro, solo titulares/ledes | 3 |
| Caracol / W Radio | broadcast establishment | 3 |
| **RTVC Noticias** | **medio público estatal — perspectiva oficial del Estado, ángulo que ningún privado cubre** | 3 |

Nota sobre RTVC: como medio público, su encuadre representa la voz institucional
del gobierno de turno. Valioso precisamente por contrastar con los privados —
amplía el espectro hacia un ángulo que hoy falta por completo. Verificar su feed
antes de integrarlo.

Nota sobre La Silla Vacía: paywall parcial; su fuerte es el análisis de poder y
relaciones, no la noticia de último minuto. Aporta profundidad analítica al clúster.

---

## 5. Taxonomía de técnicas de persuasión (Fase 3)

El producto dice "técnicas de persuasión detectadas", NO "sesgo cognitivo"
(el sesgo vive en el lector; la técnica vive en el texto).

> **ESTADO (medido 2026-07-17): el carril de detección PER-ARTÍCULO está CERRADO.**
> De 7 códigos, 1 pasó su banco (`arrastre`) y resultó irrelevante en el archivo real
> (0.15% de cobertura ≈ 10 artículos de 6562). Ver BITACORA 2026-07-17.

### Veredicto por código
| Código | Estado | Base |
|---|---|---|
| `arrastre` | validado en banco, IRRELEVANTE en producción | cobertura 0.15% (medida) |
| `atribucion_difusa` | RECHAZADO — baja confianza | FP=4/4 (medido) |
| `encuadre` | baja confianza, v4 congelado | error se desplaza, no se reduce (medido) |
| `falsa_dicotomia`, `miedo` | NO MEDIDOS — carril cerrado | predichos baja confianza |
| `titular_enganoso` | fuera por estructura | es relación titular↔cuerpo, otra clase de claim |
| `omision` | sin validar — ÚNICO superviviente estructural | es inter-artículo, el carril vivo |

### Por qué falló (no fue el modelo ni el prompt)
1. **Aritmética del falso positivo.** Con prevalencia 0.15% y umbral de precisión 0.90 se
   exige especificidad 99.983%. Ningún clasificador lo hace. La regla "un FP cuesta más que
   diez FN" (correcta) y una clase al 0.15% (medida) son **contradictorias juntas**.
2. **Taxonomía deductiva.** Esta §5 se escribió antes de que existiera el corpus: categorías
   de manual de retórica, no inducidas del archivo. El archivo dice que casi no ocurren.
3. **Tarea en la columna débil del modelo.** El 70B es fuerte comparando textos y
   distinguiendo voz de cita; es débil en juicios normativos abiertos y en hallar clases
   raras. Toda esta §5 pedía lo segundo.

### Reglas que gobiernan cualquier código futuro (no negociables)
- **BASE RATE PRIMERO.** Ningún código entra a probe sin medir su prevalencia. Si es <1%, se
  cambia la TAREA, no el prompt.
- **Un banco balanceado mide separabilidad, NO precisión operativa.** Todo banco declara su
  prevalencia.
- **La verificación debe ser CÓDIGO, no juicio.** No existe oráculo humano disponible en este
  proyecto (ver BITACORA).
- **Grounding verbatim = filtro de publicación.** Si la cita no está literal en el artículo,
  no se publica.
- **Los prompts validados son especificación de producto**, viven versionados en
  `/crawler/prompts/`, no en diag desechables.
- Calibrar conservador sigue vigente: un falso positivo de "manipulación" cuesta más
  credibilidad que diez falsos negativos.

### Implementación
Proveedor **DeepInfra**, modelo `meta-llama/Llama-3.3-70B-Instruct`, temp 0.15, detrás de
cliente swappable (base_url + api_key + model_id en config). NVIDIA NIM fallback; Groq
deprecado (decomisión 2026-08-16). JSON estricto por prompt + validación/retry, no por
extensión propietaria. **Corrige la decisión previa de 2026-06-19 (NIM primario) y §2.**
**El modelo no es el cuello de botella: no cambiar de modelo buscando arreglar esto.**

### Fase 3 v1 — IMPLEMENTACIÓN (2026-07-29)
Esquema: `comparaciones` (por par, cache-key = par de hashes ordenado) + `resumenes` (por
clúster, cache-key = sha256 del set de hashes). FK SET NULL. El análisis es CACHE DERIVADO:
idempotente, borrable, reconstruible; su identidad es el contenido inmutable (hash), no el
story_id volátil — esto resuelve el choque con el clustering full-recompute cada 6h.

Módulo crawler/analisis_fase3.py. Principio: el LLM SEÑALA spans verbatim; el gate verbatim
(subcadena literal) es la defensa arquitectónica — lo no-literal se descarta antes de
guardar. El resumen usa 2 llamadas separadas: la síntesis solo ve spans verificados, nunca
los artículos (anti-fabricación). Modelo: GLM-5.2.

Restricción de escala (medida): el análisis por pares es O(n²). Requiere split de beats /
agrupación temporal + tope de tamaño de clúster antes del backfill y del cron.

Pendiente de §5: reescritura integral (carril per-artículo cerrado, veredictos, aritmética
del FP como sección).

Resumen de Fase 3: de por-clúster a por-día. La unidad del resumen pasó del clúster
completo a la ventana-día. procesar_dia genera, por cada día de un clúster: (1) una
síntesis breve destrabada (ve los cuerpos completos del día) y (2) una corroboración
con gate verbatim. Ambas viven en resumenes_dia, que es ahora el objeto completo de la
jornada: síntesis + hechos corroborados + solo-un-medio, con atribución de medios y fecha.

Razones de diseño: (a) trocear por día elimina la deriva causal por construcción — una
foto de un día no encadena eventos separados en el tiempo; (b) el payload por día es chico,
lo que evita el structural collapse y el timeout de la corroboración monolítica; (c) el gate
verbatim se preserva, ahora fusionado por medio (todas las notas de un medio ese día se
unen en un bloque; un span vale si aparece en cualquiera de ellas), lo que recupera los
sub-hechos que un colapso 1-por-medio perdía. La síntesis única y la corroboración por
clúster quedan retiradas/a-retirar. El gate mecánico valida procedencia; la robustez del
modelo (con contexto completo) es lo que evita la fabricación, no la restricción del input.

### Inmutabilidad: evidencia vs. análisis derivado
La regla "fila nueva, nunca UPDATE" aplica a `articles` (el archivo forense: evidencia con valor
probatorio). NO aplica a los derivados LLM (`comparaciones`, `resumenes_dia`), que son caché
regenerable anclado a hashes de contenido. Consecuencias de diseño:
- `resumenes_dia` mantiene UN análisis vigente por (story_id, dia): al cambiar la composición del
  día (dia_key nuevo), la versión previa se RETIRA (DELETE post-insert), no se acumula.
- El FK story_id es ON DELETE SET NULL (no CASCADE): un re-split que mata el sid deja la fila
  huérfana y adoptable por dia_key, en vez de destruir trabajo LLM caro.
- El anclaje del derivado es el contenido inmutable (dia_key = hash de hashes del día), no la
  etiqueta volátil (story_id, que es uuid5 del artículo más antiguo y muta al recomponerse el clúster).
---

## 6. Clustering (Fase 2 — el corazón intelectual)

Pipeline de dos etapas, **entidades primero, semántica después**:
1. Clasificar tipo (ya hecho en Fase 1)
2. Extraer entidades (spaCy es_core_news_md) + embeddings
   (sentence-transformers paraphrase-multilingual-MiniLM-L12-v2, 384 dims)
3. Candidatos: pares de medios distintos dentro de ±72h (filtro grueso)
4. Confirmación: **DOS COMPUERTAS EN AND** (validadas con datos reales 2026-06-16,
   reemplazan la hipótesis original de "≥3 entidades + coseno ≥0.62"):
   - **Compuerta 1 (entidades):** peso IDF de entidades compartidas ≥ 20. El peso
     pondera cada entidad por rareza (log(N/df)); entidades genéricas como "Petro"
     o "Bogotá" pesan poco, específicas como "golfo de Urabá" pesan mucho.
   - **Compuerta 2 (semántica):** similitud coseno de embeddings ≥ 0.70.
   Un par entra al clúster solo si pasa AMBAS. Razón medida: ni el conteo de
   entidades ni la similitud solos separan "mismo hecho" de "mismo tema" (la
   campaña electoral comparte muchas entidades Y similitud media). Las dos juntas
   sí: "mismo hecho" tiene peso alto Y coseno alto; "mismo tema, distinto hecho"
   tiene uno alto y el otro bajo, y cae.
5. Agrupación por componentes conexas (union-find). Transitividad intencional:
   si A~B y B~C, los tres forman una historia aunque A y C no se compararan alto.

**Reglas:** solo las noticias forman el clúster núcleo; opinión/editorial/análisis
se adjuntan como "reacciones" (no se comparan contra noticias en omisiones). Solo
clústeres de 2+ artículos y 2+ medios distintos (un solo medio no es cobertura
cruzada).

**Estado (hito 2026-06-16): motor construido y VALIDADO.** Corrió sobre 587 artículos
(2.5 días) → 20 clústeres, todos limpios a ojo. Los grandes (18 = captura alias
Chalá; 13 = muerte Niño Guerrero) son un solo hecho cada uno; la campaña electoral
quedó correctamente fragmentada en clústeres distintos, no desbordada. (Números
ACTUALES en TRASPASO — no este hito histórico.) Los umbrales SIGUEN siendo
provisionales en el sentido de que la muestra estuvo dominada por un macro-tema
(elección); re-verificar la frontera cuando haya semanas de volumen y varios temas
grandes simultáneos. La METODOLOGÍA (dos compuertas en AND) es lo robusto; los
números exactos se recalibran corriendo de nuevo los scripts de diagnóstico de pares.

**Decisiones cerradas con datos (2026-06-16):**
- Umbrales: peso IDF ≥20 AND coseno ≥0.70 (antes: hipótesis 0.62 sin calibrar).
- Ventana temporal ±72h: se mantiene como filtro grueso de candidatos. La regla
  temporal estricta que se consideró resultó INNECESARIA — las dos compuertas ya
  separan hecho de tema sin ayuda del tiempo.
- Regla de "sección compatible": no se implementó; las dos compuertas bastaron.
  Queda como parámetro opcional si una recalibración futura la necesita.

**Scores requeridos por el algoritmo para la UI (contrato backend→frontend):**
Cada artículo dentro de un clúster necesita tres scores calculados por el pipeline:
1. `score_neutralidad` — cercanía al centroide del clúster en el espacio de
   embeddings (mayor = más central/neutral; menor = más sesgado).
2. `score_cobertura` — proporción de entidades del clúster que el artículo
   menciona (qué tan completo es factualmente). NOTA: hoy no es comparable entre
   clústeres de distinto tamaño — ver deuda en BITACORA.
3. `score_divergencia` — distancia al artículo más similar del clúster (qué tan
   distinto es del consenso).
Las dos cards ancla se eligen así (criterio actualizado 2026-06-18):
- **Ancla principal:** entre los artículos que superan un piso de neutralidad
  (percentil 75 de score_neutralidad DENTRO del clúster), la de mayor
  score_cobertura. Razón: multiplicar neutralidad×cobertura fallaba en clústeres
  grandes —neutralidad es casi constante y cobertura de alta varianza, así que el
  producto ordenaba de facto por cobertura y dejaba anclar reacciones
  editorializadas (medido, caso Chalá 2026-06-17). El gate separa "¿es central?"
  de "¿es completo?". Umbral p75 PROVISIONAL, recalibrar con volumen.
- **Ancla secundaria:** la de mayor score_divergencia (sin cambios). Puede NO pasar
  el piso de neutralidad: por diseño, la card divergente representa la versión más
  distinta del consenso, no la más neutral.

- **Limitación conocida (titular-cita):** el gate de anclas NO atrapa titulares-cita
  de actor político con alta neutralidad+cobertura — el embedding las ve centrales.
  El SCORING / es_ancla sigue SIN tocar (una cita puede ser legítimamente el ancla de
  las cards). Lo que SÍ se resolvió (2026-06-21) es el TÍTULO DE DISPLAY del feed —
  ver bloque siguiente. Ojo: no son lo mismo. Detalle en BITACORA.

- **Título de display vs ancla (desacople, 2026-06-21):** el NOMBRE de la historia
  en el feed NO es el titular del ancla. Se calcula aparte (tituloCanonico,
  lib/colapsarCluster.js): el titular noticia más neutral que NO sea cita
  declarativa. Razón: el ancla es load-bearing (qué artículo representa el clúster en
  las cards); el título es presentación (cómo se nombra el hecho). Un titular-cita
  puede ser legítimamente el ancla por embedding, pero es mal nombre del hecho —
  adopta el encuadre del actor, que es lo que Trama señala, no narra. La heurística
  de cita (cláusula entre comillas adyacente a dos puntos) vive solo en presentación:
  un falso positivo da un título subóptimo (cosmético, reversible), nunca corrompe
  scores ni anclas. Residual conocido: clústeres cuyas noticias son TODAS cita (1/48
  hoy) caen a la más neutral. Detalle en BITACORA.

  - **Identidad estable del clúster (uuid5 determinista, 2026-06-21):** stories.id NO
  es aleatorio. Se computa como uuid5(NAMESPACE_STORIES, url del artículo más antiguo
  del clúster). Razón: reescribir_stories hace delete()+insert() cada corrida; con id
  aleatorio, todo enlace /historia/[id] compartido se rompía. Sembrar del url (átomo
  permanente, no del article_id que cambia por re-captura) hace que el id sobreviva
  entre corridas mientras el artículo más antiguo siga en el clúster. Preserva la
  naturaleza de stories como CACHÉ DERIVADA PURA: el id se COMPUTA desde datos, no se
  almacena-y-recupera (eso habría sido estado, la opción descartada). NAMESPACE_STORIES
  es constante e inmutable: si cambia, toda la identidad se rompe. Limitación conocida:
  fusión de clústeres y re-semilla (el más antiguo abandona) generan uuid nuevo — caso
  raro, documentado en BITACORA con disparador para escalar a tabla de identidad.

  - **Átomo del clustering = URL, no captura (colapso al cargar, 2026-06-23):** el
  clustering colapsa las múltiples capturas de un mismo URL a un representante (la
  última captura) en cargar_articulos(), ANTES de calcular IDF, formar aristas y
  calcular scores. Razón: una nota editada genera filas nuevas (hash distinto,
  inmutabilidad), pero es UN artículo. Sin colapsar, una nota muy editada pesaba Nx
  en el centroide del clúster y inflaba n_articulos, contaminando además el orden
  "Más cobertura" del feed (que ordena por n_articulos). Colapsar al cargar lleva el
  átomo correcto a TODO el pipeline de una sola intervención, sin tocar compuertas ni
  scores. Resultado: backend y frontend (colapsarCluster.js) cuentan el mismo átomo —
  n_articulos del feed == nodos del hilo del expediente. El uuid5 sobrevive al
  colapso porque el "más antiguo" es un URL (permanente), no una captura. Residual
  conocido (medido 2026-06-23): un clúster que solo alcanzaba 2 medios gracias a una
  recaptura se disuelve al colapsar — correcto, no era cobertura cruzada real.

### ⭐ Evolución del modelo: grafo de historias relacionadas (idea de Jota)
### Exposición de story_relations en el frontend (corregido 2026-08-08)
El grafo relacional se expone en /historia/[id] en DOS superficies distintas:
- **"De la misma trama"** (arriba): sub-hechos hermanos del Louvain split
  (tipo='misma_trama'). Verdad mecánica, no depende de NER → siempre expuesto.
  Índice cronológico con "Estás aquí". (feat/indice-trama, 2026-08-08.)
- **"Historias conectadas"** (abajo): relaciones temáticas (tipo='tematica',
  n_especificas≥umbral). YA EXPUESTAS en producción — la nota previa "ocultas
  hasta el re-backfill de NER" era stale. El re-backfill sigue pendiente y
  MEJORARÁ la calidad de n_especificas, pero no gobierna la visibilidad.
El query de este bloque filtra tipo='tematica' para no mezclar hermanas.

**Criterio refinado con medición (2026-06-24, diag_relaciones v1–v4 — detalle en
BITACORA):** la idea de "dos compuertas un nivel arriba" se corrigió con datos. El
coseno entre centroides liga por TEMA, no por hecho → es GUARDIA, no motor. El motor es
n_especificas: entidades reales y específicas compartidas, tras limpiar ruido NER +
clasificar geografía + descartar genéricas por DF de CLÚSTER (la rareza correcta a este
nivel es df-de-clúster, no df-de-artículo). Funciona para hechos discretos. El macro-tema
(p. ej. campaña electoral) es un HUB IRREDUCIBLE por heurística de entidades (clúster
grande = superficie de solapamiento grande); se controla con CAP DE IN-DEGREE en la capa
de lectura (presentación), y la distinción contexto/seguimiento se difiere a Fase 3
(LLM + tipo_relacion). story_relations = caché derivada pura (...). Esquema RESUELTO (migración 000010, dirigido-espejo, criterio n_esp≥3 ∧ cos≥0.50; ver BITACORA 2026-06-25). 

### Nota sobre expansión de medios y Fase 2
El clustering opera sobre artículos, no sobre medios. Agregar un medio = config
nueva en outlets, NO toca el clustering; solo se recalibran umbrales. Por eso:
validar el clustering con los 5 medios actuales (que Jota conoce y puede juzgar a
ojo) ANTES de expandir (HECHO 2026-06-16). Menos medios = más capacidad de
verificar si el motor sirve. Feeds de cola ya verificados (La Silla Vacía, RTVC)
en BITACORA; activarlos solo tras decidir construir sobre 7 medios.
---

## 7. Sistema de diseño (IMPLEMENTADO en Fase 1)

**Tokens:** tinta `#171A2E` · papel `#FCFBF6` · resaltador `#FFC23D` (técnicas,
Fase 3) · hilo `#C8442E` (conexión de versiones) · verificado `#2E6E4E` · gris
archivo `#8C8A82`.

**Tipografía:** Archivo Black (display, fundición argentina — la elección es el
concepto) · Source Serif 4 (cuerpo) · IBM Plex Mono (hashes, timestamps, forense).

**Tintas por medio:** paleta sobria asignada por Trama (NO colores de marca ni de
partido). El Tiempo azul, El Espectador verdeazul, Vorágine violeta, Las2orillas
ocre, El Colombiano marrón. Rojo/ámbar/verde reservados para hilo/resaltador/
verificado. Etiquetas con relleno sólido + texto papel para contraste.
(Pendiente: alinear estos valores con los tokens reales de globals.css — ver TRASPASO.)

**Elemento firma:** el hilo rojo — conecta versiones de un mismo hecho ordenadas
por hora, estilo tablero de investigación. Hoy es decorativo (lista cronológica);
hará su verdadero trabajo en Fase 2 con el clustering. Única animación del sitio,
respeta prefers-reduced-motion.

**Reglas:** esquinas rectas (papel no tiene border-radius), bordes 1px, sin
gradientes/sombras/glassmorphism.

**Vista de clúster — Fase 2 (diseño cerrado 2026-06-15):**
Layout bento editorial: 2 cards ancla (borde izq 3px color-medio, criterio:
neutralidad+cobertura+divergencia) + N cards secundarias (borde 1px). Hilo
cronológico con ediciones tachadas, popup de historial por nodo, y extensión
hacia historia relacionada con nodo hueco + segmento discontinuo. Hilo
implementado como SVG path curvo (Bézier), no línea recta — pendiente precisar
en implementación. Grafo panorámico expandible con líneas SVG dinámicas.
Barra de búsqueda con filtros: sección, tipo, medio, fecha. Análisis de
persuasión: acordeón por card (Fase 3). Resumen del hecho: bloque prominente,
placeholder Fase 2, LLM en Fase 3.

---

## 8. Fases de construcción

### ✅ FASE 1 — El archivo funciona (COMPLETA Y DESPLEGADA)
Crawler de 5 medios + snapshots con hash + clasificador de tipo + sección + web
pública de solo lectura (registro, expediente, perfil de medio). Gate de
observación de 7 días (≥150 artículos, 5 medios, cero duplicados, tipos ≥80%):
superado.

### ⏳ ANTES DE FASE 2 
### Extracción de cuerpo por bucket (desde 2026-06-14)
El cuerpo del artículo se extrae según el campo outlets.extraccion:
- **'articlebody':** se prefiere el campo articleBody del JSON-LD (lo que el medio
  declara), con trafilatura de respaldo si una nota no lo expone. Medios: El Tiempo,
  El Colombiano, El Espectador. Motivo: cuerpos sin boilerplate (cookies, audio IA,
  cola de boletines) como materia prima limpia para el clustering.
- **'trafilatura':** solo trafilatura. Medios: Vorágine (no expone JSON-LD),
  Las2orillas (no expone articleBody). Trafilatura ya los extrae limpio.
Título, subtítulo, autor y fecha SIEMPRE salen de trafilatura/meta; articleBody
aporta solo el cuerpo. Trafilatura sigue siendo el piso: articleBody que falte o
falle cae a trafilatura (degradación elegante). Al agregar un medio nuevo:
diagnosticar su articleBody y fijar el bucket explícito antes de admitirlo.

### FASE 2 — Las historias se conectan
Entidades + embeddings + clustering + vista del hilo rojo. Integrar Colombia+20 y
La Silla Vacía DESPUÉS de validar el clustering con los 5 actuales.
El clustering aplica Louvain (res 1.6, seed fijo) a todo componente >50 artículos, partiendo beats políticos de semanas en sub-hechos legibles. Validado 2026-08-08 (ver BITACORA). El grafo story_relations distingue ahora tipo: tematica (motor n_especificas + guardia coseno, oculto hasta re-backfill de NER) y misma_trama (subhistorias hermanas del mismo componente padre, verdad mecánica sin umbral, exento del bloqueo NER, expuesto en front).

### FASE 3 — El análisis de persuasión
Pipeline NVIDIA NIM por clúster (≥3 medios), resaltador ámbar, resumen neutral, perfiles
de medios (sobre columnas ya reservadas; cada dato con fuente citable). Integrar
Semana, Caracol/W Radio, RTVC.

### FASE 4 — Comunidad e inmutabilidad fuerte
Auth, anotaciones (voto a la anotación, no al medio), reputación de anotadores,
gobernanza mínima contra captura coordinada, anclaje opcional en Polygon.

---

## 9. Riesgos vigentes

1. **Scope creep** — ideas nuevas van a BITACORA.md (sección Ideas), no al código.
2. **Falsos positivos del análisis** (Fase 3) — calibrar conservador.
3. **Comunidad como vector de sesgo** (Fase 4) — gobernanza, no antes.
4. **Legal** — jamás saltar paywalls; solo contenido público; citas cortas con
   enlace al original.
5. **Arranque en frío** — la Fase 1 es útil sin un solo usuario. Esa es la defensa.
6. **Calidad de extracción por medio** — trafilatura sirve de base general, pero
   algunos medios necesitan extractor a medida (ver deuda El Tiempo / articleBody).
   Es la naturaleza del scraping, no un fallo de diseño.

---

*Siguiente sesión: en el Proyecto Trama, con TRASPASO.md cargado. Estado volátil y
próximo paso viven en TRASPASO, no aquí.*
