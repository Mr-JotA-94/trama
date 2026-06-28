# TRAMA — Estado del proyecto (traspaso a nueva sesión)

> Dáselo a un chat nuevo para retomar sin releer conversaciones. Léelo junto con
> ARQUITECTURA.md (plan completo) y BITACORA.md (decisiones y deuda).
> Última actualización: **2026-06-28**.
> >>> CAMBIO: fecha actualizada de 2026-06-27 a 2026-06-28.

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
- **Migraciones:** van 10. Última: 20260625000010_story_relations.
- **CI:** workflow `crawler.yml` con TRES jobs encadenados: crawl (6h) → backfill
  (needs:crawl) → clustering (needs:backfill).

## DÓNDE ESTAMOS — 2026-06-28

**Fase 1 COMPLETA y desplegada.** Crawler, web pública, 5 medios.

**Fase 2 EN PRODUCCIÓN.** Vista + clustering + feed paginado + **grafo de historias
conectadas EXPUESTO**. trama-co.vercel.app/historias y /historia/[id].

**PIPELINE AUTOMATIZADO Y ARCHIVANDO.** Tres jobs CI en cadena.

**RELACIONES RECALIBRADAS SOBRE NER LIMPIO (2026-06-27) — EN MAIN.**
>>> CAMBIO: el TRASPASO anterior decía "Branch: fix/relaciones-canon-frac008" como
pendiente de merge. Confirmado: ese contenido está en main desde commit 9410713
(push directo, no PR). No hay branch pendiente de merge para la recalibración.
Tres capas: canon()+ALIAS, GEO_EXTRA, FRAC=0.08. Medido: 191→68 aristas, hub
Pastrana grado 21→3, andamiaje=0. CORE intacto. n_esp≥3 y guardia 0.50 intactos.

**GRAFO EXPUESTO EN EL FRONT (2026-06-27).**
/historia/[id]/page.js: top-5 conectadas (n_especificas desc, coseno desc) +
`<details>` "y N más". Server Component, cero JS. Hilo colapsable (3+resto),
versiones (2+resto), fade con gradiente en estado colapsado.

**>>> CAMBIO: INCIDENTE CI CLUSTERING — RESUELTO EN MAIN LOCAL, PENDIENTE PUSH (2026-06-28).**
El job `clustering` del cron falló con NameError. Causa raíz: commit **6e25379**
("cambios regulares diarios de los md file") hizo DOS cosas sobre la versión validada
9410713: añadió `RUIDO_C`/`GEO_C` como comprehensions de módulo antes de `def canon`
(→ NameError en import) Y cambió `es_especifica` a membership canonizada (cambio
semántico al motor de relaciones, NO medido). **story_relations NO se corrompió** (el
crash es en import, antes del delete de `reescribir_stories`). Grafo congelado en la
última corrida válida. **Fix: `fix/clustering-restore-validado` (commit ce4af7f) —
restauración exacta a 9410713** (`git checkout 9410713 -- ...`): elimina `RUIDO_C`/
`GEO_C`, revierte `es_especifica` a crudo. Mergeado a main LOCAL por fast-forward.
**PENDIENTE: `git push origin main`** (origin sigue en 6e25379 roto). Se descartó el
reorden 91c8c78 porque conservaba el cambio no validado de `es_especifica`; lo cazó el
diff contra 9410713 (detalle en BITACORA).

**>>> CAMBIO: DIAGNÓSTICO DE CENTROIDE-POR-MEDIO REALIZADO.**
El TRASPASO anterior lo listaba como "próximo paso pendiente". Ya medido sobre
161 clústeres válidos con 2+ medios (snapshot live 2026-06-28; difiere del ~149 del
2026-06-27 porque el clustering corre cada 6h entre ambas mediciones):
- **64 clústeres (40%)** tienen desbalance intra-medio (algún medio aporta >1 artículo
  al clúster, con ≥2 medios presentes — los casos donde un-voto-por-medio difiere del
  voto-por-artículo; en el 60% restante el centroide no cambia).
