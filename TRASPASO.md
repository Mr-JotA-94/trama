# TRAMA — Estado del proyecto (traspaso a nueva sesión)

> Dáselo a un chat nuevo para retomar sin releer conversaciones. Léelo junto con
> ARQUITECTURA.md (plan completo) y BITACORA.md (decisiones y deuda).
> Última actualización: **2026-06-18**.

## Quién soy y cómo trabajamos
Soy Jota (Johan). Claude es "Claudio". Reglas que NO se pierden:
- **Challenge-first:** cuestiona enfoques con fallas ANTES de construir. Honestidad
  sobre complacencia.
- **Declarar Tier (0–3) + load-bearing antes de construir.**
- Directo, conciso, instructivo, en español. **Medir antes de arreglar.**
- Diagnóstico con datos reales; si Claudio no puede verificar en su entorno, me da
  script para correr aquí.
- **Disciplina de sesión (aprendida a la mala 2026-06-17):** un chat = UNA unidad
  de trabajo = un cierre. Cerrar en límites lógicos, no cuando se llene la ventana.
  Un chat largo multitema arrastra todo el contexto cada turno y agota tokens. El
  TRASPASO al día es lo que hace barato el arranque del siguiente chat.
- App para pensar/decidir (genera el prompt) → Claude Code para tocar archivos →
  de vuelta a la app el RESUMEN (no la sesión entera) para revisar.
- **Flujo git (confirmado esta sesión):** branch ANTES de tocar código (no después,
  o los commits caen en main). Un branch por unidad de trabajo, no por cambio.
  Cambio → npm run dev → si gusta, commit dentro del branch → push → PR en GitHub
  → validar en deploy preview de Vercel → merge → borrar branch (remoto al mergear,
  local con `git branch -d`). DevTools (Ctrl+Shift+M, 375/560px) basta para verificar
  layout móvil.

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
- **Repo:** GitHub JotaLabs/trama (privado, monorepo: un solo .git en raíz).
  /crawler, /web, /supabase/migrations.
- **Migraciones:** van 9. Última: 20260617000009_rls_lectura_stories.

## DÓNDE ESTAMOS — 2026-06-18

**Fase 1 COMPLETA y desplegada.** Crawler solo, web pública, 5 medios.

**Fase 2 EN PRODUCCIÓN (vista + clustering).** Confirmado esta sesión: ya estaba
fusionada a main; rama fase2-historias eliminada. Vive en trama-co.vercel.app/historias
y /historia/[id]. (Se eliminó la contradicción del TRASPASO anterior, que pedía
"fusionar fase2-historias" cuando ya estaba mergeado.)

**Fase 2 clustering COMPLETO y validado** (corre manual, no automatizado).
587 artículos → 20 clústeres / 82 noticias, limpios a ojo. Dos compuertas AND:
peso IDF de entidades compartidas ≥20 Y coseno ≥0.70. 3 scores por artículo
(neutralidad, cobertura, divergencia) en story_articles. Umbrales provisionales
(muestra dominada por un macro-tema; re-verificar con semanas de volumen).

**Ajustes de UI de esta sesión (2026-06-18) — MERGEADOS a main.** Cuatro cambios
Tier 2 en un solo branch (fase2-ajustes-web), vía PR:
- **Nav móvil:** .masthead-nav ahora visible y compacta en <560px (cierra deuda
  del 2026-06-17). Sin hamburguesa ni JS.
- **Jerarquía del nav:** "Historias" primero y destacado como entrada principal;
  "Registro" secundario. NO se cambió la home/raíz ni las rutas (decisión deliberada:
  el Registro sigue siendo la defensa de arranque en frío).
- **/buscar — estado "artículo sin clúster" unificado:** mismo render por texto y
  por URL. Título del artículo prominente, aviso de "sin historia" recortado a una
  frase, se mantiene "ver la nota archivada". Lógica de lookup por URL (4 variantes
  www×slash) intacta.
- **/articulo/[id] — link al clúster:** bloque "Parte de una historia →" al inicio,
  solo si el artículo pertenece a un clúster; nada si no.

### Decisiones de la vista (cerradas, encarnadas en el código)
- **Átomo = `url`**, no el medio ni la captura. Colapsar capturas del mismo url.
- Representante del artículo = última captura (título/scores/es_parcial de ahí).
- "editada" solo si cambió titular o bajada (señal editorial confiable); cambio
  solo de cuerpo → "N capturas", sin afirmar edición.
- es_ancla = OR de capturas (no se recalcula en la vista; es contrato del pipeline).
- Hilo: un nodo por artículo (url), coloreado por medio, ordenado por primera
  captura.
- **Título del feed = artículo de mayor score_neutralidad**, NO stories.titulo.

## PRÓXIMO PASO cuando retomemos
1. **Verificar en producción los 4 ajustes de UI** (especialmente nav móvil real y
   link al clúster en /articulo). Confirmar si el link aparece en capturas viejas o
   solo en el representante (depende de cómo story_articles referencia el article_id
   — pendiente de confirmar).
2. **Arreglo BACKEND del ancla por cobertura** — disparador CUMPLIDO (visible en
   Chalá, ver BITACORA). Fix es backend, no de la vista. Es la deuda más madura.
3. Decisión de automatizar el clustering (solo tras semanas de volumen).
4. Limpieza pendiente: duplicados de capitalización en la raíz (Cierre/CIERRE,
   Arquitectura/ARQUITECTURA) y alinear tintas de ARQUITECTURA §7 con globals.css.
5. Fase 3 más adelante.

## Deudas activas (detalle en BITACORA)
- **Ancla por cobertura elige mal** en clústeres grandes — disparador CUMPLIDO
  (visible en Chalá). Fix es backend, no de la vista.
- **Lookup por URL best-effort** — falla silencioso con variantes AMP/m./canónicas
  inconsistentes. Mitigado parcialmente con las 4 variantes www×slash.

## Fase 2 NO obliga a reconstruir al agregar medios
El clustering opera sobre artículos. Agregar medio = config en outlets; solo se
recalibran umbrales. Validar con 5 medios antes de expandir. Cola: La Silla Vacía
y RTVC (feeds ya verificados, no activados), Colombia+20, Semana, Caracol/W Radio.

## Cómo verificar el estado
- Web vista de Fase 2: trama-co.vercel.app/historias y /historia/[id] (en
  producción). Para desarrollo local: cd web && npm run dev → localhost:3000.
- RLS: `select * from pg_policies where tablename in ('stories','story_articles');`
- Clustering: stories/story_articles tienen filas (20 clústeres).
- Crawler: pestaña Actions en verde.