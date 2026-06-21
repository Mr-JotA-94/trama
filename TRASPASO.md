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
- **Repo:** GitHub JotaLabs/trama (privado, monorepo). /crawler, /web, /supabase/migrations.
- **Migraciones:** van 9. Última: 20260617000009_rls_lectura_stories.

## DÓNDE ESTAMOS — 2026-06-21

**Fase 1 COMPLETA y desplegada.** Crawler solo, web pública, 5 medios.

**Fase 2 EN PRODUCCIÓN (vista + clustering).** Vive en trama-co.vercel.app/historias
y /historia/[id].

**Banco de artículos vs banco clusterizado SE SEPARARON (medido 2026-06-21):**
- **Artículos en BD: 1645** (re-medido 06-21). El crawler corre solo cada 6h y sumó
  ~663 desde el 06-18.
- **Último clustering: corrió sobre 982 → 48 clústeres / 178 noticias.** Los ~663
  nuevos NO están clusterizados y muchos aún sin embedding (backfill manual pendiente).
- **Implicación:** correr backfill+clustering ahora incorpora los 663 PERO regenera
  TODOS los uuids de stories (delete+insert) → rompe enlaces existentes. Es la deuda
  UUID-estable hecha tensión real. Decidir UUID estable ANTES, o aceptar el churn.

**Clustering: dos compuertas AND** — peso IDF de entidades compartidas ≥20 Y coseno
≥0.70. 3 scores por artículo (neutralidad, cobertura, divergencia) en story_articles.
Umbrales provisionales (re-verificar con semanas de volumen multitema; el banco sigue
dominado por pocos macro-temas Chalá/Niño Guerrero/electoral).

**ARREGLO DEL ANCLA — vigente (2026-06-18).** Ancla principal = piso p75 de
neutralidad del clúster + desempate por cobertura. Ancla secundaria = mayor
divergencia. Validado: Chalá ancla "Legalizan captura" (id 0b869f42), no la reacción
del Alcalde. Ver BITACORA.

**FEED↔ANCLA RESUELTO (2026-06-21).** El feed NO lee stories.titulo: usa
`tituloCanonico` (lib/colapsarCluster.js). Antes elegía el titular noticia de máxima
neutralidad PURA — la fórmula que el arreglo del ancla descartó → el arreglo era
invisible en el feed. Causa estructural: el título de display se computa en TRES
lugares (es_ancla backend = gate p75; stories.titulo = hereda del ancla;
tituloCanonico frontend). Fix aplicado: tituloCanonico ahora descarta titulares-cita
declarativos. Tier 2, presentación, NO toca scoring ni es_ancla. Validado sobre los
48: 3 títulos saneados (Petro b56729d8, Gaona 974f9571, Medicina Legal 3ce9745f), 0
falsos positivos, 1 residual aceptado (Germán 656a7e6c, sin alternativa no-cita).

### Decisiones de la vista (cerradas, encarnadas en el código)
- **Átomo = `url`**, no el medio ni la captura. Colapsar capturas del mismo url.
- Representante del artículo = última captura (título/scores/es_parcial de ahí).
- "editada" solo si cambió titular o bajada; cambio solo de cuerpo → "N capturas".
- es_ancla = OR de capturas (contrato del pipeline, no se recalcula en la vista).
- Hilo: un nodo por artículo (url), coloreado por medio, ordenado por primera captura.
- **Título del feed = titular noticia más neutral que NO sea cita declarativa**
  (tituloCanonico). Independiente de es_ancla por diseño (desacople presentación↔
  scoring). Si todas las noticias son cita, cae a la más neutral; si no hay noticias,
  cae a stories.titulo.

## PRÓXIMO PASO cuando retomemos
1. **UUID estable / identidad de stories (RECOMENDADO).** reescribir_stories hace
   delete+insert → uuid nuevo cada corrida → todo enlace /historia/[uuid] compartido
   se rompe. Es PREREQUISITO de automatizar clustering y de incorporar los 663 nuevos
   sin romper enlaces. NO es optimización de cuota — es identidad + escala. Opciones
   en BITACORA.
