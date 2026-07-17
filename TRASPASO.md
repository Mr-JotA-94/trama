# TRASPASO — Estado volátil de Trama
> Última actualización: 2026-07-17 (sesión Fase 3 — carril per-artículo MEDIDO y
> CERRADO: `arrastre` cubre 0.15% del archivo. Opción (a) muerta. Batch Tier 3
> CANCELADO. Descubierto el error metodológico transversal: banco balanceado ≠
> prevalencia real (400×). Dirección acordada: comparación inter-medio.)
> Autoridad: este archivo manda sobre memoria. Estado volátil vive AQUÍ.

## Quién soy y cómo trabajamos
Soy Jota (Johan). Claude es "Claudio". Reglas que NO se pierden:
- **Challenge-first:** cuestiona enfoques con fallas ANTES de construir. Honestidad
  sobre complacencia.
- **Declarar Tier (0–3) + load-bearing antes de construir.**
- Directo, conciso, instructivo, en español. **Medir antes de arreglar.**
- Diagnóstico con datos reales; si Claudio no puede verificar en su entorno, me da
  script para correr aquí. Claude Code es solo para CAMBIOS de código en repo.
- **Disciplina de sesión:** un chat = UNA unidad de trabajo = un cierre.
- App para pensar/decidir → Claude Code para tocar archivos → de vuelta el RESUMEN.
  Cambios de una sola función, a mano sin Claude Code.
- **Flujo git:** branch ANTES de tocar código. Pull al EMPEZAR cada unidad.
  Commits de documentación SEPARADOS de los de código. El `git diff` contra el
  commit validado es autoritativo, no el auto-reporte de la herramienta.
- **Los scripts (backfill/clustering/diag) escriben a Supabase o son read-only, NO al
  repo.** Los diag_*.py y prototipos son desechables y no se commitean.
- **Umbral de éxito se fija ANTES de correr, no se mueve después.** (Sostenido TRES
  sesiones seguidas: arrastre pasó; atribucion_difusa falló; el lexicón falló contra
  el MISMO umbral y se cerró sin negociar.)
- **[NUEVA] La receta validada tiene límites de validez.** Aplicar un patrón de la
  BITACORA fuera del régimen donde se midió es un error de método (ver 2026-07-17,
  coarse ilike).

## Quién soy / qué es Trama
Jota (Johan), dev único. Trama: hemeroteca forense de medios colombianos —
rastrea origen, divergencia y técnicas de persuasión sobre el mismo hecho.
En producción: trama-co.vercel.app. Claude = "Claudio".

## Stack
Crawler Python (httpx + trafilatura + articleBody) en GitHub Actions cada 6h →
Supabase (Postgres + pgvector, São Paulo) → Next.js 14 en Vercel.
Monorepo Mr-JotA-94/trama: /crawler, /web, /supabase/migrations.
LLM Fase 3: **DeepInfra (meta-llama/Llama-3.3-70B-Instruct) PRIMARIO** — validado como
proveedor 2026-07-11 (conexión estable, grounding consistente, temp 0.15).
**NVIDIA NIM (meta/llama-3.3-70b-instruct) FALLBACK. Groq DEPRECADO** (fecha límite de
decomisión del modelo: 2026-08-16 — selección de reemplazo PENDIENTE). Cliente swappable
por LLM_PROVIDER en .env (deepinfra|nvidia|groq); failover automático NO implementado.
OJO: el diag arranca en default `nvidia`; confirmar `LLM_PROVIDER=deepinfra` por la línea
`Provider:` antes de medir.
**El modelo NO es el cuello de botella (MEDIDO 2026-07-17).** No cambiar de modelo
buscando arreglar Fase 3: el techo era aritmético, no de capacidad.

## Banco: 7 medios ACTIVOS y VALIDADOS
El Espectador, El Tiempo, El Colombiano, Las2orillas, Vorágine, La Silla Vacía, RTVC.
Corpus MEDIDO 2026-07-17: **7046 filas / 6562 URLs únicas** (recapturas: 484 = 6.9%,
mucho menos de lo que se creía). Crece ~1000 filas/día (crawler cada 6h) — cualquier
número de corpus se desactualiza solo.
**Distribución MEDIDA (artículos únicos):** el-espectador 2622 (40%), el-tiempo 2044
(31%), el-colombiano 879, las2orillas 545, la-silla-vacia 370, **rtvc 81, voragine 21**.

