# TRASPASO — Estado volátil de Trama
> Última actualización: 2026-08-26 (cierre. Repo PÚBLICO con claves rotadas. Módulo
> `revincular_huerfanas.py` en producción como 4º job del pipeline. Fase 3 enganchada al
> cron como 5º job, 1×/día. Se REFUTA con datos la premisa de que "el cron de Fase 3 es el
> arreglo del desvinculado". Aparece una restricción nueva con reloj: el free tier de
> Supabase.)
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
- **[2026-08-26] WebFetch CONFIRMA PRESENCIA, NUNCA AUSENCIA.** Pasa el archivo por un
  modelo pequeño que resume: preguntado "¿existe el job revincular?" contestó "no existe"
  sobre un `crawler.yml` que sí lo tenía. Un "no está" de esa herramienta NO es evidencia.
  Para verificar ausencia: leer local, o pedir transcripción literal y desconfiar.
- **PRESENCIA ≠ CORRECCIÓN, y CORRECCIÓN ≠ SOSPECHA.** El `+00:00` de La Silla se veía
  mal y estaba bien (medido); el 18/18 de RTVC se veía bien y podía estar mal. Las dos
  direcciones se miden, ninguna se supone. **[2026-08-26] MORDIÓ AL REVÉS:** la presencia
  de `astimezone(BOGOTA)` en el grep se leyó como bug vivo. Era la rama `else` del guard
  que `26a10eb` ya había agregado. Presencia de una línea ≠ ejecución de esa línea.
- **[2026-08-23] Verificar PRESENCIA no es verificar el MECANISMO.** CORREGIDO EL
  2026-08-26: Claude Code había reportado un "DELETE+INSERT de toda la tabla". Para
  `stories` era falso (poda acotada). Pero `story_articles` SÍ se borra entera cada
  corrida. Acertó el mecanismo, erró la tabla.
- **Antes de culpar al código, descartar el entorno.**
- **Ver el crudo ANTES de fijar el fix.**
- **[2026-08-23] Una fecha sin hora NO tiene zona horaria que convertir.**
- **[2026-08-23] Deuda DERIVADA vs PÉRDIDA PERMANENTE DE ARCHIVO — regla de priorización.**
  Casi toda la deuda de Trama es derivada y regenerable; posponerla es barato. La que toca
  el ARCHIVO no: lo que no se captura hoy no se recupera nunca. **Ante dos deudas de
  impacto parecido, gana la que pierde archivo.**
- **[2026-08-23] Defensas que fallan en silencio son peores que el bug.** Toda ruta de
  degradación se REPORTA.
- **[2026-08-26] Un guard que compara contra una FOTO del estado no protege contra lo que
  el propio lote está escribiendo.** `dias_ocupados` se leía una vez al inicio: dos
  huérfanas del mismo (story_id, dia) pasaban ambas y creaban el duplicado que el guard
  existía para evitar. Se predijo y no se arregló antes de correr; mordió.
- **[2026-08-26] Asimetría de tests: un experimento benigno que YA duele concluye; uno que
  no duele NO concluye.** Se declara la asimetría ANTES de correr, junto con el umbral.
- **[2026-08-26] El campo `modelo` de las filas derivadas es marca temporal forense.**
  `zai-org/GLM-5.2` = pre-OpenRouter; `z-ai/glm-5.2` = post 2026-08-22. No se diseñó para
  eso y resolvió un duplicado sin necesidad de hipótesis.
- **[2026-08-09] Trocear por DÍA mata la deriva causal. resumenes_dia es DERIVADO.**
- **[2026-08-09] El clustering NO es incremental: re-particiona todo el corpus.**
- **[2026-08-22] Un smoke/diag verde valida LÓGICA, no INTEGRACIÓN.**
- **[2026-08-22] El árbitro de un fix es el `git diff` contra la versión validada, no el
  reporte del ejecutor.** Presencia ≠ equivalencia.

