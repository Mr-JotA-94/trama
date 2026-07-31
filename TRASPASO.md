# TRASPASO — Estado volátil de Trama
> Última actualización: 2026-07-30 (sesión SPLIT DE BEATS: selección de pares por VENTANA
> TEMPORAL implementada y validada end-to-end. Esquema C (ventana-día Bogotá + colapso
> 1-por-medio-por-ventana) reemplaza la comparación exhaustiva C(n,2) en analisis_fase3.py.
> Costo cuadrático RESUELTO. Nuevo bloqueante medido: backfill completo ~8.4h > límite 6h
> de GitHub Actions. Próximo paso: leer muestra de comparaciones GLM + diseñar backfill
> reanudable por lotes.)
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
- **El instrumento de medición también se valida** (2026-07-30): un diag que mide la métrica
  EQUIVOCADA miente con números. El primer diag de latencia usó un prompt trivial (22 tokens
  out) en vez de SYS_COMPARACION y "descartó" el problema con datos irrelevantes. Un diag de
  diagnóstico exige el mismo rigor de métrica que un diag de calibración: medir el camino REAL.
- **Antes de culpar al código, descartar el entorno** (2026-07-30): "12 pares en una noche"
  parecía bug de timeout; era Windows durmiéndose (sleep-timeout 5min). La latencia real medida
  (~31s/par, 1 llamada, 0 reintentos) coincidía con la estimación. El código nunca fue el lento.

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
**ENTORNO — Python 3.14 (local): bug conocido de sockets SSL con streaming.** Mitigado con
POST no-streaming + timeout 120s. CONFIRMADO estable a escala esta sesión: 115 pares seguidos,
~31s/par, 1 llamada HTTP c/u, 0 reintentos, sin cuelgues. El no-streaming basta; el bug NO se
manifestó en el backfill real. PRODUCCIÓN corre en CI: fijar el workflow a Python 3.12.
`requests==2.32.3` ya en crawler/requirements.txt. **OJO en corridas locales largas: Windows
duerme a los 5min y detiene el proceso** (ver deuda operativa). El backfill masivo NO debe
correr en la laptop.

## Banco: 7 medios. Corpus ~7000+ filas / ~6500 URLs, crece ~1000/día.
En cobertura cruzada: Vorágine=0, RTVC 4.2% (deuda de pipeline).

## DÓNDE ESTAMOS

**Fase 1 COMPLETA. Fase 2 EN PRODUCCIÓN** (clustering + feed + grafo, CI 6h).

**Fase 3 — carril de COMPARACIÓN INTER-MEDIO (a). v1 FUNCIONALMENTE COMPLETO Y PROBADO.
Selección de pares por ventana temporal IMPLEMENTADA (2026-07-30).**

**ESQUEMA (creado 2026-07-22, aplicado a mano en Supabase + espejado en /migrations):**
- Tabla `analyses` vieja (carril per-artículo, vacía) -> DROPEADA.
- `comparaciones` (por par): hash_a, hash_b (unique, con CHECK hash_a<hash_b), article_a/b
  (FK SET NULL), diferencias jsonb, es_mismo_hecho, divergencia_relevante, desfase_temporal,
  modelo, prompt_version.
- `resumenes` (por clúster): cluster_key (unique) = sha256 del set ordenado de hashes,
  story_id (FK SET NULL), article_ids[], member_hashes[], hechos_corroborados jsonb,
  solo_un_medio jsonb, sintesis text, modelo, prompt_version.

**MÓDULO: crawler/analisis_fase3.py (PROBADO, con selección por ventana).**
- Contrato LLM (3 prompts congelados = los de los diag validados): SYS_COMPARACION (por par,
  solo-spans), SYS_CORROBORA + SYS_SINTESIS (resumen, 2 llamadas SEPARADAS a propósito:
  síntesis NO ve los artículos, solo los spans verificados — así no fabrica).
- Matching por SLUG (los prompts responden "medio":"slug").
- **SELECCIÓN DE PARES POR VENTANA (nuevo, Tier 2, 2026-07-30):** `pares_por_ventana()`
  agrupa los comparables por día calendario (America/Bogota, vía `_dia_bogota`), colapsa a
  1-artículo-por-medio-por-ventana (el más reciente, reusa `_un_articulo_por_medio`) y emite
  C(medios,2) por ventana. Reemplazó el doble loop exhaustivo C(n,2) en `main()`. Función pura
  y determinista; el backfill/cron futuro la reutiliza. NO filtra ni cachea: `analizar_par`
  sigue siendo el único dueño del descarte mismo-medio/mismo-hash y del caché por hash.
