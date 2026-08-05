# TRASPASO — Estado volátil de Trama
> Última actualización: 2026-08-01 (sesión CORROBORACIÓN + SÍNTESIS POR DÍA. La síntesis y la
> corroboración migran de por-clúster a POR-DÍA. Síntesis por día EN PRODUCCIÓN (mató el F5 de
> deriva causal). Corroboración por día LISTA en código+esquema, pendiente validar en Actions.
> Síntesis única RETIRADA. Filtro de boletines-agregador ampliado. Truncamiento JSON resuelto
> vía max_tokens. SYS_CORROBORA v2 techo-con-prioridad.)
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
- Los diag_*.py y sus .md de salida son desechables y NO se commitean (van al .gitignore).
- **Umbral de éxito se fija ANTES de correr.**
- **Ningún % corona una feature sin LEER material real** (2026-07-20).
- **El error del modelo se DESPLAZA, no se reduce, cuando redacta** (2026-07-21).
- **Éxito concluyente, fracaso no (en generación):** un modelo mejor puede resolver lo que otro
  falla. GLM resolvió la deriva del 70B (2026-07-22).
- **El verificador mecánico ordena; la fidelidad la juzga el ojo humano.** El substring valida
  procedencia, NO relación causal ni equivalencia semántica.
- **Un ítem malo no tumba el batch:** try/except por ítem + retry.
- **El instrumento de medición también se valida** (2026-07-30): un diag que mide la métrica
  equivocada miente con números.
- **Antes de culpar al código, descartar el entorno** (2026-07-30 / reforzado 2026-08-01).
- **[NUEVO 2026-08-01] El gate mecánico no distingue "el modelo fabrica" de "el input estaba
  mutilado".** Con cuerpos completos GLM NO fabricó el puente causal de Popayán; con solo los
  spans corroborados (input pobre), SÍ. El spans-only pudo CAUSAR el F5, no prevenirlo. Cuando
  el modelo es robusto, dar contexto > restringir.
- **[NUEVO 2026-08-01] Trocear por DÍA mata la deriva causal por construcción.** Una foto de un
  día no tiene material inter-temporal con el que soldar causas equivocadas. El F5 nació de
  encadenar eventos separados por semanas.
- **[NUEVO 2026-08-01] Techo, NO cuota.** "Máximo N" hace que el modelo rellene hasta N (todos
  los días daban exactamente 5 hechos). "Hasta N, priorizado por fuerza de corroboración, y
  menos si corresponde" evita el relleno.
- **[NUEVO 2026-08-01] Ver el crudo ANTES de fijar el fix.** El truncamiento JEP parecía
  "comillas sin escapar"; el crudo mostró comillas BIEN escapadas y JSON cortado por max_tokens.
  La hipótesis equivocada llevaba al parche equivocado.

## Quién soy / qué es Trama
Jota (Johan), dev único. Trama: hemeroteca forense de medios colombianos. En producción:
trama-co.vercel.app. Claude = "Claudio".

## Stack
Crawler Python en GitHub Actions cada 6h → Supabase (Postgres + pgvector) → Next.js 14 en
Vercel. Monorepo Mr-JotA-94/trama (/crawler, /web, /supabase/migrations).
**LLM Fase 3: zai-org/GLM-5.2 (DeepInfra) — SELLADO. temp 0.15, max_tokens 16000** (subido de
6000 el 2026-08-01: la corroboración por día con spans largos rebasaba 6000 y truncaba el JSON).
**PROMPT_VERSION = v2** (global; v2 = SYS_CORROBORA techo-con-prioridad). Filas v1 viejas
coexisten; el campo prompt_version dice qué generación produjo cada una.
**ENTORNO PRODUCCIÓN = GitHub Actions (Linux x86_64), wheels para todo, UTF-8 por defecto.**
El pipeline real vive AHÍ; validar carriles de respuesta larga (corroboración) AHÍ, no en local.
**ENTORNO LOCAL (laptop de Jota) = Windows ARM64 + Python 3.14 — hostil para diags pesados.**
Bug de sockets SSL de 3.14 (timeouts no respetados, respuestas vacías/truncadas en llamadas
largas) + falta de wheels ARM64 (torch/cryptography compilan desde fuente, sin linker). NO es
un problema a "arreglar" para igualar Actions: es otra plataforma. Local sirve para escribir
código, commits y diags livianos que solo hablan con APIs. NO validar corroboración en local.