## DÓNDE ESTAMOS

**Fase 1 COMPLETA y desplegada.** Crawler, web pública.

**Fase 2 EN PRODUCCIÓN.** Vista + clustering + feed paginado + grafo de historias.
trama-co.vercel.app/historias y /historia/[id]. Pipeline automatizado (3 jobs CI), cada 6h.

**Fase 3 — CARRIL PER-ARTÍCULO CERRADO POR MEDICIÓN.** El método funcionó; la taxonomía
per-artículo no sobrevive al archivo real.
- **Proveedor: DECIDIDO y VALIDADO.** DeepInfra primario, NIM fallback.
- **`arrastre`: sigue VALIDADO en su banco, pero IRRELEVANTE en producción (MEDIDO
  2026-07-17).** Cobertura 0.84% (55/6562 arts con hit léxico); precisión del lexicón
  17.5%; **positivos reales ≈ 10 artículos en TODO el archivo (0.15%)**. Un v1 con un
  código que se enciende en 1 de cada 656 artículos no es producto.
- **`atribucion_difusa`: RECHAZADO (2026-07-17).** FP=4/4. Ver BITACORA.
- **`encuadre`: baja-confianza, v4 congelado.** Sin cambio.
- **`falsa_dicotomia`, `miedo`: NO MEDIDOS, predichos baja-confianza.** Ya no se miden:
  el carril está cerrado. Si se reabre, medir PREVALENCIA antes que precisión.
- **`titular_enganoso`: FUERA de v1 por estructura** (relación titular↔cuerpo).
- **`omision`: sin validar** — pero es el ÚNICO código de la §5 que vive en el carril
  vivo (inter-artículo). Reconsiderar bajo el diseño nuevo.
- **OPCIÓN (a) — "v1 = arrastre solo a producción": MUERTA.** Cerrada por cobertura, no
  por opinión.
- **BATCH Tier 3: CANCELADO.** 55 artículos no son un batch. Failover, retry-backoff y
  escritura por prompt_version no se justifican para un `for` loop de 2 minutos.
- **Presentación:** `condensar.py` PROTOTIPADO, no integrado. Sin códigos publicables,
  no hay qué presentar todavía.

## LA ARITMÉTICA DEL FALSO POSITIVO (hallazgo central 2026-07-17)
> **Con prevalencia 0.15% y umbral de precisión 0.90, se exige especificidad
> 99.983% — un error cada 6.000 juicios. Ningún clasificador humano ni artificial
> hace eso.**
- El lexicón logró especificidad 99.28% (47 FP sobre 6552 negativos) y aun así dio
  17.5% de precisión. El denominador manda, no la calidad del detector.
- **Las dos premisas del proyecto eran sensatas por separado y contradictorias juntas:**
  "un FP cuesta más que diez FN" (correcta) + clase al 0.15% (medida) = imposible.
  Se ejecutó esa contradicción durante semanas, correctamente. Por eso ningún código pasa.
- **REGLA NUEVA, no negociable:** *ningún código entra a probe sin medir su BASE RATE
  primero. Si es <1%, la precisión alta es inalcanzable: hay que cambiar la TAREA, no el
  prompt.* Esto habría matado `arrastre` el día que se coronó.
- **MATIZ IMPORTANTE (no perder):** la aritmética mata la CLASIFICACIÓN A CIEGAS sobre
  6562 artículos. NO mata el pipeline `regex propone span → LLM juzga sí/no`. Ahí la base
  rate en el punto de decisión es **17.5%, no 0.15%** — dos órdenes de magnitud — y la
  FABRICACIÓN se vuelve imposible (el span viene dado, no hay nada que inventar).

## PREDICTOR DE SUPERVIVENCIA (v3 — VIGENTE pero DEGRADADO a secundario)
> v1 (morfológico vs contextual): FALSADO. v2 (exclusión convergente): FALSADO.
> **v3:** si POSITIVO y NEGATIVO comparten DISPARADOR DE SUPERFICIE y solo difieren en
> el ESTATUS EPISTÉMICO, ningún prompt los separa en un 70B.
- **v3 sigue siendo cierto pero ya NO es la pregunta principal.** Predice si un código es
  *domesticable*; la prevalencia predice si es *rentable*. Un código puede pasar v3
  (arrastre lo hizo) y ser inútil igual. **Medir base rate ANTES que aplicar v3.**

