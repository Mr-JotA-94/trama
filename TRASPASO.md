# TRAMA — Estado del proyecto (traspaso a nueva sesión)

> Dáselo a un chat nuevo para retomar sin releer conversaciones. Léelo junto con
> ARQUITECTURA.md (plan completo) y BITACORA.md (decisiones y deuda).
> Última actualización: **2026-06-21**.

## Quién soy y cómo trabajamos
Soy Jota (Johan). Claude es "Claudio". Reglas que NO se pierden:
- **Challenge-first:** cuestiona enfoques con fallas ANTES de construir. Honestidad
  sobre complacencia.
- **Declarar Tier (0–3) + load-bearing antes de construir.**
- Directo, conciso, instructivo, en español. **Medir antes de arreglar.**
- Diagnóstico con datos reales; si Claudio no puede verificar en su entorno, me da
  script para correr aquí.
- **Disciplina de sesión:** un chat = UNA unidad de trabajo = un cierre. Cerrar en
  límites lógicos, no cuando se llene la ventana. El TRASPASO al día es lo que hace
  barato el arranque del siguiente chat.
- App para pensar/decidir (genera el prompt) → Claude Code para tocar archivos →
  de vuelta a la app el RESUMEN (no la sesión entera) para revisar. Cambios de una
  sola función pueden hacerse a mano sin Claude Code.
- **Flujo git:** branch ANTES de tocar código. Un branch por unidad de trabajo.
  Cambio → npm run dev → commit dentro del branch → push → PR → validar en deploy
  preview de Vercel → merge → borrar branch. DevTools (375/560px) basta para móvil.
- **Los scripts (backfill/clustering) escriben a Supabase, NO al repo.** No hay git
  push tras correrlos; la data ya está en la base. Solo el código va por git.

## Qué es Trama (una frase)
Hemeroteca forense de medios colombianos: archiva el contenido públicamente visible
con hash SHA-256 y marca de tiempo, para rastrear cómo un mismo hecho se cubre
distinto entre medios (Fase 2) y señalar técnicas de persuasión (Fase 3). Público:
periodistas, verificadores, ciudadanos activos.

## Stack (todo gratis)
- **Crawler:** Python (httpx + trafilatura + articleBody JSON-LD), GitHub Actions 6h.
- **BD:** Supabase (Postgres + pgvector), São Paulo. Claves sb_secret_ (crawler) /
  sb_publishable_ (web, var NEXT_PUBLIC_SUPABASE_KEY). RLS = solo lectura pública.
- **Web:** Next.js 14 (App Router, Server Components, JS/JSX — NO TypeScript),
  Vercel → trama-co.vercel.app. CSS global en globals.css (tokens en :root).
  Caché: feed revalidate 300s, artículos 3600s (la base se actualiza al instante;
  la web puede tardar ~5min o requerir hard refresh; para validar, usar query).
  NOTA: /historias se renderiza dinámicamente por request (usa searchParams).
- **Repo:** GitHub JotaLabs/trama (privado, monorepo). /crawler, /web, /supabase/migrations.
- **Migraciones:** van 9. Última: 20260617000009_rls_lectura_stories.

## DÓNDE ESTAMOS — 2026-06-21

**Fase 1 COMPLETA y desplegada.** Crawler solo, web pública, 5 medios.

**Fase 2 EN PRODUCCIÓN (vista + clustering + feed paginado).** Vive en
trama-co.vercel.app/historias y /historia/[id].

**Banco al día (medido 2026-06-21, tras backfill + reclustering):**
- **Artículos en BD: 1645**, TODOS con embedding (los 663 pendientes se backfillearon).
- **Clustering vigente: 83 clústeres / 329 noticias clusterizadas** (sobre 1496
  noticias núcleo; 458 aristas pasan las dos compuertas). El banco YA es multitema:
  dejó de estar dominado por 2-3 macro-temas (Chalá/Niño Guerrero/electoral). Es la
  primera corrida sobre la que tiene sentido recalibrar umbrales con volumen diverso.