- **22 clústeres (14%)** cambian de ancla principal bajo centroide un-voto-por-medio.
- **Sesgo DIRECCIONAL confirmado:** El Tiempo (Δ −0.0087), El Colombiano (−0.0025),
  El Espectador (−0.0016) — alto volumen, neutralidad inflada por el centroide actual.
  Las2orillas (+0.0263) — bajo volumen, neutralidad suprimida.
- **Conclusión: el fix se justifica.** 14% de anclas cambiando es impacto real.
- **Enfoque decidido (SPLIT):** nueva `centroide_neutralidad` (un-voto-por-medio) solo
  para `calcular_scores`; `centroide_de_cluster` (voto-por-artículo) se queda intacta
  para la guardia coseno de relaciones (su calibración FRAC=0.08/guardia=0.50 se hizo
  contra ese centroide; moverla es otra unidad medida por separado).
- **NO implementado aún** — es la próxima unidad de trabajo tras resolver el incidente.

**Banco:** ~2700+ artículos embebidos (entidades limpias post re-backfill). ~149 stories
en la corrida 2026-06-27 (ver nota de conteo en el diagnóstico de centroide arriba; el
conteo exacto es el de la última corrida verde del cron).

**ÁTOMO = URL, UUID ESTABLE, ANCLA, FEED↔TÍTULO-CITA, FEED PAGINADO, NER LIMPIO** — vigente.

## PRÓXIMO PASO cuando retomemos

>>> CAMBIO: lista reordenada y actualizada. El #1 anterior ("CONFIRMAR MERGES") se
resolvió parcialmente (9410713 ya está en main) pero fue reemplazado por el incidente.

1. **URGENTE — `git push origin main`.** El fix (ce4af7f) está mergeado en main LOCAL
   pero origin sigue en 6e25379 (roto); el cron corre origin cada 6h y seguirá fallando
   hasta el push. Tras pushear, la próxima corrida restaura story_relations y el grafo
   del front vuelve al estado vivo. Verificar que el cron siguiente completa los tres
   jobs en verde. ANTES del `git add` de docs: sacar `diag_centroide_por_medio.py` de
   `crawler/` y añadir `crawler/diag_*.py` a `.gitignore` (sigue untracked en el árbol).

2. **Implementar centroide-por-medio (SPLIT)** — diagnóstico hecho, decisión tomada,
   unidad de trabajo lista. Cambio en `calcular_scores`: añadir `centroide_neutralidad`
   (un-voto-por-medio) para elegir el ancla; `centroide_de_cluster` no se toca.
   Re-validar a ojo las 22 historias donde cambia el ancla. Hacerlo ANTES de activar
   medios nuevos (más volumen asimétrico agrava el sesgo).

3. **Activar La Silla Vacía / RTVC** (feeds verificados) tras el centroide-por-medio.
   Al activar: agregar su nombre a MEDIOS en ner_filtro.py.

4. Fase 3 (LLM decidido: NVIDIA NIM).

## Deudas activas (detalle en BITACORA)

>>> CAMBIO: se añaden las deudas del incidente y del diagnóstico de centroide.

- **[RESUELTO local, pendiente push] Job clustering roto en main** (2026-06-28) —
  6e25379 añadió `RUIDO_C`/`GEO_C` mal ordenados (NameError) + cambió `es_especifica`
  a canonizada (no validado). Fix por restauración a 9410713: `fix/clustering-restore-validado`
  (ce4af7f). Falta `git push origin main`.
- **[NUEVA] Canonizar exclusión de `es_especifica` — mejora SIN MEDIR** (2026-06-28) —
  revertida en el incidente; reintroducir solo con medición (aristas/hub vs 68 validadas).
- **Centroide-por-medio (SPLIT) no implementado** (diagnóstico 2026-06-28) — 22 anclas
  cambian, sesgo en El Tiempo/Colombiano/Espectador. Próxima unidad de trabajo.
