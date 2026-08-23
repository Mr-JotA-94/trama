# TRASPASO — Estado volátil de Trama
> Última actualización: 2026-08-23 (cierre. PR #18 frontend de Fase 3 y PR #19 hora de
> publicación MERGEADOS a main y en producción. Aparecen DOS restricciones nuevas que
> reordenan la cola: presupuesto de GitHub Actions casi agotado, y el análisis de Fase 3
> se desvincula solo entre corridas del clustering.)
> Autoridad: este archivo manda sobre memoria. Estado volátil vive AQUÍ.

## Quién soy y cómo trabajamos
Soy Jota (Johan). Claude es "Claudio". Reglas que NO se pierden:
- **Challenge-first:** cuestiona enfoques con fallas ANTES de construir.
- **Declarar Tier (0–3) + load-bearing antes de construir.**
- Directo, conciso, instructivo, en español. **Medir antes de arreglar.**
- Diagnóstico con datos reales. Claude Code solo para CAMBIOS de código; NO ejecuta DDL.
- **Un chat = UNA unidad de trabajo = un cierre.**
- **Flujo git:** branch antes de tocar código. Commits de doc SEPARADOS de los de código.
  `git status` ANTES de cambiar de rama.
- Los diag_*.py / *.sql son desechables y NO se commitean.
- **Umbral de éxito se fija ANTES de correr — y NO se mueve después de ver el resultado.**
- **Ningún % corona una feature sin LEER material real.**
- **El instrumento de medición también se valida.** REFORZADO con TRES fallas propias en
  dos días: el "95,6% de divergencia" (query sin auditar), el "6/12 sin hora" de El
  Colombiano (regex que exigía `\d{2}` contra un medio sin padding), y el "12/12 con
  timestamp de plantilla" de RTVC (muestreo sin dedup por URL). **Corolario: un número
  que asusta de más suele ser el medidor, no el fenómeno.**
- **PRESENCIA ≠ CORRECCIÓN, y CORRECCIÓN ≠ SOSPECHA.** El `+00:00` de La Silla se veía
  mal y estaba bien (medido); el 18/18 de RTVC se veía bien y podía estar mal. Las dos
  direcciones se miden, ninguna se supone.
- **[2026-08-23] Verificar PRESENCIA no es verificar el MECANISMO.** Claude Code atribuyó
  las huérfanas a un "DELETE+INSERT de toda la tabla stories" que NO existe (el código
  hace UPSERT + poda acotada desde 2026-07-05). El síntoma era real, la causa no, y la
  causa es lo que decide el arreglo. Leer el código antes de aceptar un diagnóstico.
- **Antes de culpar al código, descartar el entorno.**
- **Ver el crudo ANTES de fijar el fix.** MORDIÓ: la deuda "resumenes_dia.dia es TIMESTAMP"
  (registrada dos veces) era FALSA —es `date`— y escondió el corrimiento de día diez días.
- **[2026-08-23] Una fecha sin hora NO tiene zona horaria que convertir.**
- **[2026-08-23] Deuda DERIVADA vs PÉRDIDA PERMANENTE DE ARCHIVO — regla de priorización.**
  Casi toda la deuda de Trama es derivada y regenerable; posponerla es barato. La que toca
  el ARCHIVO no: lo que no se captura hoy no se recupera nunca. **Ante dos deudas de
  impacto parecido, gana la que pierde archivo.** Aplica también al recorte de CI.
- **[2026-08-23] Defensas que fallan en silencio son peores que el bug.** RLS sin policy;
  un parseo que cae al fallback sin loguear. Toda ruta de degradación se REPORTA.
- **[2026-08-09] Trocear por DÍA mata la deriva causal. resumenes_dia es DERIVADO.**
- **[2026-08-09] El clustering NO es incremental: re-particiona todo el corpus.**
- **[2026-08-22] Un smoke/diag verde valida LÓGICA, no INTEGRACIÓN.**
- **[2026-08-22] El árbitro de un fix es el `git diff` contra la versión validada, no el
  reporte del ejecutor.** Presencia ≠ equivalencia.

## Stack
Crawler Python (GitHub Actions cada 6h) → Supabase (Postgres + pgvector) → Next.js 14 en Vercel.
Monorepo Mr-JotA-94/trama (/crawler, /web, /supabase/migrations).
**LLM Fase 3: GLM-5.2 vía OPENROUTER.** Slug `z-ai/glm-5.2`, endpoint
`https://openrouter.ai/api/v1`, key `OPENROUTER_API_KEY`.
- **Payload OBLIGATORIO: `reasoning:{enabled:False}`.**
- **Routing forense: `{"order":["deepinfra","cloudflare","baidu"],"allow_fallbacks":False}`**
- temp 0.15, max_tokens 16000, TIMEOUT_TOTAL 300, PROMPT_VERSION v2.
**ENTORNO PROD = GitHub Actions (Linux x86_64).** LOCAL = Windows ARM64 + Python 3.14.