- **Asimetría intencional:** comparación colapsa 1-por-medio POR VENTANA (versiones
  contemporáneas); corroboración/resumen colapsa 1-por-medio POR CLÚSTER (estado más reciente
  del hecho). No es bug — cada pasada quiere una cosa distinta. cluster_key/member_hashes
  siguen reflejando el clúster COMPLETO.
- GATE VERBATIM (load-bearing): todo span debe ser subcadena literal (≥6 palabras) del texto
  del medio declarado; los que no, se descartan antes de guardar. Aplica a diferencias,
  hechos_corroborados Y solo_un_medio.
- Caché por hash: par existe -> skip; cluster_key existe -> skip. Cache derivado idempotente.
- Robustez: try/except por par/clúster + resumen final guardados/skip/fallidos. LLM con retry
  de JSON + reintento en 429.

**VALIDADO end-to-end (esta sesión):**
- **Diag Tier 0 (diag_ventanas.py) sobre corpus real (2225 arts en clústeres):** exhaustivo
  35.174 pares (~322h LLM) -> esquema C 973 pares (~8.9h). nulls de fecha_publicacion = 0.0%.
  Corte de medianoche = 0 pares perdidos (Δt≤6h entre ventanas adyacentes, medios distintos).
  Los 4 umbrales pre-registrados pasaron. Esquema C ratificado.
- **Lógica probada en aislamiento (5 casos sintéticos):** colapso 1-por-medio, separación de
  días (mata el confound), techo duro C(7,2)=21/ventana, corte de medianoche, determinismo
  ante reordenamiento del input (importa para idempotencia del caché).
- **Corrida real sobre story 54b1342f... (posesión Abelardo de la Espriella, 253 arts / 115
  pares por ventana vs 31.878 exhaustivo):** 103 guardados, 12 skip (caché), 1 fallido (JSON
  malformado de GLM, span truncado — recuperable por caché). resumen guardado. ~53 min con
  la máquina despierta. Latencia por par ~31s, coincide con la estimación de diseño (33s).

## PRÓXIMO PASO cuando retomemos — LECTURA DE CALIDAD + DISEÑO DE BACKFILL
El costo cuadrático está resuelto; el bloqueante ahora es de ESCALA-EN-CI y de CALIDAD-NO-LEÍDA.
1. **LEER una muestra de las 103 comparaciones + el resumen del clúster 54b1342f** (ya en DB).
   El gate verbatim valida procedencia, NO fidelidad. Es la primera cosecha grande de GLM en
   comparación — antes de backfilear 973 pares hay que confirmar que las divergencias que marca
   son reales y útiles, no ruido groundeado. Deuda abierta: ¿SYS_COMPARACION se calibró con GLM
   o con el 70B retirado? Verificar antes de coronar.
2. **Diseñar el backfill REANUDABLE por lotes.** Medido: 973 pares × ~31s ≈ 8.4h > límite 6h de
   Actions (runner estándar). No cabe de una. Opciones: chunking por rango de clústeres (el
   caché ya lo hace reanudable), self-hosted runner, o partir en varios jobs. Decisión de diseño.
3. **Enganche al cron:** workflow con Python 3.12; job de análisis después del clustering.

## Deudas activas (detalle en BITACORA)
- **[RESUELTA 2026-07-30] Costo cuadrático C(n,2).** Resuelto por selección de pares por
  ventana-día + colapso 1-por-medio-por-ventana (techo duro C(7,2)=21/ventana). El "tope de
  tamaño de clúster" para el cron ya NO hace falta como palanca de costo (queda opcional como
  circuit-breaker barato contra un bug futuro, no como arquitectura).
- **[NUEVA 2026-07-30, BLOQUEANTE BACKFILL] Backfill completo ~8.4h > 6h de Actions.** 973
  pares × 31s. No cabe en un job estándar. Backfill reanudable por lotes / self-hosted runner.
- **[NUEVA 2026-07-30] Calidad de comparación GLM sin leer a escala.** 103 comparaciones reales
  en DB (clúster 54b1342f) sin auditar. Leer antes de publicar/backfilear. Verificar además si
  SYS_COMPARACION se calibró con GLM o con el 70B.
