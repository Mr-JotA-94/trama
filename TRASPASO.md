# TRAMA — Estado del proyecto (traspaso a nueva sesión)

> Dáselo a un chat nuevo para retomar sin releer conversaciones. Léelo junto con
> ARQUITECTURA.md (plan completo) y BITACORA.md (decisiones y deuda).
> Última actualización: **2026-06-27**.

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
  Vercel → trama-co.vercel.app. CSS global en globals.css (tokens en :root:
  --tinta/--papel/--hilo/--resaltador/--verificado/--gris-archivo, fuentes --f-mono/--f-ui).
  Caché: feed revalidate 300s, artículos 3600s. /historias es dinámico por request.
- **Repo:** GitHub Mr-JotA-94/trama (privado, monorepo). /crawler, /web, /supabase/migrations.
- **Migraciones:** van 10. Última: 20260625000010_story_relations. (Esta sesión NO añadió
  migración: la recalibración de relaciones es lógica derivada, sin cambio de esquema.)
- **CI:** workflow `crawler.yml` con TRES jobs encadenados: crawl (6h) → backfill
  (needs:crawl) → clustering (needs:backfill).

## DÓNDE ESTAMOS — 2026-06-27

**Fase 1 COMPLETA y desplegada.** Crawler, web pública, 5 medios.

**Fase 2 EN PRODUCCIÓN.** Vista + clustering + feed paginado + **grafo de historias
conectadas EXPUESTO**. trama-co.vercel.app/historias y /historia/[id].

**PIPELINE AUTOMATIZADO Y ARCHIVANDO.** Tres jobs CI en cadena.

**RELACIONES RECALIBRADAS SOBRE NER LIMPIO (2026-06-27).** El criterio de story_relations
se arregló de raíz: el problema no era n_especificas sino QUÉ cuenta como específica.
Tres capas nuevas en la 2ª pasada de clustering_fase2.py — (1) canon()+ALIAS (dedup de
formas de superficie: "la procuraduría"/"procuraduría general" = 1 referente; siglas↔
expansión), (2) GEO_EXTRA (geografía extranjera al filtro, antes solo Colombia), (3)
FRAC_GENERICA 0.15→0.08 (instituciones recurrentes se vuelven genéricas por DF). Medido:
191→68 aristas, hub Pastrana grado 21→3, andamiaje electoral eliminado (control = 0 pares
con {defensores de la patria, registraduría, donald trump}). CORE intacto (Troncal,
Calavera↔24, Arizabaleta, Beto Coral). Piso = Calavera↔24 (rompe en 0.06, por eso 0.08 es
el límite). **n_esp≥3 y guardia coseno 0.50 NO se movieron.** Validado en producción tras
correr clustering: ~101 pares / 202 filas espejo (crecimiento real: terremoto Venezuela +
formación de gabinete), Pastrana grado 4, control de andamiaje = 0.
Branch: **fix/relaciones-canon-frac008**.

**GRAFO EXPUESTO EN EL FRONT (2026-06-27).** /historia/[id]/page.js: el placeholder de
"Historias conectadas" se reemplazó por la vista real. Q3 a story_relations filtrando por
origen_id (espejo dirigido completo → sin duplicar), trae hasta 50, render muestra **5
cards principales** (orden n_especificas desc, coseno desc) + `<details>` "y N más". Es CAP
DE PRESENTACIÓN: Uribe conserva sus 13 filas en tabla, la vista muestra 5. Server Component,
cero JS de cliente. UI adicional en la misma página: hilo cronológico con 3 primeras
visibles + resto en `<details>`, versiones secundarias con 2 visibles + resto en `<details>`,
fade por máscara de gradiente activo solo en estado colapsado (selector [open]), conectadas
movidas al final. Branch UI: **feat/timeline-colapsable-reordenar**.

**Banco:** ~2700+ artículos embebidos (entidades limpias post re-backfill), 149 stories activas.

**ÁTOMO = URL, UUID ESTABLE, ANCLA, FEED↔TÍTULO-CITA, FEED PAGINADO, NER LIMPIO** — vigente.

## PRÓXIMO PASO cuando retomemos
1. **CONFIRMAR MERGES Y QUE EL CRON CORRE FRAC=0.08 (urgente, no opcional).** La
   recalibración vive en branch fix/relaciones-canon-frac008; el front lee lo que haya en
   story_relations. Si el cron de clustering corre todavía con FRAC=0.15, la próxima corrida
   RE-CONTAMINA el grafo en vivo. Verificar: ambos branches mergeados a main, y que el job
   `clustering` ejecuta la versión con canon/geo/FRAC=0.08. Aplicar el toggle "ver menos"
   pendiente del hilo/versiones si se decidió.
2. **Recalibrar centroide-por-medio ANTES de activar medios nuevos** (constraint de
   secuencia bloqueado). El centroide no ponderado sesga neutralidad por volumen.
3. **Activar La Silla Vacía / RTVC** (feeds verificados) tras el diagnóstico de centroide.
   Al activar: agregar su nombre a MEDIOS en ner_filtro.py.
4. Fase 3 (LLM decidido: NVIDIA NIM).

## Deudas activas (detalle en BITACORA)
- **Air-e = falso negativo MEDIDO de relaciones** (2026-06-27) — solo comparte 2 específicas
  limpias (andeg + superservicios), cae bajo n_esp≥3. Decidido NO bajar a 2 (reabre la
  co-mención institucional del hub). FN aceptado, como Beto Coral lo fue para la guardia.
- **Retirar RUIDO_DURO sigue BLOQUEADO** (medido 2026-06-27) — 9/50 términos sobreviven al
  NER limpio (incl. "match electoral de el espectador", "el presidente de estados unidos").
  Retirarlo re-contaminaría. Disparador: mejor filtro de NER de cuerpo, no antes.
- **Cap de in-degree en lectura → SUPERSEDIDO para la vista per-historia.** El cap de
  presentación (top-5 + "ver más") ya contiene la densidad visual. Solo vuelve a hacer falta
  SI se construye un grafo panorámico de fuerza (no es el caso hoy).
- **tipo_relacion (contexto vs seguimiento vs hecho)** → Fase 3. Confirmado que pares de
  contexto (Cauca, US/Venezuela) sobreviven a 0.08 como relaciones reales pero sin tipar.
- **Writes masivos uno-por-uno frágiles** (2026-06-26, OBSERVADO).
- **Robustez delete-then-insert del clustering** (2026-06-23) — cubre también story_relations.
- **Dependencias de clustering/backfill sin pin** (2026-06-23).
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
- Web Fase 2: trama-co.vercel.app/historias y /historia/[id] (grafo de conectadas visible).
- Pipeline CI: Actions → "crawler" con TRES jobs en verde y en cadena.
- Recalibración viva: clustering en producción produce ~100 pares (no ~190); query de
  control sobre entidades_compartidas con {defensores de la patria, registraduría,
  donald trump} debe dar 0 pares.
- Cap de presentación: historia hub (Uribe) muestra 5 cards + "y N más", legible en mobile.
- UUID estable: clustering 2× sin cambiar datos → misma huella md5 de string_agg.