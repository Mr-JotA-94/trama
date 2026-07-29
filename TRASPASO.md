# TRASPASO — Estado volátil de Trama
> Última actualización: 2026-07-29 (sesión PIPELINE FASE 3: GLM-5.2 sellado, tablas
> comparaciones/resumenes creadas, módulo analisis_fase3.py escrito y PROBADO end-to-end
> sobre datos reales. v1 funcionalmente completo. Falta escala: costo CUADRÁTICO ->
> split de beats es BLOQUEANTE del backfill. Próximo paso: split/agrupación temporal.)
> Autoridad: este archivo manda sobre memoria. Estado volátil vive AQUÍ.

## Quién soy y cómo trabajamos
Soy Jota (Johan). Claude es "Claudio". Reglas que NO se pierden:
- **Challenge-first:** cuestiona enfoques con fallas ANTES de construir.
- **Declarar Tier (0–3) + load-bearing antes de construir.**
- Directo, conciso, instructivo, en español. **Medir antes de arreglar.**
- Diagnóstico con datos reales; scripts para correr en mi máquina. Claude Code solo para
  CAMBIOS de código en repo, y NO ejecuta DDL contra Supabase (migraciones a mano).
- **Un chat = UNA unidad de trabajo = un cierre.**
- **Flujo git:** branch antes de tocar código. Commits de doc SEPARADOS de los de código.
- Los diag_*.py son desechables y NO se commitean.
- **Umbral de éxito se fija ANTES de correr.**
- **Ningún % corona una feature sin LEER material real** (2026-07-20).
- **El error del modelo se DESPLAZA, no se reduce, cuando redacta** -> quitar la redacción,
  no endurecer el campo. La solución fue solo-spans (2026-07-21).
- **Éxito concluyente, fracaso no (en generación):** un modelo mejor puede resolver lo que
  otro falla. GLM resolvió la deriva del 70B (2026-07-22).
- **El verificador mecánico ordena; la fidelidad la juzga el ojo humano.** El substring
  valida procedencia, NO relación causal ni equivalencia semántica.
- **Un ítem malo no tumba el batch:** try/except por ítem + retry, como en el bake-off.
  (Lección re-aplicada dentro del módulo, 2026-07-29.)

## Quién soy / qué es Trama
Jota (Johan), dev único. Trama: hemeroteca forense de medios colombianos. En producción:
trama-co.vercel.app. Claude = "Claudio".

## Stack
Crawler Python en GitHub Actions cada 6h → Supabase (Postgres + pgvector) → Next.js 14 en
Vercel. Monorepo Mr-JotA-94/trama (/crawler, /web, /supabase/migrations).
**LLM Fase 3: zai-org/GLM-5.2 (DeepInfra) — SELLADO. temp 0.15, max_tokens 6000.**
DeepInfra $0.93/M in, $3.00/M out (~3 USD por pasada de 400 clústeres; irrelevante a esta
escala). Baseline Llama-3.3-70B RETIRADO de Fase 3. Groq (decomisión 2026-08-16) resuelto
de facto por GLM.
**ENTORNO — bug: Python 3.14 (local) cuelga sockets SSL de httpx Y requests.** Mitigado con
POST no-streaming + timeout total 120s (tolerable, no ideal). PRODUCCIÓN corre en CI: fijar
el workflow a Python 3.12, no 3.14. `requests==2.32.3` ya en crawler/requirements.txt.

## Banco: 7 medios. Corpus ~7000+ filas / ~6500 URLs, crece ~1000/día.
En cobertura cruzada: Vorágine=0, RTVC 4.2% (deuda de pipeline).

## DÓNDE ESTAMOS

**Fase 1 COMPLETA. Fase 2 EN PRODUCCIÓN** (clustering + feed + grafo, CI 6h).

**Fase 3 — carril de COMPARACIÓN INTER-MEDIO (a). v1 FUNCIONALMENTE COMPLETO Y PROBADO.**

**ESQUEMA (creado 2026-07-22, aplicado a mano en Supabase + espejado en /migrations):**
- Tabla `analyses` vieja (carril per-artículo, vacía) -> DROPEADA.
- `comparaciones` (por par): hash_a, hash_b (unique, con CHECK hash_a<hash_b), article_a/b
  (FK SET NULL), diferencias jsonb, es_mismo_hecho, divergencia_relevante, desfase_temporal,
  modelo, prompt_version.
- `resumenes` (por clúster): cluster_key (unique) = sha256 del set ordenado de hashes,
  story_id (FK SET NULL), article_ids[], member_hashes[], hechos_corroborados jsonb,
  solo_un_medio jsonb, sintesis text, modelo, prompt_version.

**MÓDULO: crawler/analisis_fase3.py (escrito por Claude Code, PROBADO).**
- Contrato LLM (3 prompts congelados = los de los diag validados): SYS_COMPARACION (por par,
  solo-spans), SYS_CORROBORA + SYS_SINTESIS (resumen, 2 llamadas SEPARADAS a propósito:
  síntesis NO ve los artículos, solo los spans verificados — así no fabrica).
- Matching por SLUG (los prompts responden "medio":"slug"). Comparación descarta pares del
  mismo medio (es inter-medio). Corroboración colapsa a 1-artículo-por-medio (más reciente)
  para el prompt, pero cluster_key/member_hashes reflejan el clúster COMPLETO.
- GATE VERBATIM (load-bearing): todo span debe ser subcadena literal (≥6 palabras) del texto
  del medio declarado; los que no, se descartan antes de guardar. Aplica a diferencias,
  hechos_corroborados Y solo_un_medio (Claude Code lo extendió a esta última, correcto).