- **Air-e = falso negativo MEDIDO de relaciones** (2026-06-27) — FN aceptado.
- **Retirar RUIDO_DURO sigue BLOQUEADO** (medido 2026-06-27) — 9/50 términos
  sobreviven al NER limpio. Disparador: mejor filtro de NER de cuerpo.
- **Cap de in-degree en lectura → SUPERSEDIDO para la vista per-historia.**
  Solo vuelve a hacer falta si se construye un grafo panorámico.
- **tipo_relacion (contexto vs seguimiento vs hecho)** → Fase 3.
- **Writes masivos uno-por-uno frágiles** (2026-06-26, OBSERVADO).
- **Robustez delete-then-insert del clustering** (2026-06-23) — cubre story_relations.
- **Dependencias de clustering/backfill sin pin** (2026-06-23).
- **Búsqueda no paginada** (2026-06-21).
- **Doble-cómputo de título** (2026-06-21) — backend vs frontend, hoy coinciden.
- **Titular-cita ancla clústeres** — MITIGADA en display. Scoring NO tocado.
- **Lookup por URL best-effort** — falla silencioso con variantes AMP/m./canónicas.

## Notas de consistencia docs↔código (auditoría 2026-06-28)

>>> CAMBIO: sección nueva. No editar Arquitectura.md sin que Jota lo decida.

Dos discrepancias STALE encontradas (no bloquean trabajo, pero leer con conciencia):

1. **Arquitectura.md §6** dice "Grafo poblado pero NO expuesto hasta el re-backfill de
   NER". **Desactualizado**: re-backfill aplicado 2026-06-26, grafo expuesto 2026-06-27.
   El estado real está en este TRASPASO; Arquitectura.md queda por actualizar (Jota decide).

2. **BITACORA "Notas de operación" (2026-06-23)** dice "El clustering NO está en este
   workflow (sigue manual)". **Desactualizado**: el clustering ES el 3er job del
   workflow desde commit 3560565. La nota era correcta cuando se escribió.

## Ideas registradas (no son scope ahora)

>>> CAMBIO: sección nueva con dos ideas de esta sesión.

- **Vorágine ausente del diagnóstico cross-coverage del centroide** — no apareció en
  ningún clúster con desbalance notable en el diagnóstico de centroide-por-medio.
  Hipótesis: gap real de cobertura del investigativo independiente (bajo volumen de
  noticias de último minuto) o artefacto del join del diagnóstico. A medir aparte;
  no actuar sin datos.

- **Segundo "ver menos" al final del hilo/versiones** — el toggle `<summary>` nativo
  queda arriba al desplegar. Un botón abajo requeriría JS de cliente; se difiere para
  no romper el principio cero-JS. Si el contenido largo molesta volver arriba, la señal
  es que ESE clúster necesita destilado.

## Fase 2 NO obliga a reconstruir al agregar medios
El clustering opera sobre artículos. Agregar medio = config en outlets; solo se
recalibran umbrales. Cola: La Silla Vacía y RTVC (feeds verificados, no activados).
Al activar un medio nuevo: agregar su nombre a MEDIOS en ner_filtro.py.

LLM de Fase 3 DECIDIDO (2026-06-19): NVIDIA NIM hosted, meta/llama-3.3-70b-instruct,
cliente swappable, Groq fallback.

## Cómo verificar el estado

>>> CAMBIO: añadido check del incidente.

- **PRIMERO: verificar que el cron post-merge completa en verde** (los tres jobs).
  Si clustering falla aún, revisar que el merge de fix/clustering-canon-order llegó
  a main antes de que corriera el cron.
- Web Fase 2: trama-co.vercel.app/historias y /historia/[id] (grafo de conectadas visible).
- Pipeline CI: Actions → "crawler" con TRES jobs en verde y en cadena.
- Recalibración viva: clustering produce ~100 pares (no ~190); query de control sobre
  entidades_compartidas con {defensores de la patria, registraduría, donald trump}
  debe dar 0 pares.
- Cap de presentación: historia hub (Uribe) muestra 5 cards + "y N más", legible en mobile.
- UUID estable: clustering 2× sin cambiar datos → misma huella md5 de string_agg.