2. **Incorporar los 663 nuevos (backfill + clustering).** Bloqueado de facto por #1:
   correrlo hoy regenera uuids. Si se acepta el churn (aún sin enlaces compartidos en
   producción), se puede correr antes; si ya importa la estabilidad, va después de #1.
3. **Feed pagination + justicia de frecuencia de medios.** El feed muestra 30 de 48
   (limit(30) en page.js, orden created_at desc) → esconde clústeres grandes (Chalá
   19-art quedó fuera). Combina con la deuda "feed plano silencia medios de baja
   frecuencia". Acotado y visible.
4. **Acumular volumen MULTITEMA** (pasivo). Prerequisito de tocar umbrales /
   automatización / grafo. Ya hay volumen nuevo (663) pendiente de procesar.
5. **Deuda doble-cómputo de título** (ver BITACORA): título se calcula en backend
   (stories.titulo) y frontend (tituloCanonico) con criterios que hoy coinciden de
   facto pero se desincronizan si cambia el criterio de ancla. ¿Fuente única algún
   día? No urgente.
6. Limpieza pendiente: duplicados de capitalización en raíz (Cierre/CIERRE,
   Arquitectura/ARQUITECTURA); alinear tintas de ARQUITECTURA §7 con globals.css.
7. **Fase 2 avanzada (grafo de historias relacionadas): PREMATURO.** Depende de
   umbrales a recalibrar y de identidad estable que aún no existe.
8. Fase 3 más adelante.

## Deudas activas (detalle en BITACORA)
- **UUID de stories no estable** (2026-06-21) — enlaces se rompen cada corrida.
  Prerequisito de automatización e incorporación de nuevos artículos.
- **Banco clusterizado desfasado** (2026-06-21) — 1645 en BD, 48 clústeres sobre 982.
  ~663 sin procesar.
- **Doble-cómputo de título** (2026-06-21) — backend vs frontend, hoy coinciden de facto.
- **Titular-cita ancla clústeres** — MITIGADA en display 2026-06-21 (tituloCanonico
  filtra citas; residual 1/48 Germán). El scoring/es_ancla NO se tocó. Ver BITACORA.
- **Ancla por cobertura elige mal** — RESUELTA 2026-06-18 (gate p75). Ver BITACORA.
- **Lookup por URL best-effort** — falla silencioso con variantes AMP/m./canónicas.
  Mitigado con 4 variantes www×slash.

## Fase 2 NO obliga a reconstruir al agregar medios
El clustering opera sobre artículos. Agregar medio = config en outlets; solo se
recalibran umbrales. Validar con 5 medios antes de expandir. Cola: La Silla Vacía
y RTVC (feeds verificados, no activados), Colombia+20, Semana, Caracol/W Radio.

LLM de Fase 3 DECIDIDO (2026-06-19): NVIDIA NIM hosted, meta/llama-3.3-70b-instruct,
cliente swappable, Groq fallback. Detalle en ARQUITECTURA §2/§5 y BITACORA. No
re-evaluar sin motivo nuevo. NOTA: descartado generar títulos de historia por LLM
(rompe inmutabilidad, no-determinista, adelanta Fase 3) — ver BITACORA 2026-06-21.

## Cómo verificar el estado
- Web vista de Fase 2: trama-co.vercel.app/historias y /historia/[id] (producción).
  Local: cd web && npm run dev → localhost:3000.
- Clustering: stories/story_articles tienen filas (48 clústeres del último run sobre 982).
- Fix título-cita: diag_fix_titulos.py debe dar 3 cambios (Petro/Gaona/Medicina
  Legal), 0 falsos positivos, residual = solo Germán 656a7e6c.
- Ancla Chalá (testea el valor de BD, NO lo que muestra el feed): stories.titulo del
  id 0b869f42 = "Última hora: Legalizan captura de alias 'Chalá'…". El feed muestra
  tituloCanonico, que puede diferir.
- RLS: select * from pg_policies where tablename in ('stories','story_articles');
- Crawler: pestaña Actions en verde.
