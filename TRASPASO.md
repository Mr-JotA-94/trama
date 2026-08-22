# TRASPASO — Estado volátil de Trama
> Última actualización: 2026-08-22 (sesión MIGRACIÓN A OPENROUTER + BACKFILL ACTIVO.
> Fase 3 corre sobre OpenRouter (routing forense). Backfill de 68 historias activas
> ejecutado y confirmado en datos. Listo para montar frontend de Fase 3 —bloque propio—.)
> Autoridad: este archivo manda sobre memoria. Estado volátil vive AQUÍ.

## Quién soy y cómo trabajamos
Soy Jota (Johan). Claude es "Claudio". Reglas que NO se pierden:
- **Challenge-first:** cuestiona enfoques con fallas ANTES de construir.
- **Declarar Tier (0–3) + load-bearing antes de construir.**
- Directo, conciso, instructivo, en español. **Medir antes de arreglar.**
- Diagnóstico con datos reales. Claude Code solo para CAMBIOS de código; NO ejecuta DDL
  (migraciones a mano en Supabase + espejo en /migrations).
- **Un chat = UNA unidad de trabajo = un cierre.**
- **Flujo git:** branch antes de tocar código. Commits de doc SEPARADOS de los de código.
  `git status` ANTES de cambiar de rama (mordió 3 veces por docs sin commitear viajando).
- Los diag_*.py / smoke_*.py son desechables y NO se commitean.
- **Umbral de éxito se fija ANTES de correr.**
- **Ningún % corona una feature sin LEER material real** (2026-07-20; reafirmado en backfill 08-22:
  el conteo del log no basta, se confirma en tabla y se lee una muestra a ojo).
- **El instrumento de medición también se valida** (incluye mis propios patrones de grep/query).
- **Antes de culpar al código, descartar el entorno.** (DeepInfra degradado ≠ bug propio;
  key fantasma del entorno de Windows ≠ .env mal.)
- **Ver el crudo ANTES de fijar el fix.** La hipótesis equivocada lleva al parche equivocado.
- **[2026-08-09] Trocear por DÍA mata la deriva causal. Techo NO cuota. resumenes_dia es
  DERIVADO regenerable, NO archivo inmutable** (la inmutabilidad es de `articles`).
- **[2026-08-09] El clustering NO es incremental: re-particiona todo el corpus cada corrida.**
  Una historia gana/pierde artículos viejos al recalibrarse el IDF global. Verificar leyendo
  material, no por intuición.
- **[2026-08-09] Condición de carrera crawler↔validación manual.** El uuid5 (story_id) migra al
  recomponerse el clúster. Para sid estable: congelar crawler o leer resultado antes del ciclo 6h.
- **[2026-08-11] Fallo transitorio del proveedor ≠ fallo determinista del input.** Re-correr
  (idempotencia) distingue uno de otro antes de tocar código.
- **[2026-08-22] Un smoke/diag verde valida LÓGICA, no INTEGRACIÓN.** Que el diag funcione no
  prueba que el módulo integrado corra en Actions; eso se valida con un run real, post-merge si
  hace falta, con el primer run supervisado como gate.
- **[2026-08-22] Workflow con workflow_dispatch solo aparece en Actions si está en la rama
  default (main).** Merge del YAML a main antes de poder dispararlo.

## Stack
Crawler Python (GitHub Actions cada 6h) → Supabase (Postgres + pgvector) → Next.js 14 en Vercel.
Monorepo Mr-JotA-94/trama (/crawler, /web, /supabase/migrations).
**LLM Fase 3: GLM-5.2 vía OPENROUTER (migrado 2026-08-22 de DeepInfra directo).**
- Slug modelo: `z-ai/glm-5.2` (OpenRouter), NO `zai-org/GLM-5.2` (era el de DeepInfra directo).
- Endpoint: `https://openrouter.ai/api/v1`. Key: `OPENROUTER_API_KEY` (.env local con
  load_dotenv(override=True); Secret en Actions).
- **Payload OBLIGATORIO: `reasoning:{enabled:False}`** (GLM-5.2 es de razonamiento; sin esto
  `content` viene vacío y cobra tokens de pensamiento).
- **Provider routing forense: `{"order":["deepinfra","cloudflare","baidu"],"allow_fallbacks":False}`**
  DeepInfra preferido (proveedor del bake-off original); Cloudflare/Baidu failover validados
  forense-equivalentes (diag 08-11). allow_fallbacks=False: si los 3 caen, falla limpio en vez de
  rutear a backend no validado (varianza forense no controlada).