## Banco: 7 medios. Corpus ~9400+ filas / crece ~1000/día.
En cobertura cruzada: Vorágine=0, RTVC baja (deuda de pipeline).

## DÓNDE ESTAMOS

**Fase 1 COMPLETA. Fase 2 EN PRODUCCIÓN** (clustering + feed + grafo, CI 6h).

**Fase 3 — pipeline inter-medio. Estado por carril:**

- **COMPARACIÓN (por par): validada y en producción.** La lectura de calidad de las 103
  comparaciones del clúster 54b1342f confirmó que las divergencias que marca son reales
  (categorías bien usadas, salvedades con marcador léxico, sin boilerplate, compuerta
  es_mismo_hecho sólida). El F5 NO estaba aquí: estaba en la síntesis. Selección de pares por
  ventana-día + colapso 1-por-medio-por-ventana (costo cuadrático resuelto).

- **SÍNTESIS POR DÍA: EN PRODUCCIÓN.** `procesar_dia` genera un digest breve por ventana-día con
  los cuerpos COMPLETOS del día. Reemplazó la síntesis única por clúster (que fabricaba el F5).
  Validada: mató el F5 por construcción (el día del cambio de sede atribuye a seguridad/volcán,
  no a Petro), sin structural collapse hasta 234k chars/día (Louvain NO es prerequisito de la
  síntesis). Longitud variable según densidad del día (aceptada por diseño). 22 días del clúster
  54b1342f poblados.

- **CORROBORACIÓN POR DÍA: LISTA (código + esquema), PENDIENTE VALIDAR EN ACTIONS.** `procesar_dia`
  hace, tras la síntesis, una segunda pasada de corroboración por ventana-día. Gate verbatim
  FUSIONADO POR MEDIO: todas las notas de un medio ese día se unen en un bloque, y cada span
  valida contra ese texto unido (así no se pierden sub-hechos cuando un medio publica varios
  temas el mismo día — objeción de Jota resuelta). Corrobora entre medios DISTINTOS (2+ slugs).
  NO se pudo validar en local (entorno ARM64 corrompe las respuestas largas). Se valida en Actions.

- **CORROBORACIÓN POR CLÚSTER (`resumenes`): VIVA, a RETIRAR.** La deja intacta hasta que la
  por-día valide en producción. Sobre hilos largos daba timeout y corroboraba mal (un
  representante por medio de semanas).

**ESQUEMA (aplicado a mano + espejado en /migrations):**
- `comparaciones` (por par): hash_a/b (unique, CHECK hash_a<hash_b), article_a/b (FK SET NULL),
  diferencias jsonb, es_mismo_hecho, divergencia_relevante, desfase_temporal, modelo, prompt_version.
- `resumenes` (por clúster): cluster_key (unique), story_id (FK SET NULL), article_ids[],
  member_hashes[], hechos_corroborados jsonb, solo_un_medio jsonb, sintesis text (ahora NULL:
  la síntesis única fue retirada de analizar_cluster), modelo, prompt_version.
- **`resumenes_dia` (por día, NUEVA):** id, story_id (FK ON DELETE CASCADE), dia date, dia_key
  text UNIQUE (sha256 del set de hashes del día = idempotencia), sintesis text, article_ids[],
  member_hashes[], medios text[], modelo, prompt_version, created_at. **+ ALTER 2026-08-01:**
  hechos_corroborados jsonb NOT NULL DEFAULT '[]', solo_un_medio jsonb NOT NULL DEFAULT '[]'.
  CASCADE (no SET NULL como resumenes) porque la poda de stories es acotada y el dia_key UNIQUE
  hace que SET NULL deje huérfanos que colisionan al renacer la historia.

