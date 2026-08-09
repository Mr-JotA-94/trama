# TRASPASO — Estado volátil de Trama
> Última actualización: 2026-08-09 (sesión VALIDACIÓN CORROBORACIÓN POR DÍA en Actions.
> Fix de robustez por-día validado en prod; causa del fallo del día denso = TIMEOUT en
> corroboración, resuelto con TIMEOUT_TOTAL=300 (en main). Corroboración por día LEÍDA
> sobre material real y aprobada, con una deuda de calidad registrada. feat/indice-trama
> sigue PENDIENTE MERGE de la sesión anterior.)
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
- **El instrumento de medición también se valida** (2026-07-30 / reforzado 2026-08-08): un diag
  que mide la métrica equivocada miente con números. El U1 (réplica==producción) es el gate
  del propio diag antes de creer en el resto.
- **Antes de culpar al código, descartar el entorno** (2026-07-30 / reforzado 2026-08-01 y 08-09).
- **[2026-08-01] El gate mecánico no distingue "el modelo fabrica" de "el input estaba
  mutilado".** Con cuerpos completos GLM NO fabricó el puente causal de Popayán; con solo los
  spans (input pobre), SÍ. Cuando el modelo es robusto, dar contexto > restringir.
- **[2026-08-01] Trocear por DÍA mata la deriva causal por construcción.**
- **[2026-08-01] Techo, NO cuota.** "Hasta N, priorizado por fuerza, menos si corresponde."
- **[2026-08-01] Ver el crudo ANTES de fijar el fix.** La hipótesis equivocada lleva al parche
  equivocado (el truncamiento JEP era max_tokens, no comillas). REAFIRMADO 2026-08-09: el fallo
  del día denso PARECÍA max_tokens y era TIMEOUT; leer el mensaje del error lo cantó.
- **[2026-08-08] Sobre-split < sub-split.** Al partir beats, una comunidad partida de más
  (dos hermanas que eran una) es costo cosmético; una partida de menos reproduce el problema
  original. Entre los dos errores, res 1.6 cae del lado barato. NO afinar la resolución al ver
  un sobre-split: reabre la calibración entera, es otra unidad.
- **[2026-08-08] La hermandad es verdad mecánica, no inferencia por umbral.** Dos
  subhistorias son hermanas SII salieron del mismo componente union-find. No se calibra: se sabe
  gratis en el momento del split. Eje distinto al coseno/n_especificas del grafo temático.
- **[2026-08-08] git status como paso del CIERRE.** El cierre del 2026-08-01 dejó BITACORA
  y Arquitectura sin commitear; viajaron sucias hasta hoy. Un status al cerrar lo canta.
- **[2026-08-08] Coherencia de nombres entre superficies.** El mismo objeto debe llamarse
  igual donde se muestre (índice vs página destino).
- **[2026-08-08] El doc de arquitectura puede mentir sobre lo que el código EXPONE.** Confirmar
  en código/prod real, no en el doc, antes de asumir qué ve el usuario.
- **[NUEVO 2026-08-09] El clustering NO es incremental: re-particiona el corpus entero cada
  corrida.** Una historia puede GANAR artículos viejos de días ya no capturados, porque el IDF
  global se recalibra con el corpus nuevo y aristas que antes no cruzaban umbral ahora sí. Eso NO
  es "encaje forzado": es corrección de un sub-conteo previo. Verificar leyendo el material
  (títulos + urls_unicos), no por intuición. Que las historias "respiren" es la propiedad que
  permite al clustering corregir sus errores tempranos.
- **[NUEVO 2026-08-09] Condición de carrera crawler↔validación manual.** El uuid_estable es
  uuid5 del artículo más antiguo del clúster; si el crawler/clustering corre durante una
  validación manual, el sid puede recalcularse, `stories` borra el viejo, y el FK
  `resumenes_dia ON DELETE CASCADE` se lleva las filas de día por delante. Síntoma vivido:
  "log dice guardado, la tabla da 0". Para validar sobre un sid estable hay que CONGELAR el
  crawler durante la ventana, o aceptar que el sid migra y leer el resultado antes del próximo
  ciclo de 6h.
- **[NUEVO 2026-08-09] Fallo transitorio del proveedor ≠ fallo determinista del input.** GLM vía
  DeepInfra devolvió body vacío ('') en el día denso una vez y al RE-CORRER (mismo input) entró.
  Un re-run idempotente (dia_key salta lo bueno, reintenta solo lo fallido) es la forma barata de
  distinguir transitorio de determinista antes de tocar código.

## Quién soy / qué es Trama
Jota (Johan), dev único. Trama: hemeroteca forense de medios colombianos. En producción:
trama-co.vercel.app. Claude = "Claudio".

## Stack
Crawler Python en GitHub Actions cada 6h → Supabase (Postgres + pgvector) → Next.js 14 en
Vercel. Monorepo Mr-JotA-94/trama (/crawler, /web, /supabase/migrations).
**LLM Fase 3: zai-org/GLM-5.2 (DeepInfra) — SELLADO. temp 0.15, max_tokens 16000.**
**TIMEOUT_TOTAL = 300** (subido de 120 el 2026-08-09: la corroboración de días densos —4+ medios
sobre evento masivo— rebasa 120s de generación. NO era max_tokens: era tiempo. En main.)
**PROMPT_VERSION = v2** (v2 = SYS_CORROBORA techo-con-prioridad). Filas v1 viejas coexisten.
**ENTORNO PRODUCCIÓN = GitHub Actions (Linux x86_64).** El pipeline LLM vive AHÍ; validar
carriles de respuesta larga (corroboración) AHÍ, no en local.
**ENTORNO LOCAL (laptop de Jota) = Windows ARM64 + Python 3.14 — hostil para diags pesados.**
Bug SSL de 3.14 (corrompe respuestas LARGAS) + falta de wheels ARM64. NO validar corroboración
por día en local.