- temp 0.15, max_tokens 16000, TIMEOUT_TOTAL 300, PROMPT_VERSION v2.
**ENTORNO PROD = GitHub Actions (Linux x86_64).** LOCAL = Windows ARM64 + Python 3.14, hostil
para respuestas LARGAS (bug SSL 3.14). NO validar corroboración en local. Terminal local:
CMD/PowerShell, no hay grep/gh nativos (usar findstr/Select-String o la web).

## Banco: 7 medios. Corpus ~12k artículos / crece ~1000/día.

## DÓNDE ESTAMOS

**Fase 1 COMPLETA. Fase 2 EN PRODUCCIÓN + Louvain beat-split** (res 1.6, seed 42; arista
misma_trama para hermanas). **Frontend "De la misma trama" MERGEADO / en prod.**

**Fase 3 — pipeline inter-medio. TODO EN PRODUCCIÓN:**
- COMPARACIÓN por par: validada.
- SÍNTESIS + CORROBORACIÓN POR DÍA: validadas, leídas a ojo, calidad confirmada.
- Robustez por-día (try/except por día + `pasada`), TIMEOUT_TOTAL=300, desacople
  resumenes_dia↔sid con ADOPCIÓN PEREZOSA (Opción A), fix un-análisis-por-día (DELETE
  post-insert): TODO mergeado y validado, incluido a escala en el backfill.
- Corroboración por clúster (vieja): RETIRADA. Tabla `resumenes` huérfana, a DROPear en
  migración futura si nada la extraña.
- **Proveedor: OpenRouter (migrado y validado en producción 08-22).**

**BACKFILL ACTIVO — EJECUTADO Y CONFIRMADO (2026-08-22):**
- Workflow `fase3_backfill.yml` (manual, workflow_dispatch, inputs horas/presupuesto, SIN cron).
- Modo `--backfill` en analisis_fase3.py: `_historias_activas(72h)` ordenadas por recencia×cobertura,
  bucle con corte por tiempo (time.monotonic vs presupuesto, chequeo ENTRE historias), try/except
  por historia. Reanudable por idempotencia (dia_key), sin cursor persistente.
- Resultado: 68 historias activas / 128 días guardados en una corrida, 0 falladas, corte por
  tiempo validado (run de prueba 600s cortó limpio en 8 historias).
- CONFIRMADO EN TABLA: 69 historias, 166 días, 0 duplicados, histograma de hechos con spread
  (0-9), síntesis leídas a ojo = buenas. 73/76 días-con-0-hechos son n_medios=1 (correcto por
  diseño); solo 3 con n_medios=2 y 0 hechos (ruido despreciable, 1.8%).
- 9 filas huérfanas (story_id NULL) por migración de sid durante el run — esperado (SET NULL las
  preservó), se adoptan en próxima corrida.

**ESQUEMA:**
- comparaciones (por par): hash_a/b, sin story_id.
- resumenes (por clúster): HUÉRFANA, a DROPear.
- resumenes_dia: dia_key UNIQUE, story_id FK **ON DELETE SET NULL** (migración 000018), nullable.
  `dia` es TIMESTAMP (filtrar por RANGO, no igualdad). Un análisis vigente por (story_id,dia).
- story_relations + tipo ('tematica'|'misma_trama').

## PRÓXIMO PASO cuando retomemos
1. **[BLOQUE PROPIO, chat nuevo] Frontend de Fase 3.** Surface la corroboración/síntesis por día
   en /historia/[id]. Arranca con BRAINSTORM de ideas. EXPECTATIVA CORRECTA: hay datos ricos para
   las ~68 historias ACTIVAS; el histórico (~750) aún sin procesar → frontend muestra lo activo,
   histórico vendrá después. Incluye resolver el problema del TÍTULO OBSOLETO (sale de la síntesis
   del día más reciente, no del titular de un artículo).
2. **Backfill HISTÓRICO completo (Objetivo B):** las ~750 historias inactivas, de grande a chica.
   Requiere extender backfill_activas a un modo histórico. Correr supervisado o con presupuesto
   grande. Costo estimado ~$25-35 total (memoria).
3. **Enganche al cron:** Fase 3 automática tras el clustering, mismo workflow. Con OpenRouter ya
   resuelto como proveedor + failover, el riesgo de disponibilidad baja. Su propia mini-saga.
4. DROP tabla `resumenes` (migración) cuando pasen semanas sin extrañarla.
5. Limpieza periódica de huérfanas permanentes (story_id NULL viejas nunca re-adoptadas).

## Cómo verificar (queries de la sesión)
- Estado resumenes_dia: count historias/días/huérfanas; duplicados (GROUP BY story_id,dia HAVING>1);
  histograma de hechos; días-0-hechos por n_medios (para distinguir "1 medio = correcto" de deuda).
- Densidad por historia: CTE por_dia con max(arts_dia) pico; unir articles→outlets (medio = slug).
- Distinguir transitorio vs determinista de proveedor: re-correr (idempotencia).