## Stack
Crawler Python (GitHub Actions cada 6h) → Supabase (Postgres + pgvector) → Next.js 14 en Vercel.
Monorepo Mr-JotA-94/trama (/crawler, /web, /supabase/migrations). **REPO PÚBLICO desde
2026-08-26**: minutos de Actions ilimitados.
**LLM Fase 3: GLM-5.2 vía OPENROUTER.** Slug `z-ai/glm-5.2`, endpoint
`https://openrouter.ai/api/v1`, key `OPENROUTER_API_KEY`.
- **Payload OBLIGATORIO: `reasoning:{enabled:False}`.**
- **Routing forense: `{"order":["deepinfra","cloudflare","baidu"],"allow_fallbacks":False}`**
- temp 0.15, max_tokens 16000, TIMEOUT_TOTAL 300, PROMPT_VERSION v2.
**ENTORNO PROD = GitHub Actions (Linux x86_64).** LOCAL = Windows ARM64 + Python 3.14.

## Banco: 7 medios. Corpus ~15k artículos / crece ~1000/día.

## ⚠️ RESTRICCIÓN NUEVA CON RELOJ — free tier de Supabase
**Supabase Free = 500 MB de base. Pro = $25/mes (8 GB).**
El corpus crece ~1000 artículos/día. Con `contenido_visible` (~4 KB) + embedding de 384
dims (~1,5 KB) + índices, del orden de **~7 MB/día ≈ 210 MB/mes**. **ESTIMADO, NO MEDIDO:
la primera acción de la próxima sesión es medirlo.**
- **Por qué es de la categoría grave:** si la base se llena, el proyecto DEJA DE ESCRIBIR.
  Eso es pérdida permanente de archivo, no deuda derivada.
- **A diferencia del presupuesto de Actions, esta NO se disuelve.** Un archivo inmutable
  que crece 1000 notas/día no cabe en 500 MB de forma indefinida, y podar es exactamente
  lo que el proyecto prohíbe. **La premisa "stack gratis" tiene fecha de vencimiento por
  diseño.** Se asume a ojos abiertos, como el repo público — no se descubre el día que
  falle una escritura.
- **Estimación gruesa: 6–8 semanas (≈ octubre 2026).** Sustituir por el dato real.

## PROYECCIÓN DE GASTO MENSUAL (2026-08-26)
| concepto | hoy | en régimen |
|---|---|---|
| GitHub Actions | $0 | **$0** — repo público, ilimitado |
| Vercel Hobby | $0 | $0 |
| LLM Fase 3 (cron 1×/día) | $0 | **$28–45/mes** |
| Supabase | $0 | **$25/mes** al pasar 500 MB |
| Backfill histórico (~750 historias) | — | $25–35, **una sola vez** |

**Régimen ~$53–70/mes.** Base del cálculo LLM: $0,062/día denso medido (2026-08-22) ×
~24 días/día calendario (derivado de los 85 días que guardó la corrida del 26 tras ~3–4
días sin dispararse). **El $45 es techo, no centro**: esos 85 se acumularon SIN
`revincular` corriendo. El número exacto llega solo con 7 días de `dia_guardados` del job
nuevo. El costo de Supabase es ESTRUCTURAL (el archivo crece); el del LLM es OPCIONAL y
regulable (bajar Fase 3 a cada 2 días lo parte al medio, a costa de frescura).

## DÓNDE ESTAMOS

**Fase 1 COMPLETA. Fase 2 EN PRODUCCIÓN + Louvain beat-split (`seed=42`, determinista).**

**PIPELINE DE CINCO JOBS en `crawler.yml`, encadenados por `needs`:**
`crawl → backfill → clustering → revincular → fase3`
- Los cuatro primeros corren en las 4 vueltas diarias (00, 06, 12, 18 UTC).
- **`fase3` corre SOLO en la vuelta de las 06:00 UTC** (01:00 CO), vía
  `if: github.event.schedule == '0 6 * * *' || inputs.correr_fase3`.