**Clustering: dos compuertas AND** — peso IDF de entidades compartidas ≥20 Y coseno
≥0.70. 3 scores por artículo (neutralidad, cobertura, divergencia) en story_articles.
Umbrales provisionales (recalibrar ahora que hay volumen multitema; antes bloqueado
por falta de diversidad temática, ese bloqueo ya NO aplica).

**UUID ESTABLE DE STORIES — RESUELTO Y VALIDADO (2026-06-21).** stories.id ya NO es
aleatorio: es uuid5 determinista sembrado en la url del artículo más antiguo del
clúster (NAMESPACE_STORIES constante en clustering_fase2.py). Validado: dos corridas
consecutivas sobre los mismos datos dan los 83 uuids IDÉNTICOS. Enlaces /historia/[id]
sobreviven cada corrida mientras el artículo más antiguo siga en el clúster. Residual
conocido (fusión / re-semilla) documentado en BITACORA. Esto DESBLOQUEA la
automatización del pipeline.

**ARREGLO DEL ANCLA — vigente (2026-06-18).** Ancla principal = piso p75 de
neutralidad del clúster + desempate por cobertura. Ancla secundaria = mayor
divergencia. Ver BITACORA.

**FEED↔ANCLA / TÍTULO-CITA — vigente (2026-06-21).** El feed usa tituloCanonico
(lib/colapsarCluster.js): titular noticia más neutral que NO sea cita declarativa.
NOTA para no asustarse: un query crudo de stories.titulo muestra titulares-cita
(Petro 8d909996, Gaona 06c71072, Germán 1f9fd820, etc.) — eso es el valor de BD, NO
lo que el feed renderiza. El feed los sanea en presentación. No es regresión.

**FEED PAGINADO + ORDENABLE — EN PRODUCCIÓN (2026-06-21).** /historias ya no muestra
30 fijos: pagina de a 20 (≈5 páginas para 83) vía searchParams + .range(). Orden por
3 atributos (Más reciente=fecha_fin desc [default], Más medios=n_medios desc, Más
cobertura=n_articulos desc), todos con desempate determinista. URLs compartibles
(/historias?sort=medios&page=2). created_at se quitó como orden (era ruido de
inserción: 63s de rango para los 83). La rama CON búsqueda aplica orden pero NO
pagina (deuda acotada, no muerde con 83 stories).

### Decisiones de la vista (cerradas, encarnadas en el código)
- **Átomo = `url`**, no el medio ni la captura. Colapsar capturas del mismo url.
- Representante del artículo = última captura (título/scores/es_parcial de ahí).
- "editada" solo si cambió titular o bajada; cambio solo de cuerpo → "N capturas".
- es_ancla = OR de capturas (contrato del pipeline, no se recalcula en la vista).
- Hilo: un nodo por artículo (url), coloreado por medio, ordenado por primera captura.
- **Título del feed = titular noticia más neutral que NO sea cita declarativa**
  (tituloCanonico). Independiente de es_ancla por diseño.
- **Orden del feed = fecha_fin desc por default**, con desempate determinista.
- **Identidad del clúster = uuid5(NAMESPACE_STORIES, url del más antiguo)**, no aleatoria.

## PRÓXIMO PASO cuando retomemos
1. **Automatizar backfill (RECOMENDADO).** backfill_fase2.py es idempotente
   (WHERE embedding IS NULL), solo agrega entidades/embedding, NO toca stories ni
   contenido/hash. Es la parte CARA (spaCy + sentence-transformers). Automatizarlo es
   seguro e independiente. Decidir runner: ¿GitHub Actions aparte del crawler, o paso
   encadenado tras el crawler? Ojo modelos pesados en Actions (tiempo/caché de deps).