## Banco: 7 medios. Corpus ~11962 filas / crece ~1000/día.
En cobertura cruzada: Vorágine=0, RTVC baja (deuda de pipeline).

## DÓNDE ESTAMOS

**Fase 1 COMPLETA. Fase 2 EN PRODUCCIÓN + LOUVAIN BEAT-SPLIT** (clustering + feed + grafo, CI 6h).

**LOUVAIN BEAT-SPLIT EN PRODUCCIÓN** (2026-08-08). `construir_clusteres` particiona todo
componente > UMBRAL_BEAT=50 con louvain_communities (res 1.6, seed 42). Determinista (seed +
nodos/aristas sorted). Arista `misma_trama` en story_relations para hermanas del mismo componente.

**FRONTEND "DE LA MISMA TRAMA" — EN RAMA feat/indice-trama, PENDIENTE MERGE** (de sesión 08-08).
Índice cronológico de sub-hechos hermanos arriba de /historia/[id]. 3 commits, verificado con
datos reales. FALTA: confirmar en preview que el título ya no cambia al entrar (commit 3), y MERGE.
NOTA: esta sesión (08-09) NO tocó esta rama; sigue igual que la dejó 08-08.

**Fase 3 — pipeline inter-medio. Estado por carril:**
- **COMPARACIÓN (por par): validada y en producción.**
- **SÍNTESIS POR DÍA: EN PRODUCCIÓN.** Mató el F5 por construcción.
- **CORROBORACIÓN POR DÍA: VALIDADA EN PRODUCCIÓN (2026-08-09).** Robustez por-día + timeout=300
  probados sobre el día más denso del corpus (elección presidencia del Senado, 38 notas/4 medios).
  Calidad LEÍDA a ojo: hechos duros corroborados (56 vs 45 votos, revés a De La Espriella, coalición
  PH descrita como acción) correctamente separados de encuadres en solo_un_medio. VER DEUDA en
  BITACORA: el gate agrupa hecho+encuadre cuando comparten suceso (desempeño variable por día).
- **CORROBORACIÓN POR CLÚSTER (`resumenes`): VIVA, DESBLOQUEADA PARA RETIRO.** La por-día ya validó;
  esta es la fase monolítica que sigue timeouteando en cada run (ruido en el log). Retirarla es la
  próxima unidad (Camino A).

**FIX DE ROBUSTEZ (`procesar_dia` try/except por día): EN MAIN, VALIDADO.** Aisló fallos 3× en la
sesión sin tumbar el pipeline. Antes, un día que agotaba reintentos mataba toda la fase por día.
Ahora imprime `día AAAA-MM-DD pasada=sintesis|corroboracion — FALLO` y sigue. Devuelve 3-tupla
(guardados, saltados, fallidos).

**ESQUEMA (aplicado a mano + espejado en /migrations):**
- `comparaciones` (por par): hash_a/b, sin story_id (sobrevive a cualquier re-split).
- `resumenes` (por clúster): cluster_key, story_id (FK SET NULL). A RETIRAR.
- `resumenes_dia` (por día): dia_key UNIQUE (idempotencia), story_id (FK ON DELETE CASCADE),
  sintesis, hechos_corroborados/solo_un_medio jsonb. **`dia` es TIMESTAMP con hora, NO date puro:**
  filtrar por rango (`>= 'X' AND < 'X+1'`), la igualdad exacta `dia = 'X'` NO matchea.
  **REGLA: un re-split del clúster (o migración de sid por crecimiento) obsoleta/borra vía CASCADE
  los dia_key del sid afectado. Purgar/regenerar tras cualquier re-cluster.**
- `story_relations` + columna `tipo` ('tematica'|'misma_trama'). Migración 000017.

**MÓDULO: crawler/analisis_fase3.py** (TOCADO esta sesión)
- `procesar_dia` (Tier 2): try/except por día + variable `pasada` (en main). Devuelve 3-tupla.
- `TIMEOUT_TOTAL=300` (en main).
- Sin cambios en prompts, esquema, ni max_tokens.

## PRÓXIMO PASO cuando retomemos
1. **[INMEDIATO, independiente de todo] Merge de feat/indice-trama** (heredado de 08-08).
   Confirmar en preview que el título de la hermana coincide con el <h1> destino, luego merge.
2. **[DESBLOQUEADO] Retirar corroboración por clúster (`resumenes` / `analizar_cluster`).**
   La por-día ya validó. Es código muerto que ensucia cada log con timeouts. Camino A, independiente
   de DeepInfra. Limpieza + posible retiro de SYS_SINTESIS et al. si quedaron huérfanos.
3. **[SI MOLESTA] Deuda de calidad del gate hecho-vs-encuadre** (ver BITACORA). NO bloqueante:
   el núcleo factual siempre queda bien; solo el calificativo interpretativo viaja de polizón a
   veces. Reactivar solo si a escala ensucia la lectura.
4. Sigue pendiente: **backfill reanudable** (~8.4h > 6h de Actions) + **enganche al cron** con
   Python 3.12 en CI. El clustering sigue MANUAL.

## Cómo verificar (queries útiles de esta sesión)
- Densidad por historia (elegir banco de prueba): CTE por_dia con max(arts_dia) pico + max medios.
  Unir `articles → outlets` por outlet_id (el medio NO es columna de articles: es outlets.slug).
- Leer resumenes_dia: filtrar `dia` por RANGO, no por igualdad (es timestamp).
- Distinguir transitorio vs determinista: re-correr (idempotencia salta lo bueno) y ver si entra.