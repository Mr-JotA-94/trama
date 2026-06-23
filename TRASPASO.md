# TRAMA — Estado del proyecto (traspaso a nueva sesión)

> Dáselo a un chat nuevo para retomar sin releer conversaciones. Léelo junto con
> ARQUITECTURA.md (plan completo) y BITACORA.md (decisiones y deuda).
> Última actualización: **2026-06-23**.

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
  **Pull al EMPEZAR cada unidad, no al chocar con el push** (un merge hecho en GitHub
  adelanta main remoto en silencio — pasó 2026-06-23).
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
- **Repo:** GitHub Mr-JotA-94/trama (privado, monorepo). /crawler, /web, /supabase/migrations.
- **Migraciones:** van 9. Última: 20260617000009_rls_lectura_stories.
- **CI:** workflow `crawler.yml` con DOS jobs encadenados: crawl (6h) → backfill
  (needs:crawl). Ver "DÓNDE ESTAMOS".

## DÓNDE ESTAMOS — 2026-06-23

**Fase 1 COMPLETA y desplegada.** Crawler solo, web pública, 5 medios.

**Fase 2 EN PRODUCCIÓN (vista + clustering + feed paginado).** Vive en
trama-co.vercel.app/historias y /historia/[id].

**BACKFILL AUTOMATIZADO — NUEVO (2026-06-23).** backfill_fase2.py ya NO se corre a
mano: corre encadenado al crawler vía `needs: crawl` en el mismo workflow
(.github/workflows/crawler.yml). Entorno ML separado del crawler liviano
(requirements-backfill.txt: torch CPU-only + spaCy + sentence-transformers), caché
pip + HuggingFace. Si crawl falla, backfill no corre (sin ingesta no hay nada que
embeber; el backlog espera sin costo). backfill_fase2.py intacto (idempotente,
WHERE embedding IS NULL). El clustering SIGUE siendo manual a propósito (ver próximo paso).

**Banco al día (medido 2026-06-21, tras backfill + reclustering):**
- **Artículos en BD: 1645+**, embeddings ahora se rellenan solos cada 6h.
- **Clustering vigente: 83 clústeres / 329 noticias** (último run manual). El banco YA
  es multitema. Es la primera corrida sobre la que tiene sentido recalibrar umbrales.

**Clustering: dos compuertas AND** — peso IDF de entidades compartidas ≥20 Y coseno
≥0.70. 3 scores por artículo (neutralidad, cobertura, divergencia) en story_articles.
Umbrales provisionales (recalibrar ahora que hay volumen multitema).

**UUID ESTABLE DE STORIES — RESUELTO Y VALIDADO (2026-06-21).** stories.id es uuid5
determinista sembrado en la url del artículo más antiguo del clúster. DESBLOQUEA la
automatización del clustering (pero esa va DESPUÉS de recalibrar — ver próximo paso).

**ARREGLO DEL ANCLA — vigente (2026-06-18).** Piso p75 de neutralidad + desempate
por cobertura. Ancla secundaria = mayor divergencia.

**FEED↔ANCLA / TÍTULO-CITA — vigente (2026-06-21).** El feed usa tituloCanonico
(titular noticia más neutral que NO sea cita declarativa). stories.titulo crudo en BD
puede mostrar títulos-cita: eso es el valor de BD, NO lo que el feed renderiza.

**FEED PAGINADO + ORDENABLE — EN PRODUCCIÓN (2026-06-21).** /historias pagina de a 20,
3 órdenes (fecha_fin desc default, n_medios desc, n_articulos desc), URLs compartibles.
La rama CON búsqueda aplica orden pero NO pagina (deuda acotada).

### Decisiones de la vista (cerradas, encarnadas en el código)
- **Átomo = `url`**, no el medio ni la captura. Colapsar capturas del mismo url.
- Representante del artículo = última captura.
- "editada" solo si cambió titular o bajada; cambio solo de cuerpo → "N capturas".
- es_ancla = OR de capturas (contrato del pipeline, no se recalcula en la vista).
- Hilo: un nodo por artículo (url), coloreado por medio, ordenado por primera captura.
- **Título del feed = titular noticia más neutral que NO sea cita declarativa.**
- **Orden del feed = fecha_fin desc por default**, con desempate determinista.
- **Identidad del clúster = uuid5(NAMESPACE_STORIES, url del más antiguo)**.