## PRÓXIMO PASO cuando retomemos
>>> #1 es la unidad elegida. NO se decidió hoy a propósito (regla: no decidir cansado ni
>>> en la misma sesión de un resultado negativo — hubo DOS hoy).

1. **DECISIÓN FORMAL DE DIRECCIÓN (unidad de decisión, sin código).** La dirección
   ACORDADA en conversación —no ratificada— es el **carril de comparación inter-medio**.
   Ratificar o rechazar. Tres caminos vivos:
   (a) **Comparación inter-medio** (recomendado): la tarea es DIFERENCIA, no etiqueta.
       Base rate ~100% por construcción. No acusa → no hay FP de "manipulación".
       Es literalmente el momento de valor de Arquitectura §1 ("veo las versiones lado a
       lado, qué omitió cada medio, decido con evidencia").
   (b) **BETA rotulado de `arrastre` vía `regex → LLM filtra`** (decisión ABIERTA, Jota
       manifestó disposición a flexibilizar COBERTURA — no precisión). Barato (57
       candidatos), sin fabricación posible. BLOQUEADOR: no hay ground truth de los 57;
       el único etiquetado existente lo produjo Claudio, que es un LLM juzgando si un LLM
       sirve — circular, no es oráculo.
   (c) **Matar Fase 3 entera.** Defendible y real: archivo inmutable + versiones lado a
       lado YA es producto, YA está en producción, y no promete lo que una IA no cumple.
2. **Si se ratifica (a): MEDIR BASE RATE DE LA DIVERGENCIA (Tier 0).** `cache_corpus.jsonl`
   ya está en disco. Sospecho alta — pero *sospechar* es exactamente lo que trajo hasta aquí.
   Sin este número no se escribe prompt.
   medir base rate de divergencia + participación por medio — salen de la misma consulta a story_articles.
3. **Restricciones de diseño ya MEDIDAS para (a) — no re-descubrir:**
   - **La unidad es el PAR de artículos, NUNCA el clúster completo** (19 art → colapsa a
     4 entradas, 504s). Un clúster de N son pares, no un blob.
   - **Gate de grounding verbatim = FILTRO DE PUBLICACIÓN, no control de calidad.** Si la
     cita no existe literal en el artículo, no se publica. Es `in`, determinista, sin
     humano, sin oráculo. Convierte la alucinación en estructuralmente impublicable — lo
     que la clasificación NUNCA pudo tener.
   - La deuda "DeepInfra recorta cita → alucinada fantasma" pasa de detalle a LOAD-BEARING:
     es el gate.
   - **Riesgo nuevo de (a):** la comparación no acusa, pero puede MENTIR ("X omitió Y"
     cuando X sí lo dice). Refutable en 10 segundos por cualquiera → ante FLIP es peor que
     la acusación. El gate de grounding es la mitigación.
4. **Groq: elegir modelo de reemplazo** antes de 2026-08-16 (decomisión).
5. **Arquitectura §5 debe editarse** — ya no es "casi finalizó", ahora hay veredicto. Ver
   bloque en el cierre de esta sesión.

## Deudas activas (detalle en BITACORA)
- **[NUEVA 2026-07-17, CRÍTICA] Banco balanceado ≠ prevalencia real (400×).** Los bancos
  de probe tienen 60% de positivos; el archivo 0.15%. FN=0/FP=0 en banco NO predice
  precisión en producción. **Aplica retroactivamente a TODA validación de Fase 3, incluida
  la de `arrastre`.** Todo banco futuro debe declarar su prevalencia y decir explícitamente
  qué mide (separabilidad, NO precisión operativa).
- **[NUEVA 2026-07-17, CRÍTICA] No hay oráculo de ground truth.** Jota declaró no poder
  etiquetar `arrastre` con confianza sobre casos reales — **siendo el autor de la
  definición**. Si el autor no puede ejecutar su definición sobre el archivo, la definición
  no es operacionalizable, y "¿el 70B la aplica bien?" nunca tuvo referencia. La BITACORA
  ya rozó esto ("no ground-truth oracle exists") y lo parchó con "Jota juzga". El parche se
  rompió. Bloquea cualquier medición de precisión que dependa de juicio humano.
- **[NUEVA 2026-07-17] Los prompts VALIDADOS no viven en ningún artefacto.** El bloque de
  `arrastre` fue sobrescrito por el de `atribucion_difusa` en el diag y se recuperó por
  suerte del historial de chat del 2026-07-12. Un prompt validado es ESPECIFICACIÓN DE
  PRODUCTO, no instrumentación desechable. Debe vivir en `/crawler/prompts/arrastre_v1.txt`
  versionado. El paso "reusa prompt(s) sobrevivientes" era un supuesto falso.
- **[NUEVA 2026-07-17] `arrastre` — positivo #3 del banco es DUDOSO.** El ejemplo SÍ
  canónico ("todos sabemos que detrás de Abelardo…") está en HABLA TRANSCRITA (contexto:
  "y el muy hábilmente, digamos, ha dicho bueno no se me suban a la tarima"). Por la regla
  de voz sería VOZ DE ACTOR → N. La regla define cita como "entre comillas o tras
  dijo/afirmó/sostuvo"; una transcripción sin comillas ni verbo declarativo se cuela.
  **Está DENTRO del prompt como ejemplo SÍ → le enseña al modelo a marcar voz de actor.**
  Conecta con la vigilancia de d209382f: puede ser el mismo agujero, no dos casos sueltos.
- **[NUEVA 2026-07-17] Bugs del lexicón de `arrastre` (medidos, no arreglados).**
  (1) NEGACIÓN: `est[aá] claro que` captura "**no** está claro que…" — el opuesto exacto
  (n=45, n=63). (2) PERSONALIZACIÓN: "**para mí** está claro que…" (n=33) es lo contrario
  de apelar al consenso. No se arreglan: el carril está cerrado. Reactivar solo si se
  retoma (b).
- **[NUEVA 2026-07-17] Vorágine (21 arts) y RTVC (81) son estadísticamente inexistentes.**
  Los dos medios que Arquitectura §4 justifica por "aportar un ángulo que ningún otro
  cubre" son ~1.5% del corpus juntos. El archivo es de facto El Espectador (40%) + El
  Tiempo (31%). **Más grave que cualquier cosa de Fase 3: afecta clustering, centroides y
  la premisa entera de divergencia** — justo el carril al que se quiere pivotar. Medir por
  qué (¿feed pobre? ¿crawler falla? ¿publican poco?) antes de construir sobre divergencia.
- **[NUEVA 2026-07-17] La receta "coarse ilike server-side" NO escala.** Validada con ~3
  términos en diag_positivos_superficie.py; con 13 términos = 13 seq scans sobre 7k filas
  de texto → el worker de Supabase revienta con Cloudflare 1101, DETERMINISTA en el
  término #12 (el backoff no ayuda: no es transitorio). Patrón correcto para scans amplios:
  bajar el corpus una vez, paginado + ordenado por id, cachear a disco, filtrar en Python.
- **[VIGENTE, DEGRADADA] `atribucion_difusa` induce fabricación.** Ahora EXPLICADA: se le
  pidió cazar a ciegas una clase casi ausente; un modelo obediente al que se manda a buscar
  agujas en pajares sin agujas fabrica agujas. **Deja de ser misterio y pasa a ser
  predicción:** cualquier código de baja prevalencia buscado a ciegas fabricará.
  Estructuralmente imposible bajo `regex → filtro`.
- **[VIGENTE] `encuadre` baja-confianza, v4 congelado** — enfoque distinto, no otra versión.
- **[VIGENTE→LOAD-BEARING] DeepInfra recorta cita → ALUCINADA fantasma.** Sube de
  prioridad: bajo el carril de comparación, la tolerancia de borde ES el gate de publicación.
- **[VIGENTE 2026-07-11] diag_fase3_prompt.py: rama de provider rota.**
- **[VIGENTE] `tipo` poco fiable entre medios** — El Espectador acapara los 'opinion'.
- **[PENDIENTE] Centroide-por-medio: sesgo direccional** — bloquea activar medios >7.
- **[PENDIENTE] delete-then-insert de story_relations/story_articles** — aceptada.
- Otras menores: writes uno-por-uno, deps sin pin, búsqueda no paginada, lookup URL
  best-effort.

## Notas de consistencia docs↔código
**Arquitectura §5 DEBE editarse ahora** (ya hay veredicto, ya no es "casi"): arrastre =
validado-en-banco pero irrelevante-en-producción (0.15%); encuadre y atribucion_difusa =
baja-confianza; falsa_dicotomia/miedo = no medidos, carril cerrado; titular_enganoso =
fuera por estructura; omision = único superviviente estructural (inter-artículo); proveedor
DeepInfra (§2 dice NIM, viejo); split extracción(LLM)↔presentación(código); disclosure de
prompt como principio; regla de base rate; aritmética del FP.

## Ideas registradas (no son scope ahora)
- **[NUEVA 2026-07-17] Taxonomía INDUCTIVA, no deductiva.** La §5 se escribió antes de que
  existiera el corpus: son categorías de manual de retórica importadas de la literatura de
  propaganda. El archivo dice que 6 de esos 7 fenómenos, tal como se definieron, casi no
  existen en él. Si se reabre taxonomía: muestrear 50 artículos al azar, LEERLOS, y
  preguntar "¿qué hacen ESTOS medios que un lector debería ver?". La taxonomía sale del
  corpus, no del manual.
- **[NUEVA 2026-07-17] Dónde es fuerte el 70B (guía de diseño).** FUERTE: comparar dos
  textos, distinguir cita de voz del medio, extraer/alinear/reescribir, detectar qué le
  falta a A que B tiene. DÉBIL: juicios normativos abiertos, proporcionalidad, encontrar
  clases raras sin evidencia, emitir acusaciones categóricas. **Toda la Fase 3 diseñada
  hasta hoy vivía en la columna débil.**
- **[NUEVA 2026-07-17] `regex → LLM filtra` como arquitectura general.** El regex da recall
  (barato, auditable); el LLM da precisión sobre un span ya acotado. Sube la base rate en
  el punto de decisión 100×, elimina la fabricación por construcción, y reduce el costo (57
  llamadas, no 6562). Aplicable a cualquier código futuro con ancla léxica.
- **[VIGENTE] Carril de divergencia inter-artículo como señal.** Usar el desacuerdo ENTRE
  medios para separar HECHO (todos coinciden) de TESIS (uno solo lo afirma) sin pedirle al
  LLM ese juicio. Es el diseño original de omision/resumen_neutral. **Promovido de Idea a
  dirección acordada.**
- **`encuadre` por enfoque distinto:** clasificador dedicado, o dos pasadas.
- **UNIDAD DE PRESENTACIÓN de Fase 3:** vista condensada; termómetro DETERMINISTA (nunca
  color por el LLM); frase-resumen groundeada; disclosure del prompt + disclaimer IA —
  PRINCIPIO. Con 0 códigos publicables, en pausa.
- **Selección de representante como problema de ranking** (no "más largo").
- Upgrade navegabilidad/estética: filtro por medio, ícono ⓘ, hilo rojo SVG, búsqueda
  paginada.
- La Silla Vacía: filtro sección opinión vs reportería.

## Cómo verificar el estado
- Cron post-merge en verde (3 jobs). Web Fase 2: /historias y /historia/[id].
- LLM swappable: LLM_PROVIDER=deepinfra|nvidia|groq. Proveedor REAL confirmado por la línea
  `Provider: {PROVIDER} | modelo: {MODEL_ID}` del diag de artículo.
- **`banco_fase3.txt`** = banco de regresión CONGELADO (6 fijos de encuadre + extensión
  arrastre). **AVISO: su prevalencia es 60%, el archivo real 0.15%. Mide SEPARABILIDAD, no
  precisión operativa. No volver a leer FN=0/FP=0 como "listo para producción".**
  El positivo 9a86e897 ("todos sabemos… Abelardo") está en disputa — ver deudas.
- **`banco_fase3_activo.txt`** = desechable, contiene el banco RECHAZADO de
  atribucion_difusa. Regenerar antes de reusar.
- **`cache_corpus.jsonl`** (7046 filas, ~35MB) — volcado del archivo generado por
  diag_arrastre_lexico.py. **NO COMMITEAR.** Añadir a .gitignore o borrar. Sirve para
  medir la base rate de divergencia sin volver a pegarle a Supabase.
- **`muestra_arrastre_ETIQUETAR.csv` / `_CLAVE.csv`** — censo de los 57 spans + 10 de
  control. El etiquetado que existe lo hizo Claudio (LLM), NO Jota. **No es ground truth.**
  Conservar solo si se retoma la opción (b).
- FK analyses: confdeltype='n' para analyses_story_id_fkey.