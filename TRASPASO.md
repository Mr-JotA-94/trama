# TRAMA — Estado del proyecto (traspaso a nueva sesión)

> Dáselo a un chat nuevo para retomar sin releer conversaciones. Léelo junto con
> ARQUITECTURA.md (plan completo) y BITACORA.md (decisiones y deuda).
> Última actualización: **2026-07-05** (cierre: fix filtro NER RTVC + constraint analyses + upsert clustering).


## Quién soy y cómo trabajamos
Soy Jota (Johan). Claude es "Claudio". Reglas que NO se pierden:
- **Challenge-first:** cuestiona enfoques con fallas ANTES de construir. Honestidad
  sobre complacencia.
- **Declarar Tier (0–3) + load-bearing antes de construir.**
- Directo, conciso, instructivo, en español. **Medir antes de arreglar.**
- Diagnóstico con datos reales; si Claudio no puede verificar en su entorno, me da
  script para correr aquí. Para diagnósticos read-only puedo exportar un snapshot
  estático (CSV/JSON) y Claudio lo corre/itera de su lado. Claude Code es solo para
  CAMBIOS de código en repo.
- **Disciplina de sesión:** un chat = UNA unidad de trabajo = un cierre.
- App para pensar/decidir (genera el prompt) → Claude Code para tocar archivos →
  de vuelta a la app el RESUMEN. Cambios de una sola función, a mano sin Claude Code.
- **Flujo git:** branch ANTES de tocar código. Pull al EMPEZAR cada unidad.
  Commits de documentación SEPARADOS de los de código. El `git diff` contra el
  commit validado es autoritativo, no el auto-reporte de la herramienta.
- **Los scripts (backfill/clustering/diag) escriben a Supabase o son read-only, NO al
  repo.** Los diag_*.py son desechables y no se commitean.

## Qué es Trama (una frase)
Hemeroteca forense de medios colombianos: archiva el contenido públicamente visible
con hash SHA-256 y marca de tiempo, para rastrear cómo un mismo hecho se cubre
distinto entre medios (Fase 2) y señalar técnicas de persuasión (Fase 3). Público:
periodistas, verificadores, ciudadanos activos.

## Stack (todo gratis)
- **Crawler:** Python (httpx + trafilatura + articleBody JSON-LD), GitHub Actions 6h.
- **BD:** Supabase (Postgres + pgvector), São Paulo. Claves sb_secret_ (crawler) /
  sb_publishable_ (web, var NEXT_PUBLIC_SUPABASE_KEY). RLS = solo lectura pública.
  **Lecturas capadas a ~1000 filas: paginar con .range(desde, desde+999) en bucle.**
- **Web:** Next.js 14 (App Router, Server Components, JS/JSX — NO TypeScript),
  Vercel → trama-co.vercel.app. CSS global en globals.css (tokens en :root:
  --tinta/--papel/--hilo/--resaltador/--verificado/--gris-archivo, fuentes --f-mono/--f-ui).
  Caché: feed revalidate 300s, artículos 3600s. /historias es dinámico por request.
- **Repo:** GitHub Mr-JotA-94/trama (privado, monorepo). /crawler, /web, /supabase/migrations.
- **Migraciones:** van 13. Última: 20260705000013_analyses_story_id_set_null.
- **CI:** workflow `crawler.yml` con TRES jobs encadenados: crawl (6h) → backfill
  (needs:crawl) → clustering (needs:backfill).

## DÓNDE ESTAMOS — 2026-07-05

**Fase 1 COMPLETA y desplegada.** Crawler, web pública.

**Fase 2 EN PRODUCCIÓN.** Vista + clustering + feed paginado + grafo de historias
conectadas expuesto. trama-co.vercel.app/historias y /historia/[id]. Pipeline
automatizado (tres jobs CI en cadena), archivando cada 6h.