## PRÓXIMO PASO cuando retomemos
1. **Recalibrar umbrales con volumen multitema (RECOMENDADO, AHORA es posible).** El
   bloqueo "banco dominado por pocos macro-temas" se levantó: 83 clústeres multitema.
   Re-juzgar IDF≥20 / coseno≥0.70 / p75 sobre los clústeres chicos (2-3 art), donde un
   umbral flojo mete falsos positivos. **Va ANTES de automatizar clustering** (cada
   recompute total es la oportunidad de re-calibrar; automatizar sin recalibrar congela
   los provisionales).
2. **Automatizar clustering (DESBLOQUEADO por UUID estable, va DESPUÉS de #1).** Ya no
   rompe enlaces. Decidir frecuencia (¿tras cada backfill? ¿diario?). El patrón natural:
   juntar clustering en un workflow propio o como tercer job `needs: backfill`.
3. **Feed pagination en rama CON búsqueda** (deuda menor). No urge con 83 stories.
4. **Doble-cómputo de título** (backend stories.titulo vs frontend tituloCanonico):
   coinciden de facto, se desincronizan si cambia el criterio de ancla. No urgente.
5. Limpieza pendiente: duplicados de capitalización en raíz; alinear tintas de
   ARQUITECTURA §7 con globals.css.
6. **Fase 2 avanzada (grafo de historias relacionadas).** Requiere umbrales
   recalibrados (#1) y tabla story_relations (no existe). Confirmado: los clusters
   relacionados son ESTA fase, pero van DESPUÉS de #1 y #2.
7. Fase 3 más adelante (LLM decidido: NVIDIA NIM).

## Deudas activas (detalle en BITACORA)
- **Árbol de dependencias de backfill no congelado** (2026-06-23) — se parchó `click`,
  no se hizo `pip freeze`. Riesgo de romper en un update transitivo silencioso. Disparador.
- **Prueba de fuego de IPs de Actions no confirmada duro** (2026-06-23) — el crawler
  corre verde desde CI; falta confirmar inserts reales vs bloqueo 403 (verde no garantiza
  archivado). Revisar log `Nuevos/Ya existentes/Errores` del job crawl.
- **Umbrales provisionales sin recalibrar con multitema** (2026-06-21) — bloqueo levantado.
- **Búsqueda no paginada** (2026-06-21) — rama q3 sin .range(). No muerde a 83.
- **Doble-cómputo de título** (2026-06-21) — backend vs frontend, hoy coinciden.
- **Titular-cita ancla clústeres** — MITIGADA en display. Scoring NO tocado.
- **Lookup por URL best-effort** — falla silencioso con variantes AMP/m./canónicas.

## Fase 2 NO obliga a reconstruir al agregar medios
El clustering opera sobre artículos. Agregar medio = config en outlets; solo se
recalibran umbrales. Cola: La Silla Vacía y RTVC (feeds verificados, no activados).

LLM de Fase 3 DECIDIDO (2026-06-19): NVIDIA NIM hosted, meta/llama-3.3-70b-instruct,
cliente swappable, Groq fallback. Descartado generar títulos de historia por LLM.

## Cómo verificar el estado
- Web vista de Fase 2: trama-co.vercel.app/historias y /historia/[id].
- Pipeline CI: pestaña Actions → workflow "crawler" debe mostrar DOS jobs (crawl,
  backfill) en verde. backfill solo corre si crawl tuvo éxito.
- Backfill funcionando: tras un run, `select count(*) from articles where embedding
  is null;` tiende a 0.
- UUID estable: correr clustering 2× sin cambiar datos; `select md5(string_agg(id::text,
  ',' order by id)) from stories;` debe dar la MISMA huella.
- Crawler insertó de verdad (no solo verde): mirar log del job crawl, línea final
  `Nuevos: X | Ya existentes: Y | Errores: Z`. Y alto = llegó a los medios.