**MÓDULO: crawler/analisis_fase3.py**
- `_un_articulo_por_medio`: colapso con desempate TOTAL por hash (fix determinismo 2026-07-31:
  el '>' estricto dejaba el ganador al orden de entrada cuando dos capturas del mismo medio
  empatan en _fecha_de; rompía la idempotencia del caché).
- `procesar_dia` (Tier 2): por ventana-día, síntesis (SYS_SINTESIS_DIA, cuerpos completos) +
  corroboración (SYS_CORROBORA, gate fusionado por medio). Idempotente por dia_key. Reemplaza a
  sintetizar_por_dia.
- `analizar_cluster`: síntesis única RETIRADA (sintesis=None). La corroboración por clúster sigue
  (hechos_corroborados/solo_un_medio en `resumenes`).
- GATE VERBATIM (load-bearing): span = subcadena literal (≥6 palabras) del texto del medio.
- SYS_CORROBORA v2: hasta 6 hechos / 4 solo-un-medio, ordenados por fuerza de corroboración,
  techo-no-cuota (da menos si el día tiene menos).
- Robustez: try/except por par/clúster/día + retry de JSON + reintento en 429.

## PRÓXIMO PASO cuando retomemos — VALIDAR CORROBORACIÓN POR DÍA EN ACTIONS
1. **Aplicar MAX_TOKENS=16000** en analisis_fase3.py (si no quedó en el commit de cierre).
2. **Paso de transición (operación sobre datos):** `DELETE FROM resumenes_dia WHERE story_id =
   '54b1342f-71cc-5ae9-8c6c-b90c9eee2e31'` — las 22 filas viejas se generaron sin corroboración
   (columnas nuevas en '[]'); idempotencia por dia_key las salta, así que hay que borrarlas para
   que `procesar_dia` las regenere completas. Es caché derivado, no archivo: cero riesgo.
3. **Correr `procesar_dia` en Actions (x86)** sobre el clúster y verificar: (a) el truncamiento
   JEP se resolvió con max_tokens (JSON completo); (b) el techo-con-prioridad da VARIACIÓN de
   hechos por día (días flacos 2-3, densos hasta 6 — no todos pegados al tope); (c) la
   corroboración por día es correcta a lectura humana; (d) sin timeouts (era ruido ARM64).
4. Si valida: **retirar la corroboración por clúster** (`resumenes`) y decidir si `resumenes_dia`
   pasa a ser la única tabla de resumen.
5. Sigue pendiente (de antes): **backfill reanudable** (~8.4h > 6h de Actions) y **enganche al
   cron** con Python 3.12 en CI.

## Deudas activas (detalle en BITACORA)
- **[RESUELTA 2026-08-01] F5 / síntesis con causalidad no respaldada.** Resuelto por troceo por
  día (síntesis por día no encadena causas inter-temporales). La síntesis única fue retirada.
- **[RESUELTA 2026-08-01] Boilerplate/agregadores como puente entre temas.** Filtro en
  clustering_fase2 excluye "duerma-informado" y "desayune-informado" de La Silla Vacía (41
  suprimidos). "diario-del-empalme" NO se filtra: es serie monotemática legítima.
- **[RESUELTA 2026-08-01] Truncamiento de JSON en corroboración (JEP).** Causa: max_tokens=6000
  insuficiente para outputs de corroboración con spans largos (NO era encoding ni comillas).
  Fix: max_tokens=16000. Vigilar si algún clúster aún rebasa.
- **[NUEVA 2026-08-01] Corroboración por día sin validar en producción.** Código+esquema listos;
  el entorno local ARM64/3.14 no permite correrla. Validar en Actions (ver próximo paso).
- **[NUEVA 2026-08-01] Código muerto tras retirar síntesis única.** SYS_SINTESIS,
  _prompt_usuario_sintesis y _verificar_sintesis_parcial quedan sin uso en analisis_fase3.py.
  Limpieza en commit posterior (se dejaron para acotar el diff).