- **[ACTUALIZADA 2026-07-30] Fallos de JSON de GLM.** Antes "~0-3.6% transitorios". Nuevo dato:
  1/115 = 0.87% en la corrida real; el crudo mostró JSON truncado a mitad de span
  ("...al esti"), no solo preámbulo. GLM antepone ```json y a veces corta la generación. El
  parser tolerante rescata el preámbulo pero no el truncamiento. Recuperable por caché
  (relanzar salta lo guardado). Vigilar a escala; si sube, endurecer parser / revisar max_tokens.
- **[NUEVA 2026-07-30, OPERATIVA] Windows duerme corridas locales largas.** sleep-timeout AC
  por defecto = 5min; detiene el proceso. Mitigación temporal: `powercfg /change
  standby-timeout-ac 0` durante la corrida (revertir a 5 después). Refuerza que el backfill
  masivo NO corre en la laptop.
- **[NUEVA 2026-07-22] Síntesis introduce causalidad no respaldada.** Versión suave del error
  Pizarro; el verificador no la ve. Mitigación futura: prohibir conectores causales en
  SYS_SINTESIS, o disclaimer visible.
- **[NUEVA 2026-07-22] Caché se "ensucia" por colapso 1-art-por-medio:** una 2ª versión de un
  medio cambia cluster_key aunque el contenido sea casi igual. Correcto, no urgente. (El colapso
  por VENTANA en comparación tiene el mismo comportamiento y es igual de correcto.)
- **[2026-07-22, BLOQUEANTE PROD] Python 3.14 cuelga sockets.** Workflow CI en 3.12. (No se
  manifestó en el backfill real con no-streaming; la mitigación aguanta.)
- **[2026-07-21] salvedad beta: categoría no validada + caducidad temporal** (mostrar con
  fecha; preliminar/presunto->confirmado cambia con el tiempo).
- **[2026-07-21] Boilerplate se cuela como hecho/diferencia.** Limpiar antes del LLM.
- **[2026-07-20, CRÍTICA] Vorágine=0, RTVC 4.2% en cobertura cruzada.** Deuda de pipeline.
- **[UI Fase 2, Claude Code] Timeline: separador de día** + rango inicio/fin/duración. Zona
  America/Bogotá. Unidad aparte.
- **[VIGENTE] `tipo` poco fiable entre medios** — para el filtro de rol.
- **[PENDIENTE] Centroide-por-medio: sesgo direccional. delete-then-insert story_*.**

## Ideas registradas (no son scope ahora)
- **[v2, la dirección siguiente fuerte] Resumen por DÍA-del-clúster, no por clúster entero.**
  La selección por ventana ya sienta la base (agrupa por día); v2 sería (a) una síntesis por día
  anclada al timeline, como pestaña flotante junto a la fecha. Cambia la unidad del resumen
  (cluster_key -> cluster+ventana) y el esquema. NO construir hasta que v1 (resumen por clúster)
  esté en producción.
- **[Idea, reforzada 2026-07-30] Louvain beat-split para mega-clústeres.** Backlogueado, sigue
  válido (res 1.6, churn 0). Candidato #1: clúster 54b1342f (253 arts, posesión Abelardo de la
  Espriella) — más grande que los 128/90 documentados; casi seguro mezcla beats. La ventana
  resolvió el COSTO y el confound temporal, pero NO separa beats semánticos dentro de un día
  (dos hechos distintos del mismo día se comparan; la compuerta es_mismo_hecho lo absorbe a
  costo de llamadas desperdiciadas). Louvain seguiría mejorando calidad de clúster. Después del
  backfill de v1.
- **[Idea] Circuit-breaker por corrida:** si el total de pares a generar supera un umbral,
  abortar y avisar. Seguro barato contra un bug futuro (p. ej. explosión de outlet_id), NO
  mecanismo de costo (eso lo da el colapso). Belt-and-suspenders.
- **[Idea] Reevaluar piezas del carril per-artículo con GLM, SEPARANDO los dos tipos de muerte:**
  las que murieron por ARITMÉTICA del FP (clase rara) -> GLM NO las revive. Las que murieron por
  CAPACIDAD del 70B (juicio contextual) -> SÍ merecen reintento. Fijar base rate antes. Unidad
  propia, después del pipeline.
- Pipeline híbrido de modelos; cache de prompt en comparación; TTS diferido; historias solo
  desde 3+ artículos.

## Cómo verificar el estado
- Cron post-merge en verde. Web Fase 2: /historias, /historia/[id].
- Tablas: comparaciones, resumenes (con datos: prueba vieja + clúster 54b1342f).
- Módulo: crawler/analisis_fase3.py. Prueba manual: `python analisis_fase3.py <story_id>`.
  La 1ª línea imprime "Pares a evaluar (ventana-día + colapso): N (exhaustivo habría sido M)".
- Prompts congelados = los de diag_v1_solospans.py (comparación) y diag_bakeoff2.py
  (corroboración+síntesis). NO editarlos sin re-medir.
- LLM: GLM-5.2 vía DeepInfra. Local: OJO Python 3.14 (usar no-streaming; producción 3.12) y
  deshabilitar sleep de Windows en corridas largas.
