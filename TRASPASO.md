# TRASPASO — Estado volátil de Trama
> Última actualización: 2026-08-09 (sesión ROBUSTEZ + CONSOLIDACIÓN FASE 3. Corroboración
> por día VALIDADA en prod con lectura humana. Opción A —desacople resumenes_dia↔sid vía
> adopción perezosa— IMPLEMENTADA Y VALIDADA (V3). Retirada la corroboración por clúster.
> feat/indice-trama MERGEADO a prod.)
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
- Los diag_*.py y sus .md de salida son desechables y NO se commitean.
- **Umbral de éxito se fija ANTES de correr.**
- **Ningún % corona una feature sin LEER material real** (2026-07-20).
- **El error del modelo se DESPLAZA, no se reduce, cuando redacta** (2026-07-21).
- **El verificador mecánico ordena; la fidelidad la juzga el ojo humano.** El substring valida
  procedencia, NO relación causal ni equivalencia semántica.
- **Un ítem malo no tumba el batch:** try/except por ítem + retry.
- **El instrumento de medición también se valida.** REFORZADO 2026-08-09: mis propios patrones de
  grep de verificación también son instrumento — `_prompt_usuario_` sin \b matcheaba una función
  viva; el word-boundary importa.
- **Antes de culpar al código, descartar el entorno.** REFORZADO 2026-08-09: DeepInfra devolvió
  body vacío ('') transitorio; re-correr (idempotencia) lo distinguió de fallo determinista.
- **[2026-08-01] Trocear por DÍA mata la deriva causal por construcción.**
- **[2026-08-01] Techo, NO cuota.** "Hasta N, priorizado por fuerza, menos si corresponde."
- **[2026-08-01] Ver el crudo ANTES de fijar el fix.** REAFIRMADO 2026-08-09: el fallo del día
  denso PARECÍA max_tokens y era TIMEOUT; leer el mensaje del error lo cantó. Subir max_tokens no
  habría arreglado nada.
- **[2026-08-08] Sobre-split < sub-split.** No afinar la resolución de Louvain al ver un
  sobre-split: reabre la calibración entera, es otra unidad.
- **[2026-08-08] La hermandad es verdad mecánica (mismo componente union-find), no umbral.**
- **[2026-08-08] git status como paso del CIERRE.** MORDIÓ DE NUEVO 2026-08-09: docs de gobernanza
  (TRASPASO/BITACORA/Arquitectura) viajaron modificados-sin-commitear entre ramas. Commit de doc
  ANTES de cambiar de rama o borrar ramas.
- **[2026-08-08] El doc de arquitectura puede mentir sobre lo que el código EXPONE.** Confirmar en
  código/prod real. CASO VIVIDO 2026-08-09: "en mi mente indice-trama ya estaba en producción" —
  y estaba en rama sin mergear. `git branch --merged main` es la verdad, no la memoria.
- **[2026-08-09] El clustering NO es incremental: re-particiona el corpus entero cada corrida.**
  Una historia puede GANAR/PERDER artículos de días ya no capturados porque el IDF global se
  recalibra con el corpus nuevo. NO es "encaje forzado": es corrección de membresía. Verificar
  leyendo material (títulos + urls_unicos), no por intuición. Que las historias "respiren" es la
  propiedad que permite corregir errores tempranos de agrupamiento.
- **[2026-08-09] Condición de carrera crawler↔validación manual.** El uuid_estable = uuid5 del
  artículo más antiguo; si el clustering corre durante una validación manual, el sid puede
  recalcularse, `stories` borra el viejo y (antes de Opción A) el CASCADE se llevaba resumenes_dia.
  Síntoma vivido: "log dice guardado, la tabla da 0". Para sid estable: congelar crawler durante la
  ventana, o leer el resultado antes del próximo ciclo de 6h. (El crawler NUNCA se congeló esta
  sesión; el sid migró 6678516b→5147e4cd a mitad de validación.)
- **[2026-08-09] resumenes_dia es DERIVADO y regenerable, NO archivo inmutable.** La regla
  "fila nueva, nunca UPDATE" aplica a `articles` (evidencia forense), no al análisis. Un día se
  re-analiza SII su dia_key cambia; al cambiar, la versión previa se RETIRA (no se acumula).