- Caché por hash: par existe -> skip; cluster_key existe -> skip. Cache derivado idempotente.
- Robustez: try/except por par/clúster (un fallo no tumba la corrida) + resumen final
  guardados/skip/fallidos. LLM con retry de JSON + reintento en 429.

**VALIDADO end-to-end (story 84a548f5..., 11 arts / 55 pares):**
- Corre sin colgarse (Python 3.14 tolerable con no-streaming).
- Caché confirmado: 2ª corrida = 54 skip de 56. Reanuda incremental donde quedó.
- Fallos de JSON: transitorios de GLM (NO sistemáticos — desaparecieron al reintentar).
  try/except los absorbe. Tasa ~0-3.6%, tolerable (par ausente ≠ mentira publicada).
- Síntesis LEÍDA: sintetiza bien PERO introdujo una causalidad no respaldada ("cierre de
  14 embajadas... lo que implicará romper relaciones únicamente con Cuba y Nicaragua").
  Versión suave del error Pizarro; el verificador no la cubre. Deuda, no bloqueante.

## PRÓXIMO PASO cuando retomemos — SPLIT DE BEATS / AGRUPACIÓN TEMPORAL (bloqueante)
El costo es CUADRÁTICO (C(n,2)): 11 arts=55 pares=~30min; 90 arts=4005 pares=~36h;
128 arts=8128 pares=~73h. Un solo beat tumba el cron. SIN esto no hay backfill.
1. **Decidir el mecanismo:** Louvain puro (ya validado: res 1.6, churn 0) VS. agrupación
   por VENTANA TEMPORAL (idea de Jota, probablemente mejor): agrupar artículos del clúster
   por día/ventana y comparar solo dentro de la ventana. Ataca las 3 cosas de una: costo
   cuadrático + confound temporal + legibilidad. Decisión de diseño con cabeza fresca.
2. **Tope de tamaño de clúster** como guardarraíl del cron (si n>N, no comparar exhaustivo).
3. **Enganche al cron:** workflow con Python 3.12; job de análisis después del clustering.
4. **Backfill inicial** (carga completa, no incremental; correr en CI/background).

## Deudas activas (detalle en BITACORA)
- **[NUEVA 2026-07-22, BLOQUEANTE] Costo cuadrático C(n,2).** Split de beats / agrupación
  temporal antes del backfill. Tope de tamaño de clúster para el cron.
- **[NUEVA 2026-07-22] Síntesis introduce causalidad no respaldada.** ("lo que implicará
  romper relaciones..."). Versión suave del error Pizarro; el verificador no la ve.
  Mitigación futura: prohibir conectores causales en SYS_SINTESIS, o disclaimer visible.
- **[NUEVA 2026-07-22] Fallos de JSON transitorios de GLM** (~0-3.6%). Absorbidos por
  try/except + retry. Vigilar la tasa a escala; si sube, endurecer el parser.
- **[NUEVA 2026-07-22] Caché se "ensucia" por colapso 1-art-por-medio:** una 2ª versión de
  un medio en el clúster cambia cluster_key aunque el contenido analizado sea casi igual.
  Correcto, no urgente.
- **[2026-07-22, BLOQUEANTE PROD] Python 3.14 cuelga sockets.** Workflow CI en 3.12.
- **[2026-07-21] salvedad beta: categoría no validada + caducidad temporal** (mostrar con
  fecha; preliminar/presunto->confirmado cambia con el tiempo).
- **[2026-07-21] Boilerplate se cuela como hecho/diferencia.** Limpiar antes del LLM.
- **[2026-07-20, CRÍTICA] Vorágine=0, RTVC 4.2% en cobertura cruzada.** Deuda de pipeline.
- **[UI Fase 2, Claude Code] Timeline: separador de día** (línea al cruzar fecha) + rango
  inicio/fin/duración. Zona horaria America/Bogotá. Unidad aparte.
- **[VIGENTE] `tipo` poco fiable entre medios** — para el filtro de rol.
- **[PENDIENTE] Centroide-por-medio: sesgo direccional. delete-then-insert story_*.**

## Ideas registradas (no son scope ahora)
- **[v2, la dirección siguiente fuerte] Resumen por DÍA-del-clúster, no por clúster entero.**
  Agrupar por ventana temporal y (a) comparar solo dentro de la ventana (resuelve costo +
  confound temporal) y (b) una síntesis por día anclada al timeline, como pestaña flotante
  junto a la fecha. Cambia la unidad del resumen (cluster_key -> cluster+ventana) y el
  esquema. NO construir hasta que v1 (resumen por clúster) esté en producción.
- **[Idea] Reevaluar piezas del carril per-artículo con GLM, SEPARANDO los dos tipos de
  muerte:** las que murieron por ARITMÉTICA del FP (clasificación de clase rara) -> GLM NO
  las revive. Las que murieron por CAPACIDAD del 70B (juicio contextual: patrón 4 valoración
  por extracción, salvedad semántica) -> SÍ merecen reintento. Fijar base rate antes. Unidad
  propia, después del pipeline.
- Pipeline híbrido de modelos; cache de prompt en comparación; TTS diferido; historias
  solo desde 3+ artículos.

## Cómo verificar el estado
- Cron post-merge en verde. Web Fase 2: /historias, /historia/[id].
- Tablas nuevas: comparaciones, resumenes (creadas y con datos de la prueba).
- Módulo: crawler/analisis_fase3.py. Prueba manual: `python analisis_fase3.py <story_id>`.
- Prompts congelados = los de diag_v1_solospans.py (comparación) y diag_bakeoff2.py
  (corroboración+síntesis). NO editarlos sin re-medir.
- LLM: GLM-5.2 vía DeepInfra. Local: OJO Python 3.14 (usar no-streaming; producción 3.12).