- **El cron está PARTIDO EN DOS entradas a propósito** (`"0 0,12,18 * * *"` y `"0 6 * * *"`):
  `github.event.schedule` devuelve el string del cron que disparó, y con el cron unificado
  las cuatro vueltas eran indistinguibles.
- **⚠️ MODO DE FALLA SILENCIOSO:** el `if` compara el string carácter por carácter. Si se
  edita el cron y no la condición, `fase3` deja de correr sin error ni log. **Verificación
  visual: la corrida de las 06:00 UTC debe mostrar CINCO jobs; las otras tres, cuatro.**
- Corridas manuales: el input `correr_fase3` viene en `false`. Disparar el crawler a mano
  NO gasta LLM salvo que se marque.

**RE-VINCULACIÓN DE HUÉRFANAS — EN PRODUCCIÓN (`crawler/revincular_huerfanas.py`).**
Repara filas de `resumenes_dia` con `story_id NULL` re-apuntándolas por PERTENENCIA de sus
artículos (sobrevive al cambio de composición, cosa que la adopción por `dia_key` no hace).
- **Criterio: CONTENCIÓN TOTAL, no mayoría.** La story candidata debe contener TODOS los
  artículos del día. Si el día se repartió entre clústeres, ese análisis ya no describe a
  ninguno y colgárselo al mayoritario contaminaría el expediente con material de otra
  historia. Las descartadas se cuentan y se imprimen; nunca en silencio.
- **`needs: revincular` en `fase3` es ECONÓMICO, no cosmético:** medido el 26/08,
  revincular recuperó 12 días ya pagados que Fase 3 habría regenerado (~$0,74/vuelta).

**⚠️ SE REFUTA: "el enganche de Fase 3 al cron es el arreglo real del desvinculado."**
Era la premisa vigente hasta el 26/08 y es FALSA. El arreglo es `revincular`. El cron de
Fase 3 es **conveniencia operativa acotada** (que los días nuevos se analicen sin apretar
el botón), y se paga en dólares recurrentes.

**⚠️ HALLAZGO ABIERTO — FRAGMENTACIÓN PROGRESIVA DE LOS DÍAS.**
Con **una hora** de material nuevo, las huérfanas pasaron de 14 a 30 en una sola vuelta.
Y los repartos escalaron: días "repartidos entre 3 clústeres" y "entre 4", que el día
anterior no existían (todos eran "entre 2"). Con `seed=42` fijo **no es aleatoriedad del
algoritmo**: es el corpus creciente reorganizando clústeres, y cada reorganización parte
un día ya partido. **Si el reparto entre 3–4 se vuelve la norma, la ventana-día deja de ser
una unidad de análisis estable, y eso toca el DISEÑO de Fase 3, no su calendario.**
No medido en el tiempo todavía: hacen falta varios días de logs de `revincular`.

