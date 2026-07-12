# TRASPASO — Estado volátil de Trama
> Última actualización: 2026-07-12 (sesión Fase 3 — `arrastre` VALIDADO como código
> #1 de v1; mecanismo de probing por-código generalizado y documentado)
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
- **Umbral de éxito se fija ANTES de correr, no se mueve después.** (Sostenido esta
  sesión: arrastre pasó contra un umbral fijado antes de la primera corrida.)

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
**NVIDIA NIM (meta/llama-3.3-70b-instruct) FALLBACK. Groq DEPRECADO.** Cliente swappable
por LLM_PROVIDER en .env (deepinfra|nvidia|groq); **failover automático NO implementado
—se construye con el batch—**, hoy se conmuta a mano. OJO: el diag arranca en default
`nvidia`; confirmar `LLM_PROVIDER=deepinfra` por la línea `Provider:` antes de medir.

## Banco: 7 medios ACTIVOS y VALIDADOS
El Espectador, El Tiempo, El Colombiano, Las2orillas, Vorágine, La Silla Vacía, RTVC.
Corpus MEDIDO 2026-07-12: **5922 filas** (incluye recapturas por inmutabilidad; dedup
por texto al muestrear banco).

## DÓNDE ESTAMOS

**Fase 1 COMPLETA y desplegada.** Crawler, web pública.

**Fase 2 EN PRODUCCIÓN.** Vista + clustering + feed paginado + grafo de historias.
trama-co.vercel.app/historias y /historia/[id]. Pipeline automatizado (3 jobs CI), cada 6h.

**Fase 3 en calibración — un código validado, el método probado.**
- **Proveedor: DECIDIDO y VALIDADO.** DeepInfra primario, NIM fallback. Arquitectura
  por-artículo confirmada (el modo clúster diluye — MEDIDO).
- **`arrastre`: VALIDADO — código #1 de v1, alta confianza (MEDIDO 2026-07-12).**
  Banco extendido, DeepInfra, temp 0.15, --repetir 3. FN=0 (3/3 positivos marcados y
  estables), FP=0 (2/2 negativos vacíos; la EXCLUSIÓN DURA de `unánime` mordió; color
  deportivo no disparó), grounding 1/1 OK, 0 alucinadas. Def. arrastre = prueba operativa
  (hecho verificable vs tesis en disputa) + exclusión dura (`unánime`-como-hecho) + regla
  de voz (medio ≠ cita) + 3 ejemplos SÍ / 3 NO sacados de texto real. Congelado como
  referencia del mecanismo de probing.
- **`encuadre`: baja-confianza (sin cambio). v4 congelado.** No domesticable por prompt en
  70B (MEDIDO, 3 versiones, error se desplaza sin reducirse). NO encabeza v1 ni dispara el
  termómetro. Reactivar solo con enfoque distinto (clasificador / dos pasadas).
- **`atribucion_difusa`: SIGUIENTE candidato (probe listo, IDs en mano).** Gemelo
  estructural de arrastre: "autoridad/fuente SIN NOMBRE afirma una TESIS discutible" vs
  "fuente reservada reporta un HECHO verificable" (exclusión dura análoga a `unánime`).
  RIESGO medido: el léxico atrapa masivamente sourcing legítimo (fuentes cercanas / expertos
  señalan un hecho); el probe mide si la prueba operativa discrimina. PRECONDICIÓN: el banco
  necesita ≥1 POSITIVO real de weasel (autoridad sin nombre + tesis en disputa, en VOZ DEL
  MEDIO). Si el corpus no tiene uno limpio, ESO es un hallazgo (los medios CO no hacen weasel
  de manual, o el léxico ancla mal), no una falla del prompt.
- **`falsa_dicotomia`: riesgo MEDIO.** Exclusión menos convergente (juzgar si las dos opciones
  son realmente las únicas pide conocimiento del mundo) + FP ya medido (marcaba su opuesto).
  Probe solo si se quiere 3er código.
- **`miedo`: baja-confianza PREDICHA.** "Amenaza desproporcionada" = juicio de proporción
  abierto, no convergente. Diferir hasta enfoque distinto.
- **`titular_enganoso`: FUERA de v1 por estructura.** Es relación titular↔cuerpo (otra clase
  de claim, no patrón intra-texto). Unidad dedicada aparte, no este carril.
- **Omisión:** sin validar (hallazgo estructural, inter-clúster). `resumen_neutral` es de nivel
  CLÚSTER (diag_fase3_prompt.py, rama de provider ROTA), NO del artículo.
- **Presentación:** `condensar.py` PROTOTIPADO (colapso determinista), no integrado a /web.
- **Batch: NO existe.** No se construye hasta cerrar extracción + medir escala.

## MECANISMO DE PROBING por-código (receta REUSABLE — implementación de referencia: arrastre)
>>> Detalle durable en BITACORA (Notas de operación, 2026-07-12). Resumen operativo:
1. **Banco por código:** ≥3 POSITIVOS reales (texto que un medio escribió) + ≥2 NEGATIVOS
   duros (el caso que DEBE quedar vacío: el "hecho literal" que el léxico confunde). Sacados
   del corpus con diag_positivos_superficie.py (coarse ilike + fino regex + flags fuente?/
   en-cita?). Dedup por texto. Etiquetar en banco_fase3.txt: {codigo}_pos / {codigo}_neg.
2. **Prompt (1 variable a la vez):** en el SYSTEM del diag de artículo, reemplazar SOLO el
   bloque de taxonomía por el del código: QUÉ ES + PRUEBA OPERATIVA (tapá el marcador, ¿queda
   hecho o tesis?) + EXCLUSIÓN DURA + REGLA DE VOZ + PROCEDIMIENTO (copiá verbatim ANTES de
   clasificar; vacío permitido; prohibido inventar/parafrasear) + EJEMPLOS SÍ/NO de TEXTO REAL.
   Cambiar también `"codigo"` en el ejemplo del JSON de salida. No tocar los otros códigos.
3. **Umbral ANTES de correr (no se mueve):** pasa si TODOS los positivos se marcan y TODOS los
   negativos quedan vacíos, ESTABLE en las 3 corridas, grounding verbatim OK.
4. **Correr:** `python diag_fase3_articulo.py <uuid> --repetir 3` por cada id del banco.
   Confirmar `Provider: deepinfra` en el print. temp 0.15 (hardcodeada).
5. **Leer:** FN (positivos deben marcar), FP (negativos deben quedar vacíos), grounding.
   Alucinada por borde recortado = FANTASMA (deuda conocida), no invento — no cuenta como FP.
6. **Veredicto:** pasa → código de v1. Falla FN → definición estrecha de más. Falla FP →
   exclusión NO convergente → baja-confianza (como encuadre) o enfoque distinto. Sin punto medio.

## PRÓXIMO PASO cuando retomemos
>>> En este orden. #1 es la unidad elegida:

1. **PROBE de `atribucion_difusa`** con el mecanismo de referencia (arriba). IDs ya en mano.
   Negativos de sourcing legítimo listos: a38be86f (las2orillas, sismo), 940dcc4c (el-tiempo,
   fuente reservada). FALTA confirmar ≥1 POSITIVO weasel limpio en el banco antes de correr.
   Def. propuesta: exclusión dura = "fuente reservada/experticia sobre un HECHO ≠ técnica".
2. **PROBE de `falsa_dicotomia`** (opcional, solo si se quiere 3er código). Riesgo medio.
3. **MEDIR ESCALA (Tier 0, paralelo).** Nº de artículos-en-historia + tokens/corrida; decidir
   unidad del batch (por fila vs por url/último-hash — ojo recapturas en las 5922). Costo NO es
   gate (~$1–2/mes). PROYECCION_ESCALA.md está desactualizada (2026-06-21, 5 medios).
4. **UNIDAD DE PRESENTACIÓN.** condensar.py → /web + termómetro DETERMINISTA + frase-resumen
   groundeada + disclosure del prompt/disclaimer IA. arrastre PUEDE encabezar (alta confianza);
   encuadre NO (baja-confianza). SOLO tras cerrar extracción de v1.
5. **BATCH (Tier 3) SOLO tras 1–4.** Reusa prompt(s) sobrevivientes + validación + grounding;
   agrega failover DeepInfra→NIM (decidido, lógica pendiente), retry-backoff, tolerancia de
   borde de cita, escritura a analyses por (article_id, prompt_version).

## Deudas activas (detalle en BITACORA)
- **[NUEVA 2026-07-12] Predictor de supervivencia CORREGIDO:** no es morfológico-vs-contextual
  (arrastre es contextual y pasó); es "¿exclusión pequeña y convergente?". Supersede la premisa
  de "5 códigos de superficie".
- **[VIGENTE] `encuadre` baja-confianza, v4 congelado** — enfoque distinto, no otra versión.
- **[VIGENTE 2026-07-11] DeepInfra recorta cita → ALUCINADA fantasma** — el batch necesita
  tolerancia de borde. (Esta sesión: 0 alucinadas en arrastre, spans cortos y limpios.)
- **[VIGENTE 2026-07-11] diag_fase3_prompt.py: rama de provider rota** — arreglar ANTES de
  usarlo para resumen_neutral.
- **[VIGENTE 2026-07-11] diag_fase3_articulo.py: veredicto de varianza mide conteo, no grounding.**
- **[SUBIÓ A RUTA 2026-07-12] `tipo` poco fiable entre medios** — dejó de ser inerte: muerde el
  MUESTREO limpio de opinión para el banco (columnas salen como 'noticia', ej. 9a86e897/d42a8e25).
- **[VIGENTE] Omisión sin validar** — posible replanteo inter-clúster.
- **[PENDIENTE] Centroide-por-medio: sesgo direccional** — bloquea activar medios >7.
- **[PENDIENTE] delete-then-insert de story_relations/story_articles** — aceptada.
- Otras menores: writes uno-por-uno, deps sin pin, búsqueda no paginada, lookup URL best-effort.

## Notas de consistencia docs↔código
No editar Arquitectura.md sin que Jota lo decida. §5 lista los 7 códigos en plano con proveedor
NIM viejo. Diferir la edición hasta que la composición de v1 FINALICE (arrastre validado es 1 de
2–3; falta atribucion_difusa). Editar §5 UNA vez con la foto completa. Candidatos acumulados para
esa edición: arrastre = alta-confianza (encabeza); encuadre = baja-confianza; split extracción(LLM)
↔presentación(código); disclosure de prompt como principio; proveedor DeepInfra.

## Ideas registradas (no son scope ahora)
- **`encuadre` por enfoque distinto:** clasificador dedicado, o dos pasadas (léxico valorativo →
  verificación separada de "¿hecho público en disputa atribuible a actor con agencia?").
- **UNIDAD DE PRESENTACIÓN de Fase 3:** vista condensada; termómetro rojo/amarillo/verde
  DETERMINISTA (densidad × severidad, NUNCA color por el LLM); frase-resumen groundeada;
  disclosure del prompt + disclaimer IA — PRINCIPIO.
- **Beta rotulado de un código:** publicar arrastre solo, como BETA visible con disclaimer IA,
  es defendible — PERO es la unidad de presentación + batch, no "diagnosticar en prod sin medir".
  No confundir las dos.
- **Selección de representante como problema de ranking** (no "más largo").
- **Expansión de taxonomía = proyecto calibrado** (SÍ/NO + grounding + FP/FN por código), NO
  cambio de display.
- Upgrade navegabilidad/estética: filtro por medio, ícono ⓘ, hilo rojo SVG, búsqueda paginada.
- La Silla Vacía: filtro sección opinión vs reportería. Vorágine ausente del cross-coverage.

## Cómo verificar el estado
- Cron post-merge en verde (3 jobs). Web Fase 2: /historias y /historia/[id].
- LLM swappable: LLM_PROVIDER=deepinfra|nvidia|groq. Proveedor REAL confirmado por la línea
  `Provider: {PROVIDER} | modelo: {MODEL_ID}` del diag de artículo.
- **`banco_fase3.txt`** = banco de regresión. 6 fijos de encuadre + extensión arrastre:
  · 9a86e897-1f1f-4dd5-aa89-3a4cad223f56  arrastre_pos  las2orillas ("todos sabemos... Abelardo")
  · d42a8e25-b75a-42d1-942a-f348cea2b5ac  arrastre_pos  el-espectador ("todos sabemos... Venezuela")
  · 79ba00e6-ba7b-4d36-bc0f-7e4506e6ffb2  arrastre_pos  las2orillas ("nadie duda... 2030")
  · 61218186-2a8b-4fa1-8ab7-302ddded3655  arrastre_neg  el-tiempo ("votación unánime" = hecho)
  · 7a80cd9a-ed6d-4bd1-a7e8-554e57f98307  arrastre_neg  el-espectador ("es evidente" = deporte)
  No cambiar entre corridas. El v4 es la versión de referencia de `encuadre`.
- FK analyses: confdeltype='n' para analyses_story_id_fkey.