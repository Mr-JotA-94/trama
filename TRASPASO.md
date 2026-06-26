# TRAMA — Estado del proyecto (traspaso a nueva sesión)

> Dáselo a un chat nuevo para retomar sin releer conversaciones. Léelo junto con
> ARQUITECTURA.md (plan completo) y BITACORA.md (decisiones y deuda).
> Última actualización: **2026-06-26**.

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
- **Web:** Next.js 14 (App Router, Server Components, JS/JSX — NO TypeScript),
  Vercel → trama-co.vercel.app. CSS global en globals.css (tokens en :root).
  Caché: feed revalidate 300s, artículos 3600s. /historias es dinámico por request.
- **Repo:** GitHub Mr-JotA-94/trama (privado, monorepo). /crawler, /web, /supabase/migrations.
- **Migraciones:** van 10. Última: 20260625000010_story_relations.
- **CI:** workflow `crawler.yml` con TRES jobs encadenados: crawl (6h) → backfill
  (needs:crawl) → clustering (needs:backfill).

## DÓNDE ESTAMOS — 2026-06-26

**Fase 1 COMPLETA y desplegada.** Crawler, web pública, 5 medios.

**Fase 2 EN PRODUCCIÓN (vista + clustering + feed paginado).** trama-co.vercel.app/historias.

**PIPELINE AUTOMATIZADO Y ARCHIVANDO.** Confirmado 2026-06-24; IPs de Actions no bloqueadas.

**story_relations IMPLEMENTADO, NO EXPUESTO (sesión 2026-06-25).** Migración 10 desplegada
(grafo dirigido-espejo: PK compuesta, FK CASCADE, CHECK anti-self-loop, índice
(origen_id, n_especificas desc), RLS con SELECT). El motor de relaciones vive en
clustering_fase2.py como 2ª pasada (criterio: n_especificas ≥ 3 AND cos-guardia ≥ 0.50).
Los PARES aún NO se validaron a ojo ni se recalibraron sobre entidades limpias, y el
grafo NO se expone en la web hasta hacerlo.

**RE-BACKFILL DE NER — FIX DE RAÍZ APLICADO (2026-06-26).** El ruido de NER (conectores,
frases con artículo, verbos sueltos, medios) que contaminaba el peso IDF y n_especificas
se atacó upstream. Filtro nuevo en ner_filtro.py (FUENTE ÚNICA, importado por
backfill_fase2.py y rebackfill_ner.py): conserva entidad si tiene ≥1 token PROPN o es
sigla; descarta medios (lista cerrada) y topes 60 chars / 8 tokens. Re-backfill aplicado
sobre todo el banco (−20,2% entidades; ruido confirmado a ojo). Clustering recomputado:
151→149 stories, 143 uuid estables (94,7%), 8 rotos / 6 nuevos = disolución de uniones
espurias por boilerplate. Banco consistente (re-backfill corrido hasta aplicados=0).

**Banco:** ~2732 artículos embebidos (todos con entidades limpias).

**ÁTOMO = URL, UUID ESTABLE, ANCLA, FEED↔TÍTULO-CITA, FEED PAGINADO** — todo vigente.

## PRÓXIMO PASO cuando retomemos
1. **Recalibrar umbrales sobre entidades limpias (measure-first, Tier 0 primero).** El
   peso IDF baja al quitar el boilerplate raro de alto IDF que lo inflaba; UMBRAL_IDF≥20
   fue validado con NER sucio. Correr diag_umbrales.py (read-only) y DECIDIR si mover el
   umbral del clustering o si aguanta. Igual para UMBRAL_N_ESPECIFICAS de relaciones.
   NO asumir que hay que bajarlo: medir el histograma primero.
2. **Retirar RUIDO_DURO de clustering_fase2.py** (queda solo MEDIOS + genéricas-por-DF),
   como prometía su propio comentario ahora que el NER limpio es la raíz.
3. **Validar los pares de story_relations a ojo** sobre entidades limpias (Air-e, capturas
   Clan del Golfo, Beto Coral, Arizabaleta, Cauca). Recién entonces exponer el grafo.
4. **Robustez delete-then-insert / writes masivos** (deuda con evidencia nueva: el patrón
   uno-por-uno se cortó en el re-backfill; el clustering inserta por lotes y aguantó).
5. Fase 3 más adelante (LLM decidido: NVIDIA NIM).

## Deudas activas (detalle en BITACORA)
- **Writes masivos uno-por-uno son frágiles** (2026-06-26, OBSERVADO) — el re-backfill se
  cortó a ~800 writes (WinError 10054, el pooler corta). Resuelto EN el re-backfill
  (reanudable + retry/backoff + reconexión). El clustering comparte el patrón delete-then-
  insert; inserta por lotes y aguantó esta vez, pero la deuda sigue latente.
- **Dependencias del clustering sin pin** (2026-06-23) — disparador.
- **Robustez delete-then-insert del clustering** (2026-06-23) — no transaccional; ahora
  también cubre story_relations (ventana ensanchada, 2026-06-24).
- **Árbol de dependencias de backfill no congelado** (2026-06-23).
- **Macro-tema irreducible por heurística de entidades** (2026-06-24) — contexto/seguimiento
  se difiere a Fase 3.
- **Búsqueda no paginada** (2026-06-21).
- **Doble-cómputo de título** (2026-06-21) — backend vs frontend, hoy coinciden.
- **Titular-cita ancla clústeres** — MITIGADA en display. Scoring NO tocado.
- **Lookup por URL best-effort** — falla silencioso con variantes AMP/m./canónicas.

## Fase 2 NO obliga a reconstruir al agregar medios
El clustering opera sobre artículos. Agregar medio = config en outlets; solo se
recalibran umbrales. Cola: La Silla Vacía y RTVC (feeds verificados, no activados).
Al activar un medio nuevo: agregar su nombre a MEDIOS en ner_filtro.py.

LLM de Fase 3 DECIDIDO (2026-06-19): NVIDIA NIM hosted, meta/llama-3.3-70b-instruct,
cliente swappable, Groq fallback.

## Cómo verificar el estado
- Web Fase 2: trama-co.vercel.app/historias y /historia/[id].
- Pipeline CI: Actions → "crawler" con TRES jobs en verde y en cadena.
- Re-backfill consistente: `python rebackfill_ner.py` dice `aplicados=0`.
- Entidades limpias: ninguna entidad debería empezar con artículo+común ("la captura")
  ni ser verbo suelto ("Estamos") al inspeccionar la columna.
- UUID estable: clustering 2× sin cambiar datos → misma huella md5 de string_agg.