**FRONTEND DE FASE 3 — MERGEADO (PR #18) Y EN PRODUCCIÓN.** Síntesis del día bajo el
título, "Lo que reportaron los medios" (corroborado / un-solo-medio), chips "Análisis por
día", modal `<dialog>` por día. Placeholders de "Análisis de persuasión" y "Reacciones"
retirados.

**HORA DE PUBLICACIÓN — MERGEADA (PR #19) Y EN PRODUCCIÓN.** Cadena ordenada: JSON-LD
`datePublished` → `<meta article:published_time>` → piso de trafilatura (solo fecha), con
procedencia contada e impresa al cierre de cada corrida.
**NO recuperó el pasado y no podía:** los ~15k artículos previos quedan sin hora para
siempre. **`_dia_bogota()` YA maneja ese caso** (guard de `26a10eb`: medianoche UTC exacta
se devuelve sin convertir). Verificado el 26/08: **0 de 198 filas con el día corrido.**
**NO "corregir" el `+00:00` de La Silla Vacía:** verificado como UTC real.

**ESQUEMA:**
- comparaciones: hash_a/b, sin story_id. RLS activo, SIN policy pública (a propósito).
- resumenes: HUÉRFANA, a DROPear.
- resumenes_dia: `dia` es **DATE**. dia_key UNIQUE, story_id FK ON DELETE SET NULL
  nullable. article_ids `uuid[]`, member_hashes/medios `text[]`,
  hechos_corroborados/solo_un_medio `jsonb`. RLS con policy `lectura_publica` (mig. 000019).
- story_relations + tipo ('tematica'|'misma_trama').

## PRÓXIMO PASO cuando retomemos
1. **[5 minutos, hacer PRIMERO] Medir el tamaño de la base.** Define si el reloj de
   Supabase marca 6 semanas o 2, y eso puede reordenar todo lo demás. Queries abajo.
2. **[Frontend, cero costo] Rediseño de la línea de tiempo por día.** Ver Ideas en
   BITACORA. **Orden obligatorio: primero agrupar la línea de tiempo por día de
   PUBLICACIÓN, después borrar los chips.** Al revés se cambia redundancia visible por
   pérdida silenciosa. Es lo único de la cola que no depende de esperar datos.
3. **[Esperar 7 días, llega solo] Costo real del cron de Fase 3.** Acumular
   `dia_guardados` del job `fase3`. Con ese número se decide si sube de 1×/día a más
   vueltas — CON el dato, no con la proyección.
4. **[Medir varios días] Fragmentación progresiva de los días.** Seguir el conteo de
   `repartida` y el número de clústeres por reparto en los logs de `revincular`.
5. **Backfill HISTÓRICO (Objetivo B):** ~750 historias inactivas, ~$25-35. Ya no bloqueado
   por CI; ahora es decisión de presupuesto.
6. Renombrar `RSL_policy_resumenes_dia.sql` → `rls_...` ("RSL" es typo, falla el grep).
7. DROP tabla `resumenes`. Limpieza de huérfanas permanentes viejas.

## Cómo verificar (queries y comandos vigentes)
- **Tamaño de la base (restricción con reloj):**
  ```sql
  select pg_size_pretty(pg_database_size(current_database())) as base_total;
  select relname, pg_size_pretty(pg_total_relation_size(c.oid)) as tamano
  from pg_class c join pg_namespace n on n.oid = c.relnamespace
  where n.nspname = 'public' and c.relkind = 'r'
  order by pg_total_relation_size(c.oid) desc limit 8;
  ```
- **Huérfanas y su clasificación:** el log del job `revincular` en CADA corrida
  (`revinculable / colision_lote / superada / repartida / sin_story`). Query cruda:
  `select count(*) from resumenes_dia where story_id is null;`
- **Duplicados de día** (no deberían existir; el retiro post-insert los previene):
  ```sql
  select story_id, dia, count(*) from resumenes_dia
  where story_id is not null group by story_id, dia having count(*) > 1;
  ```
- **Costo del cron de Fase 3:** cierre del log del job `fase3` → `N días guardados`.
  Multiplicar por ~$0,062.
- **Que `fase3` sigue enganchado:** Actions → la corrida de las 06:00 UTC debe mostrar
  CINCO jobs. Cuatro = el `if` se desincronizó del cron.
- **RLS de una tabla nueva** (al CREARLA, no al consumirla):
  `select c.relname, c.relrowsecurity, p.polname from pg_class c
   left join pg_policy p on p.polrelid=c.oid where c.relname='X';`
- **Procedencia de fechas nuevas:** el log del crawler imprime `fecha_publicacion por
  fuente: {...}`. Si `trafilatura-solo-fecha` deja de ser marginal, un medio cambió su
  HTML: es regresión, no ruido.
- **Cron de GitHub:** se deshabilita solo tras 60 días sin actividad en el repo, avisando
  solo por mail. Si el crawler deja de correr sin explicación, revisar eso primero.
- Distinguir transitorio vs determinista de proveedor: re-correr (idempotencia).