## Banco: 7 medios. Corpus ~15k artículos / crece ~1000/día.

## ⚠️ RESTRICCIÓN OPERATIVA NUEVA — presupuesto de GitHub Actions
**1.805 de 2.000 minutos consumidos al 2026-08-23. Quedan ~195 para ~8 días de mes.**
- **DECIDIDO (2026-08-23): el repo se hace PÚBLICO.** En repos públicos los minutos de
  Actions son ILIMITADOS, así que esto disuelve la restricción en vez de administrarla.
  Coherente con Arquitectura §0 ("Tier 2, compartible públicamente") y con el principio
  de disclosure del método.
  **CHECKLIST PREVIO AL SWITCH — dos pasos son irreversibles, hacerlos ANTES:**
  1. **Rotar la clave secreta de Supabase y la de OpenRouter ANTES de flipear.** Es lo
     único que hace que un secreto filtrado en el historial nazca muerto. Después no sirve.
  2. **Auditar la HISTORIA de git, no el working tree.** Hacerlo público expone todos los
     commits, no el estado actual: `git log --all --oneline -S "sb_secret_"` (repetir con
     SUPABASE_SERVICE_KEY=, OPENROUTER_API_KEY=, eyJ) y
     `git log --all --pretty=format: --name-only --diff-filter=A | findstr /I ".env"`.
     **Si aparece algo, la salida NO es reescribir la historia:** filter-repo/BFG cambia
     todos los SHA, y la BITACORA CITA SHAs concretos (6e25379, ce4af7f, 26a10eb, b2bbb43)
     como evidencia forense de incidentes. Reescribir destruiría trazabilidad real para
     tapar un valor ya rotado. Rotar y seguir.
  3. **Verificar que nunca se commiteó corpus:**
     `git log --all --pretty=format: --name-only --diff-filter=A | findstr /I "jsonl csv corpus dump"`.
     Un volcado de textos completos en un repo público es REDISTRIBUIR contenido de los
     medios, y choca con la regla legal del proyecto. El código va público; el archivo
     vive en Supabase.
  4. **Asumido a ojos abiertos:** la BITACORA y Arquitectura §4 se vuelven públicas,
     incluida la tabla de posicionamiento editorial por medio ("hipótesis internas, NO
     etiquetas del producto"). Se publica igual —esconder los supuestos sería la opacidad
     que Trama critica— pero es decisión tomada, no descubierta después. Los prompts de
     Fase 3 también quedan expuestos: alineado con la disclosure, riesgo bajo (el gate
     verbatim no es gameable sin dejar de citar literal).
- Si sigue privado, el triaje sale de "archivo antes que derivado":
  · **NO tocar el job `crawl`** — es lo único que protege el archivo (una nota que el feed
    rota y no se capturó no vuelve nunca), y es el job barato.
  · **Recortar el job `backfill`** (torch CPU + spaCy + sentence-transformers instalados en
    cada corrida). Su trabajo es derivado y acumulable: los artículos con `embedding NULL`
    esperan sin perderse. Bajarlo a 1×/día en vez de 4×.
  · **MEDIR primero:** Settings → Billing → Actions usage da minutos por workflow. No
    adivinar cuál es el goloso.
- **CONSECUENCIA: enganchar Fase 3 al cron consume minutos que hoy no existen.** Ese plan
  queda BLOQUEADO detrás de esta decisión.

## DÓNDE ESTAMOS

**Fase 1 COMPLETA. Fase 2 EN PRODUCCIÓN + Louvain beat-split.**

**Fase 3 — pipeline EN PRODUCCIÓN. Disparo MANUAL (no está en el cron).**
Bucle operativo: crawler y clustering corren solos cada 6h; Fase 3 se dispara a mano en
Actions → `fase3_backfill.yml` → Run workflow (horas=72). La web lee `resumenes_dia` con
`revalidate=300`: ~5 min después se ve.

**FRONTEND DE FASE 3 — MERGEADO (PR #18) Y EN PRODUCCIÓN.** Verificado en vivo en
trama-co.vercel.app: síntesis del día bajo el título, "Lo que reportaron los medios"
(corroborado verde / un-solo-medio ámbar), chips "Análisis por día", modal `<dialog>` por
día. Los placeholders de "Análisis de persuasión" y "Reacciones" están retirados.
Los 7 puntos del gate cerraron, incluido el fix de mayúsculas heredadas por el `<dialog>`
y el detalle de móvil.

**HORA DE PUBLICACIÓN — MERGEADA (PR #19) Y EN PRODUCCIÓN.** `crawler.py` ahora resuelve
la fecha por cadena ordenada: JSON-LD `datePublished` → `<meta article:published_time>` →
piso de trafilatura (solo fecha), con la procedencia contada e impresa al cierre de cada
corrida. Gate de 6 puntos, 6/6. Confirmado en base: filas nuevas con hora real
(20:01:56, 21:38:53, 23:15:43 UTC) conviviendo con las viejas en 00:00:00.
**NO recuperó el pasado y no podía:** los ~15k artículos previos quedan sin hora para
siempre. De acá en adelante sí la hay.
**NO "corregir" el `+00:00` de La Silla Vacía:** verificado como UTC real (Δ=0,00 h en
10/10 contra el `<pubDate>` de su RSS).

**⚠️ EL ANÁLISIS SE DESVINCULA SOLO ENTRE CORRIDAS — hallazgo del 2026-08-23.**
Muchas historias muestran la página en blanco pese a tener análisis hecho. **28 filas
huérfanas** (`story_id IS NULL`) contra 9 el día anterior.
- **Mecanismo REAL (verificado en el código, no el que reportó Claude Code):** `stories`
  usa UPSERT + poda ACOTADA de huérfanas. Una historia que conserva su `uuid_estable` NO
  se borra. Lo que dispara el SET NULL es la **migración del uuid**: un clúster que crece
  e incorpora una nota MÁS ANTIGUA cambia su artículo semilla → uuid5 nuevo → el sid viejo
  sale de `sids_actuales` → lo barre la poda. Es el "residual aceptado" del 2026-06-21.
- **La adopción por `dia_key` NO rescata el caso que importa.** Adopta solo si la
  composición del día es IDÉNTICA. Un clúster que pasó de 8 a 47 artículos cambió la
  composición de sus días → dia_key nuevo → esas filas no se adoptan nunca: se REGENERAN
  pagando LLM de nuevo, y las viejas quedan huérfanas permanentes.
- Correr el backfill hoy es COSMÉTICO: arregla la foto y se vuelve a vaciar en la próxima
  corrida del clustering que haga migrar un sid.

**ESQUEMA:**
- comparaciones: hash_a/b, sin story_id. RLS activo, SIN policy pública (a propósito: su
  deuda de auditoría sigue abierta, no se expone material no leído).
- resumenes: HUÉRFANA, a DROPear.
- resumenes_dia: `dia` es **DATE** (la deuda que decía TIMESTAMP era falsa, RETIRADA).
  dia_key UNIQUE, story_id FK ON DELETE SET NULL nullable. article_ids `uuid[]`,
  member_hashes/medios `text[]`, hechos_corroborados/solo_un_medio `jsonb`.
  RLS con policy `lectura_publica` (migración 000019).
- story_relations + tipo ('tematica'|'misma_trama').

## PRÓXIMO PASO cuando retomemos
1. **[BLOQUEANTE, días] Hacer el repo público** siguiendo el checklist de arriba —rotar
   claves y auditar la historia ANTES del switch—. Disuelve el presupuesto de Actions,
   que es lo único acá que puede apagar el crawler y causar pérdida de archivo
   irreversible. Si por lo que sea el switch se demora, el plan B es recortar el job
   `backfill` (derivado, acumulable), nunca el `crawl`.
2. **[Frontend, cero minutos de CI] Rediseño de la línea de tiempo por día.** Ver Ideas
   en BITACORA. Se puede hacer entero con el presupuesto de CI seco, y elimina la
   redundancia chips↔separadores. **Orden obligatorio: primero agrupar la línea de tiempo
   por día de PUBLICACIÓN, después borrar los chips.** Al revés se cambia redundancia
   visible por pérdida silenciosa.
3. **Enganche de Fase 3 al cron** — es el arreglo real del desvinculado. BLOQUEADO por (1).
4. **Backfill HISTÓRICO (Objetivo B):** ~750 historias inactivas, ~$25-35. También
   consume CI: va después de (1).
5. Renombrar `RSL_policy_resumenes_dia.sql` → `rls_...` ("RSL" es typo, falla el grep).
   Sigue sin trackear en main.
6. DROP tabla `resumenes`. Limpieza de huérfanas permanentes viejas.

## Cómo verificar (queries y comandos vigentes)
- **Ver avance de Fase 3 en la web:** Actions → `fase3_backfill.yml` → Run workflow
  (horas=72) → recargar a los ~5 min. OJO: consume minutos de CI.
- **Minutos de Actions:** Settings → Billing → Actions usage (por workflow).
- **RLS de una tabla nueva** (al CREARLA, no al consumirla):
  `select c.relname, c.relrowsecurity, p.polname from pg_class c
   left join pg_policy p on p.polrelid=c.oid where c.relname='X';`
- **Huérfanas:** `select count(*) from resumenes_dia where story_id is null;`
- **Procedencia de fechas nuevas:** el log de cada corrida del crawler imprime
  `fecha_publicacion por fuente: {...}`. Si `trafilatura-solo-fecha` deja de ser marginal,
  un medio cambió su HTML: es regresión, no ruido.
- Distinguir transitorio vs determinista de proveedor: re-correr (idempotencia).