## Quién soy / qué es Trama
Jota (Johan), dev único. Trama: hemeroteca forense de medios colombianos. Prod:
trama-co.vercel.app. Claude = "Claudio".

## Stack
Crawler Python en GitHub Actions cada 6h → Supabase (Postgres + pgvector) → Next.js 14 en
Vercel. Monorepo Mr-JotA-94/trama (/crawler, /web, /supabase/migrations).
**LLM Fase 3: zai-org/GLM-5.2 (DeepInfra) — SELLADO. temp 0.15, max_tokens 16000.**
**TIMEOUT_TOTAL = 300** (subido de 120 el 2026-08-09: la corroboración de días densos —4+ medios
sobre evento masivo— rebasa 120s de generación. NO era max_tokens: era TIEMPO. En main, validado.)
**PROMPT_VERSION = v2.** Filas v1 viejas coexisten en `comparaciones` (237 v1 / resto v2).
**ENTORNO PROD = GitHub Actions (Linux x86_64).** El pipeline LLM vive AHÍ.
**ENTORNO LOCAL = Windows ARM64 + Python 3.14 — hostil.** Bug SSL 3.14 corrompe respuestas
LARGAS. NO validar corroboración por día en local. (Terminal local = CMD/PowerShell: no hay
`grep`/`gh` salvo que se instalen; usar `findstr`/`Select-String`, o la web de Actions.)

## Banco: 7 medios. Corpus ~11962 filas / crece ~1000/día.

## DÓNDE ESTAMOS

**Fase 1 COMPLETA. Fase 2 EN PRODUCCIÓN + LOUVAIN BEAT-SPLIT** (clustering + feed + grafo, CI 6h).
Louvain: componentes >50 → louvain_communities (res 1.6, seed 42), determinista. Arista
`misma_trama` en story_relations.

**FRONTEND "DE LA MISMA TRAMA": MERGEADO A MAIN / EN PRODUCCIÓN (2026-08-09).** Índice cronológico
de sub-hechos hermanos. Ya no está en rama; confirmado con `git branch --merged`.

**Fase 3 — pipeline inter-medio. Estado por carril:**
- **COMPARACIÓN (por par): validada y en producción.**
- **SÍNTESIS POR DÍA: EN PRODUCCIÓN.**
- **CORROBORACIÓN POR DÍA: VALIDADA EN PRODUCCIÓN (2026-08-09).** Robustez por-día + timeout=300
  probados sobre el día más denso del corpus (presidencia del Senado, 37-38 notas/4 medios).
  Calidad leída a ojo: hechos duros (56 vs 45 votos, revés a De La Espriella, coalición PH como
  acción) separados de encuadres en solo_un_medio. DEUDA conocida (BITACORA): el gate agrupa
  hecho+encuadre cuando comparten suceso; desempeño variable por día. No bloqueante.
- **CORROBORACIÓN POR CLÚSTER (`analizar_cluster` / tabla `resumenes`): RETIRADA (2026-08-09).**
  Código borrado del módulo (rama chore/retirar-corroboracion-cluster, mergeada). La TABLA
  `resumenes` queda huérfana a propósito: DROP en migración aparte en unas semanas si nada la
  extraña (código es reversible por git; DROP no).

**OPCIÓN A — DESACOPLE resumenes_dia↔sid: IMPLEMENTADA Y VALIDADA (2026-08-09).**
Migración 000018: FK story_id CASCADE→SET NULL + story_id nullable. `dia_ya_existe` devuelve fila
(no bool); `procesar_dia` ADOPTA (UPDATE story_id, cero LLM) los días huérfanos/migrados de
composición intacta, en vez de regenerarlos. Devuelve 4-tupla (guardados, saltados, adoptados,
fallidos). V3 validado en Actions: línea `día 2026-07-17 — adoptado (sid previo obsoleto)` con 0
llamadas LLM. Cobertura parcial: el camino "story_id distinto pero NO NULL" no se ejercitó
(mismo if, riesgo bajo).

