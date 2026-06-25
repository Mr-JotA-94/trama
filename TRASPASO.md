# TRAMA — Estado del proyecto (traspaso a nueva sesión)

> Dáselo a un chat nuevo para retomar sin releer conversaciones. Léelo junto con
> ARQUITECTURA.md (plan completo) y BITACORA.md (decisiones y deuda).
> Última actualización: **2026-06-24**.

## Quién soy y cómo trabajamos
Soy Jota (Johan). Claude es "Claudio". Reglas que NO se pierden:
- **Challenge-first:** cuestiona enfoques con fallas ANTES de construir. Honestidad
  sobre complacencia.
- **Declarar Tier (0–3) + load-bearing antes de construir.**
- Directo, conciso, instructivo, en español. **Medir antes de arreglar.**
- Diagnóstico con datos reales; si Claudio no puede verificar en su entorno, me da
  script para correr aquí. NUEVO (2026-06-24): para diagnósticos read-only puedo
  exportar un snapshot estático (CSV/JSON de las columnas necesarias) y Claudio lo
  corre/itera de su lado. Claude Code es solo para CAMBIOS de código en repo.
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
- **Migraciones:** van 9. Última: 20260617000009_rls_lectura_stories.
- **CI:** workflow `crawler.yml` con TRES jobs encadenados: crawl (6h) → backfill
  (needs:crawl) → clustering (needs:backfill).

## DÓNDE ESTAMOS — 2026-06-24

**Fase 1 COMPLETA y desplegada.** Crawler, web pública, 5 medios.

**Fase 2 EN PRODUCCIÓN (vista + clustering + feed paginado).** trama-co.vercel.app/historias.

**PIPELINE AUTOMATIZADO Y CONFIRMADO ARCHIVANDO (2026-06-24).** La "prueba de fuego de
IPs" quedó CERRADA: Jota verificó que el pipeline archiva de verdad y que las historias
crecen progresivamente corrida a corrida. Las IPs de GitHub Actions NO están bloqueadas.
Deuda cerrada.

**Banco creciendo (observado por diag 2026-06-24):** 122 clústeres vigentes; 2275
capturas embebidas cargadas por el diagnóstico. (Conteo de artículos ÚNICOS: verificar
con la query estándar; el diag colapsa por URL solo dentro de cada clúster.)

**FASE 2 AVANZADA — MEDICIÓN CERRADA, ESQUEMA PENDIENTE (2026-06-24).** Cuatro
diagnósticos read-only (diag_relaciones v1→v4, desechables, no en repo) definieron el
criterio de relaciones entre clústeres con datos:
- **Criterio que SÍ funciona (hechos discretos):** n_especificas (entidades reales y
  específicas compartidas, tras limpiar ruido NER + geografía + genéricas por DF de
  clúster) ≥ umbral, con coseno entre centroides como GUARDIA (no motor; el coseno liga
  por TEMA, no por hecho). Valida Air-e, capturas Clan del Golfo, Cauca, Arizabaleta,
  Beto Coral, giro a la derecha LatAm.
- **Lo que NO se puede por heurística:** el macro-tema (campaña electoral) es un hub
  irreducible. Un clúster-bolsa grande (n_esp propias 125-134 vs 31-40 de un hecho
  discreto) toca medio archivo por TAMAÑO. Ni cluster-IDF ni el cap de presentación lo
  disuelven (Pastrana in-degree 26→23). Separar "contexto" de "seguimiento" es trabajo
  de Fase 3 (LLM + tipo_relacion).
- **Decisiones tomadas (detalle y porqué en BITACORA 2026-06-24):**
  * story_relations = CACHÉ DERIVADA PURA, se recomputa con stories, NO estado
    persistente (coherente con la naturaleza de stories; ensancha la ventana del
    delete-then-insert no transaccional a otra tabla — aceptado en frío).
  * Hub controlado con **cap de in-degree (+out-degree) en la capa de LECTURA**, no en
    la tabla. Reversible, de presentación.
  * Alcance del tablero: clúster↔clúster, expandido desde la historia foco, 1-2 saltos,
    nunca los 122. Hilo sólido = relación fuerte, discontinuo = débil (no mentir sobre
    la fuerza de la evidencia).

**ÁTOMO = URL, UUID ESTABLE, ANCLA, FEED↔TÍTULO-CITA, FEED PAGINADO** — todo vigente
(ver historial 2026-06-21/23).

## PRÓXIMO PASO cuando retomemos
1. **Diseñar el esquema `story_relations`** (unidad propia, con cierre formal). Toca
   arquitectura. Criterio = n_especificas ≥ umbral + cos-guardia; caps de in/out-degree
   en lectura; caché derivada pura recomputada con stories; columna tipo_relacion como
   stub para Fase 3. Definir umbral conservador con los datos de los diags.
2. **HIPÓTESIS NO MEDIDA: sobre-fusión del clustering** (unidad aparte, measure-first).
   Los clústeres-bolsa gigantes (Pastrana, Chalá, cierres de campaña) PUEDEN ser
   sobre-fusión de la transitividad union-find, no problema de relaciones. Diagnóstico
   read-only ANTES de tocar clustering_fase2.py (Tier 2 load-bearing). Se puede correr
   subiéndole a Claudio un snapshot estático. NO bloquea el esquema (el cap de in-degree
   controla el hub exista o no sobre-fusión).
3. Robustez delete-then-insert del clustering (deuda; ahora con story_relations encima).
4. Feed pagination en rama CON búsqueda (deuda menor).
5. Fase 3 más adelante (LLM decidido: NVIDIA NIM).

## Deudas activas (detalle en BITACORA)
- **Ruido de NER contamina relaciones inter-clúster** (2026-06-24) — el fix es NER
  upstream en backfill (re-backfill), no en la capa de relaciones. Disparador medido.
- **Macro-tema irreducible por heurística de entidades** (2026-06-24) — limitación
  conocida; clasificación contexto/seguimiento se difiere a Fase 3.
- **story_relations ensancha la ventana del delete-then-insert** (2026-06-24).
- **Dependencias del clustering sin pin** (2026-06-23) — disparador.
- **Robustez delete-then-insert del clustering** (2026-06-23) — no transaccional.
- **Árbol de dependencias de backfill no congelado** (2026-06-23).
- **Búsqueda no paginada** (2026-06-21).
- **Doble-cómputo de título** (2026-06-21) — backend vs frontend, hoy coinciden.
- **Titular-cita ancla clústeres** — MITIGADA en display. Scoring NO tocado.
- **Lookup por URL best-effort** — falla silencioso con variantes AMP/m./canónicas.

## Fase 2 NO obliga a reconstruir al agregar medios
El clustering opera sobre artículos. Agregar medio = config en outlets; solo se
recalibran umbrales. Cola: La Silla Vacía y RTVC (feeds verificados, no activados).

LLM de Fase 3 DECIDIDO (2026-06-19): NVIDIA NIM hosted, meta/llama-3.3-70b-instruct,
cliente swappable, Groq fallback.

## Cómo verificar el estado
- Web Fase 2: trama-co.vercel.app/historias y /historia/[id].
- Pipeline CI: Actions → "crawler" con TRES jobs en verde y en cadena.
- Crawler insertó de verdad: log del job crawl, línea `Nuevos: X | Ya existentes: Y |
  Errores: Z`. (Confirmado archivando 2026-06-24.)
- Backfill: tras un run, `select count(*) from articles where embedding is null;` → 0.
- UUID estable: clustering 2× sin cambiar datos → misma huella md5 de string_agg.