**7 MEDIOS ACTIVOS:** El Espectador, El Tiempo, El Colombiano, Las2orillas, Vorágine,
La Silla Vacía (6º, verificado 2026-06-29), **RTVC (7º, activado en código
2026-06-30 vía cef1d3b; sitemap-news.xml, extracción trafilatura, color slate-blue
#455a75).**

**FILTRO NER DE RTVC CORREGIDO — EN MAIN (2026-07-05, esta sesión).** Las 3 entradas
de RTVC en `MEDIOS` (ner_filtro.py) estaban en mayúscula y nunca matcheaban la
comparación `t.lower()`: el filtro anti-autorreferencia era código muerto. Fix
defensivo: el set se auto-normaliza en su definición (`{m.lower() for m in {...}}`),
lo que elimina la clase de bug para cualquier medio futuro. Rama
`fix/medios-case-insensitive`, mergeada. Verificado por git diff (11 literales
intactos) y dry-run (todas las variantes de casing rechazadas).

**CONSTRAINT analyses.story_id + UPSERT DE CLUSTERING — EN MAIN (2026-07-05, esta
sesión).** Prerequisito silencioso de Fase 3. Hallazgo: `analyses.story_id` NO tenía
FK (se perdió en el `drop table stories cascade` de la migración 000008 y nadie lo
recreó) — peor que la landmine RESTRICT original, porque una story borrada dejaba
story_id apuntando a un id inexistente sin error. Fix (migración 000013, aplicada en
Supabase y verificada `confdeltype='n'`): FK con `ON DELETE SET NULL` (no CASCADE,
para no borrar los analyses caros de Fase 3 en cada recompute). Código:
`reescribir_stories` ya no borra stories entera → UPSERT on_conflict=id (preserva la
identidad uuid5 estable) + poda acotada de huérfanas (existentes − sids_actuales) +
lectura de existentes paginada a ~1000. Rama `fix/clustering-upsert-analyses-setnull`,
mergeada (3 commits: migración, upsert+poda, paginación). Validado con dry-run que
reproduce el tope de 1000 filas (1500 stories → 2 páginas + vacía, 1500 podadas).

**Banco:** ~2700+ artículos embebidos (entidades limpias). Conteo exacto de stories =
última corrida verde del cron.

**ÁTOMO = URL, UUID ESTABLE, ANCLA, FEED↔TÍTULO-CITA, FEED PAGINADO, NER LIMPIO** — vigente.

## PRÓXIMO PASO cuando retomemos

>>> Fase 2 sin pendientes de código. Dos unidades cerradas esta sesión destraban Fase 3.

1. **RTVC — validación EN VIVO (Tier 0, la unidad más chica que sigue).** RTVC está
   activado en código y con el filtro NER ya corregido, pero NADIE ha confirmado con
   datos que el cron ingirió notas limpias. Correr la misma query read-only que se
   usó para La Silla Vacía (BITACORA 2026-06-29) sobre `outlets.slug='rtvc'`:
   `extraccion`, `es_parcial`, boilerplate residual, conteo de entidades (confirmar
   que "rtvc"/"señal colombia" ya NO aparecen tras el fix). Cierra el "banco de 7
   medios" que gate Fase 3.

2. **Fase 3 (LLM: NVIDIA NIM / meta/llama-3.3-70b-instruct / Groq fallback).** Tras
   validar RTVC. El esquema de `analyses` ya quedó listo esta sesión (FK SET NULL).
   Falta TODO el código: cliente HTTP swappable (base_url/api_key/model_id desde
   .env), prompts de la taxonomía de técnicas, validación JSON + retry, batch sobre
   clústeres de ≥3 medios. NOTA: `llama-3.3-70b-versatile` (el modelo del fallback
   Groq documentado) se decomisiona el 2026-08-16; el modelo primario en NIM
   (`meta/llama-3.3-70b-instruct`) es de otro catálogo y no se ve afectado, pero el
   fallback de Groq necesita modelo de reemplazo TBD antes de esa fecha.

3. **CLAUDE.md — commit pendiente.** Redactado esta sesión (contrato operativo +
   capa operativa). Falta guardarlo en la raíz del repo y commitearlo aparte (`docs:`).

## Deudas activas (detalle en BITACORA)

- **[RESUELTO 2026-07-05] Filtro NER de RTVC = código muerto** — case-sensitivity en
  MEDIOS. Fix defensivo auto-normalizador, en main.
- **[RESUELTO 2026-07-05] analyses.story_id sin FK (landmine de Fase 3)** — FK con ON
  DELETE SET NULL (migración 000013), en main y aplicada en Supabase.
- **[PARCIALMENTE RETIRADA 2026-07-05] delete-then-insert no transaccional del
  clustering** — `stories` ya no se borra-y-reinserta (ahora UPSERT); pero
  `story_relations`/`story_articles` SIGUEN con delete-total-then-insert cada corrida.
  Esa parte de la deuda queda vigente (sin FK externo, aceptada).
- **[NUEVA] Groq fallback de Fase 3 sin modelo de reemplazo** — `llama-3.3-70b-versatile`
  se decomisiona 2026-08-16. Decidir reemplazo antes de esa fecha o al empezar Fase 3,
  lo que llegue primero. Requiere validación independiente (JSON estricto en español,
  temperatura baja, sobre artículos reales) antes de adoptar.
- **[PENDIENTE] Centroide-por-medio: diagnóstico de sesgo aún abierto** — un-voto-por-medio
  mide sesgo direccional confirmado; bloquea activar medios más allá de los 7 actuales
  hasta re-medir. (El SPLIT de scores ya está implementado y en main desde 2026-06-29.)
- **[PENDIENTE] Re-medir PROYECCION_ESCALA.md** — su propio disparador ("re-medir al
  activar un medio") está incumplido: se activaron La Silla Vacía y RTVC y la medición
  sigue fechada 2026-06-21 (1645 art., proyección a 5 medios). No urgente (~3% del free
  tier), pero pendiente. Esperar unos días de datos con los 2 medios nuevos.
- **[NUEVA] Varianza de ancla en clústeres pequeños bajo un-voto** (2026-06-28) — ~5
  clústeres de 3-4 art. pierden cobertura de ancla. Aceptado. Disparador: medir guarda
  de tamaño N si molesta.
- **Canonizar exclusión de `es_especifica` — mejora SIN MEDIR** (2026-06-28) —
  reintroducir solo con medición.
- **Air-e = falso negativo MEDIDO de relaciones** (2026-06-27) — FN aceptado.
- **Retirar RUIDO_DURO BLOQUEADO** (2026-06-27) — disparador: mejor filtro de NER de cuerpo.
- **Writes masivos uno-por-uno frágiles** (2026-06-26) — corte medido a ~800 writes.
- **Dependencias de clustering/backfill sin pin** (2026-06-23).
- **Búsqueda no paginada** (2026-06-21). **Doble-cómputo de título** (2026-06-21).
- **Lookup por URL best-effort** — falla silencioso con variantes AMP/m./canónicas.

## Notas de consistencia docs↔código

Dos discrepancias STALE previas (Arquitectura.md §6 "grafo no expuesto"; BITACORA
"clustering no está en el workflow") siguen sin bloquear trabajo — no editar
Arquitectura.md sin que Jota lo decida. NUEVA nota: la migración 000013 CREA el FK de
analyses.story_id por primera vez (no lo altera), porque el histórico lo dejó sin FK.

## Ideas registradas (no son scope ahora)

- **Upgrade de navegabilidad/estética (post-estructura, propuesta 2026-07-02):** filtro
  por medio en /historias (esfuerzo bajo, mismo patrón que ControlOrden/PresetsFecha;
  impacto alto con 7 medios), ícono "ⓘ" con `<details>` nativo (destraba explicar los
  scores de Fase 3 sin romper cero-JS), hilo rojo curvo SVG (identidad visual, bajo
  impacto funcional), búsqueda paginada. Ninguno rompe el sistema de diseño cerrado.
  Es unidad(es) aparte, POST estructura principal.
- Texto de servicio idéntico entre notas (footer RCF, disclaimer opinión) — vigilancia,
  no acción; contenido legítimo bajo el gate n_especificas≥3.
- La Silla Vacía: filtro de sección opinión vs reportería (red-de-expertos).
- Vorágine ausente del diagnóstico cross-coverage del centroide — a medir aparte.
- Segundo "ver menos" al final del hilo — se difiere por cero-JS.

## Fase 2 NO obliga a reconstruir al agregar medios
El clustering opera sobre artículos. Agregar medio = config en outlets; solo se
recalibran umbrales. Al activar un medio nuevo: agregar su nombre a MEDIOS en
ner_filtro.py (el set ya se auto-normaliza; cualquier capitalización sirve).

LLM de Fase 3 DECIDIDO (2026-06-19): NVIDIA NIM hosted, meta/llama-3.3-70b-instruct,
cliente swappable, Groq fallback (modelo de reemplazo TBD, ver deudas).

## Cómo verificar el estado
- Cron post-merge en verde (los tres jobs).
- Web Fase 2: trama-co.vercel.app/historias y /historia/[id] (grafo visible).
- RTVC en vivo (PENDIENTE): query read-only sobre outlets.slug='rtvc'.
- Constraint viva: `select conname, confdeltype from pg_constraint where
  conrelid='analyses'::regclass and contype='f';` → analyses_story_id_fkey debe dar 'n'.
- UUID estable: clustering 2× sin cambiar datos → misma huella; ahora además las
  stories estables NO se recrean (upsert), su id se conserva entre corridas.