2. **Automatizar clustering (DESBLOQUEADO por UUID estable, va DESPUÉS de #1).** Ya
   no rompe enlaces. Decidir frecuencia (¿tras cada backfill? ¿diario?) y si recalibrar
   umbrales ANTES de automatizar, para no fosilizar provisionales (ver #3).
3. **Recalibrar umbrales con volumen multitema (AHORA es posible).** El bloqueo
   "banco dominado por pocos macro-temas" se levantó: 83 clústeres multitema. Re-juzgar
   IDF≥20 / coseno≥0.70 / p75 sobre los clústeres chicos (2-3 art), donde un umbral
   flojo mete falsos positivos. Hacerlo ANTES de automatizar clustering (cada recompute
   total es la oportunidad de re-calibrar; automatizar sin recalibrar congela los
   provisionales).
4. **Feed pagination en rama CON búsqueda** (deuda menor): hoy la búsqueda no pagina.
   No urge con 83 stories. Combinar con "feed plano silencia medios de baja frecuencia"
   si se aborda.
5. **Doble-cómputo de título** (backend stories.titulo vs frontend tituloCanonico):
   coinciden de facto, se desincronizan si cambia el criterio de ancla. No urgente.
6. Limpieza pendiente: duplicados de capitalización en raíz (Cierre/CIERRE,
   Arquitectura/ARQUITECTURA); alinear tintas de ARQUITECTURA §7 con globals.css.
7. **Fase 2 avanzada (grafo de historias relacionadas).** Ahora menos prematuro:
   identidad estable ya existe. Sigue dependiendo de umbrales recalibrados (#3) y de
   tabla story_relations (no existe).
8. Fase 3 más adelante (LLM decidido: NVIDIA NIM).

## Deudas activas (detalle en BITACORA)
- **UUID de stories no estable** — RESUELTO 2026-06-21 (uuid5 determinista). Residual
  de fusión/re-semilla documentado, con disparador. Ver BITACORA.
- **Umbrales provisionales sin recalibrar con multitema** (2026-06-21) — el bloqueo se
  levantó (banco multitema); recalibrar es ahora trabajo posible, no bloqueado.
- **Búsqueda no paginada** (2026-06-21) — rama q3 sin .limit()/.range(). No muerde a 83.
- **Doble-cómputo de título** (2026-06-21) — backend vs frontend, hoy coinciden de facto.
- **Titular-cita ancla clústeres** — MITIGADA en display (tituloCanonico). Scoring NO tocado.
- **Ancla por cobertura elige mal** — RESUELTA 2026-06-18 (gate p75).
- **Lookup por URL best-effort** — falla silencioso con variantes AMP/m./canónicas.

## Fase 2 NO obliga a reconstruir al agregar medios
El clustering opera sobre artículos. Agregar medio = config en outlets; solo se
recalibran umbrales. Validar con 5 medios antes de expandir. Cola: La Silla Vacía
y RTVC (feeds verificados, no activados), Colombia+20, Semana, Caracol/W Radio.

LLM de Fase 3 DECIDIDO (2026-06-19): NVIDIA NIM hosted, meta/llama-3.3-70b-instruct,
cliente swappable, Groq fallback. Detalle en ARQUITECTURA §2/§5 y BITACORA. No
re-evaluar sin motivo nuevo. NOTA: descartado generar títulos de historia por LLM.

## Cómo verificar el estado
- Web vista de Fase 2: trama-co.vercel.app/historias y /historia/[id] (producción).
  Local: cd web && npm run dev → localhost:3000.
- Feed paginado: /historias muestra 20, default fecha_fin desc, ~5 páginas. Probar
  /historias?sort=medios&page=2 (orden + página persisten en URL).
- UUID estable (prueba decisiva): correr clustering 2× sin cambiar datos; el query
  `select md5(string_agg(id::text, ',' order by id)) from stories;` debe dar la MISMA
  huella en ambas corridas. uuids son v5 (5º grupo empieza con '5'), no v4.
- Clustering: stories/story_articles tienen filas (83 clústeres del último run sobre 1645).
- RLS: select * from pg_policies where tablename in ('stories','story_articles');
- Crawler: pestaña Actions en verde.