**FIX un-análisis-por-día (2026-08-09):** `guardar_resumen_dia` hace DELETE post-insert de
versiones previas del mismo (story_id, dia), EXCEPTO la recién creada (neq id). Insert primero: si
falla, la versión vieja sobrevive en vez de perderse el día. Resuelve los duplicados por día que
aparecen cuando la composición de un día cambia (dia_key nuevo coexistía con el viejo).

**ESQUEMA:**
- `comparaciones` (por par): hash_a/b, sin story_id. Sobrevive a cualquier re-split.
- `resumenes` (por clúster): HUÉRFANA, a DROPEAR en migración futura.
- `resumenes_dia` (por día): dia_key UNIQUE, story_id (FK **ON DELETE SET NULL**, nullable),
  sintesis, hechos_corroborados/solo_un_medio jsonb. **`dia` es TIMESTAMP con hora, NO date:**
  filtrar por RANGO (`>= 'X' AND < 'X+1'`), la igualdad `dia = 'X'` NO matchea.
- `story_relations` + columna `tipo` ('tematica'|'misma_trama'). Migración 000017.
- **Migración 000018** aplicada a mano + espejada: CASCADE→SET NULL en resumenes_dia.

**MÓDULO crawler/analisis_fase3.py — estado tras esta sesión:**
- `procesar_dia`: try/except por día + `pasada` + adopción perezosa. Devuelve 4-tupla.
- `guardar_resumen_dia`: DELETE post-insert (un análisis vigente por día).
- `TIMEOUT_TOTAL=300`.
- BORRADO: analizar_cluster, cluster_key_de, cluster_ya_existe, guardar_resumen, SYS_SINTESIS,
  _verificar_sintesis_parcial (+ regex), _prompt_usuario_corrobora, _prompt_usuario_sintesis.
- CONSERVADO (crítico): SYS_CORROBORA (compartido con _corroborar_dia), SYS_COMPARACION,
  analizar_par, todo el carril por día.
- VERIFICAR pendiente (no bloqueante): si `_un_articulo_por_medio` quedó huérfano tras el retiro
  (lo usaba analizar_cluster). Inofensivo; limpiar en próxima pasada si no tiene otro llamador.

## PRÓXIMO PASO cuando retomemos
1. **[SIGUIENTE UNIDAD] Backfill reanudable.** ~8.4h de trabajo LLM > límite 6h de Actions → hay
   que chunkear con corte por tiempo + reanudabilidad. Ya hay media solución: idempotencia por
   dia_key + caché por hash_a/hash_b = re-run salta lo hecho. Falta: control de tiempo (cortar
   limpio antes del límite) y ORDEN de procesamiento (prioridad: recientes × cobertura n_medios;
   historias de 2 artículos AL FINAL). Es unidad grande, chat propio.
2. **Modelo de costos DeepInfra.** Variable que gobierna la factura recurrente: cuántos dia_key
   cambian por ciclo de clustering (query a medir). Costo NO es acumulativo — proporcional al
   delta de composición, decae al estabilizarse el corpus. Backfill = pico único; estado estable =
   proporcional al flujo diario. Unidad propia con queries reales.
3. **Enganche de Fase 3 al cron** — DESPUÉS del clustering, mismo workflow, Python 3.12. Depende de
   1 y 2. Es la corona, y su propia mini-saga.
4. DROP de tabla `resumenes` (migración) cuando pasen semanas sin extrañarla.

## Cómo verificar (queries de esta sesión)
- Densidad por historia (elegir banco): CTE por_dia, max(arts_dia) pico + max medios. Unir
  articles→outlets por outlet_id (el medio es outlets.slug, NO columna de articles).
- Canario de huérfanas: `SELECT count(*) FILTER (WHERE story_id IS NULL) FROM resumenes_dia;`
- Duplicados por día: `... GROUP BY story_id, dia HAVING count(*) > 1;` (debe ser vacío tras el fix).
- Leer resumenes_dia: filtrar `dia` por RANGO, no igualdad.
- Distinguir transitorio vs determinista de DeepInfra: re-correr (idempotencia) y ver si entra.