- **[NUEVA 2026-08-01] Entorno local Windows ARM64.** Sin wheels para varias deps (torch,
  cryptography → compilan desde fuente, sin linker). Bug SSL de Python 3.14 corrompe respuestas
  largas. Decisión: NO validar carriles pesados en local; usar Actions. Ver Ideas para paliativos.
- **[BLOQUEANTE BACKFILL, 2026-07-30] Backfill completo ~8.4h > 6h de Actions.** Reanudable por
  lotes / self-hosted runner / varios jobs. El caché ya lo hace reanudable.
- **[2026-07-22] Caché se "ensucia" por colapso 1-art-por-medio.** Correcto, no urgente.
- **[2026-07-21] salvedad beta:** categoría no validada + caducidad temporal (mostrar con fecha).
- **[2026-07-20, CRÍTICA] Vorágine=0, RTVC baja en cobertura cruzada.** Deuda de pipeline.
- **[VIGENTE] `tipo` poco fiable entre medios** — para el filtro de rol.
- **[PENDIENTE] Centroide-por-medio: sesgo direccional. delete-then-insert story_*.**

## Ideas registradas (no son scope ahora)
- **[Idea, reforzada 2026-08-01] Louvain beat-split para mega-clústeres.** El filtro de boletines
  NO lo resolvió (el clúster 54b1342f sigue ~261 arts): es hilo político genuino de 3 semanas
  que la transitividad mantiene unido, no basura agregadora. Sigue siendo prerequisito de un
  backfill de comparación limpio y de una corroboración que no mezcle sub-hechos del mismo día.
- **[Idea, tooling local] Separar requirements:** `requirements-fase3.txt` mínimo (requests,
  dotenv, supabase sin extras de crypto) para diags locales sin compilar el stack de ML;
  `requirements.txt` completo solo para el runner x86 de Actions.
- **[Idea, tooling local] `open()` del proyecto con `encoding='utf-8'` explícito** (Windows
  default cp1252 rompe con acentos). En Actions/Linux no pasa; es arruga local.
- **[Idea, tooling local] Ordenar PATH de Python:** quitar el 3.13-arm64 que winget dejó al
  frente; fijar la versión del proyecto (idealmente el launcher `py -3.X` explícito).
- **[Idea] PROMPT_VERSION por carril** (COMPARA/CORROBORA/SINTESIS) en vez de global, si la
  coexistencia v1/v2 estorba la auditoría.
- **[Idea] Simplificar el resumen a una sola tabla `resumenes_dia`** si la corroboración por día
  valida y se retira `resumenes`.
- **[Idea] "Leer con Gemini" / breakdown cronológico:** es el MISMO objeto que la síntesis +
  corroboración por día con atribución de medios. Ya no es feature aparte; el front lo arma
  leyendo resumenes_dia en orden.
- **[Idea] Circuit-breaker por corrida; pipeline híbrido; cache de prompt; TTS diferido;
  historias solo desde 3+ artículos; reevaluar carril per-artículo separando muerte-por-aritmética
  de muerte-por-capacidad.**

## Cómo verificar el estado
- Cron post-merge en verde. Web Fase 2: /historias, /historia/[id].
- Tablas: comparaciones, resumenes, resumenes_dia (con datos del clúster 54b1342f).
- Módulo: crawler/analisis_fase3.py. Prueba manual: `python analisis_fase3.py <story_id>`.
  1ª línea: "Pares a evaluar (ventana-día + colapso): N (exhaustivo habría sido M)".
  Salida final incluye "resúmenes por día — N guardados, M skip".
- Clustering: `python clustering_fase2.py` imprime "Excluidos N boletines-agregador".
- LLM: GLM-5.2 vía DeepInfra, max_tokens 16000, PROMPT_VERSION v2. Validación de corroboración
  por día: en Actions x86, NO en la laptop ARM64.
