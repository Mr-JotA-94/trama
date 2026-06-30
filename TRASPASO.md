# TRAMA — Estado del proyecto (traspaso a nueva sesión)

> Dáselo a un chat nuevo para retomar sin releer conversaciones. Léelo junto con
> ARQUITECTURA.md (plan completo) y BITACORA.md (decisiones y deuda).
> Última actualización: **2026-06-29** (post-verificación La Silla Vacía).


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

**INCIDENTE CI CLUSTERING — RESUELTO Y PUSHEADO, PIPELINE VERDE (2026-06-28).**
`6e25379` ("cambios regulares diarios de los md file") añadió `RUIDO_C`/`GEO_C` antes
de `def canon` (→ NameError en import) Y cambió `es_especifica` a membership canonizada
(cambio semántico NO medido). story_relations no se corrompió (crash en import).
**Fix: restauración exacta a 9410713 (`fix/clustering-restore-validado`, ce4af7f)** —
elimina `RUIDO_C`/`GEO_C`, revierte `es_especifica` a crudo. Mergeado y **pusheado a
origin/main**. Cron verde confirmado (corrida real: 165 clústeres, 128 pares). Se
descartó el reorden 91c8c78 porque conservaba el cambio no validado; lo cazó el diff
contra 9410713 (detalle en BITACORA).

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
- **IMPLEMENTADO Y VALIDADO (2026-06-28).** `centroide_neutralidad` añadida; `calcular_scores`
  conmutado a ella; relaciones intacta (PASADA 2 sigue en `centroide_de_cluster`). Validación
  sobre prod: **relaciones NO se movió (128 pares)** y las 23 anclas se de-sesgaron — Trump/Irán
  pasó a Las2orillas, Niño Guerrero a El Colombiano (prueba directa de que medios de bajo volumen
  ganan ancla). Costo medido y aceptado: ~5 clústeres pequeños pierden cobertura de ancla (deuda
  abajo). **Branch `fix/centroide-neutralidad-split`. PENDIENTE: merge a main + push** — el cron
  corre main; si no se mergea, la próxima corrida revierte los scores y re-sesga La Silla Vacía.

**Banco:** ~2700+ artículos embebidos (entidades limpias post re-backfill). ~149 stories
en la corrida 2026-06-27 (ver nota de conteo en el diagnóstico de centroide arriba; el
conteo exacto es el de la última corrida verde del cron).

**LA SILLA VACÍA ACTIVADA, VERIFICADA Y CONFIABLE (2026-06-29).** 6º medio, archivando en prod
(cron verde). Config validada sobre datos capturados reales: `extraccion='trafilatura'`,
`nivel_paywall='abierto'` (es_parcial=false en todas), `regla_seccion={"metodo":"primer_segmento"}`
(en-vivo→`en-vivo`, red-de-expertos→`null` por guard de 2-guiones, como se predijo).
**Verificación concluyente:** el footer de Cruz Roja (RCF) y el disclaimer de opinión NO son
boilerplate — son contenido editorial legítimo (servicio de Restablecimiento de Contactos Familiares
en cobertura de desastre; disclaimer propio de columnas de opinión). Archivarlos es coherente con
"archivar lo públicamente visible". Unidad CERRADA, sin pendientes. RTVC NO activado (ver cola).

**ÁTOMO = URL, UUID ESTABLE, ANCLA, FEED↔TÍTULO-CITA, FEED PAGINADO, NER LIMPIO** — vigente.

## PRÓXIMO PASO cuando retomemos

>>> La Silla Vacía cerrada (verificada y confiable, 2026-06-29). Sin pendientes abiertos de Fase 2.

1. **RTVC — activación (unidad aparte).** Trafilatura/abierto, pero diag midió 20% de ruido
   (boilerplate de navegación sin og:title, descartado por keep=NO) y el feed RSS solo expone 10
   ítems. Antes de activar: muestra por sitemap (no el RSS de 10) y confirmar que keep=sí no traen
   cola de boilerplate. Posible filtro extra como el de video de El Tiempo.

2. **Fase 3 (LLM: NVIDIA NIM / llama-3.3-70b / Groq fallback).** Tras activar RTVC (banco de 7
   medios) para que el batch LLM corra una vez sobre el set completo.

## Deudas activas (detalle en BITACORA)

>>> CAMBIO: se añaden las deudas del incidente y del diagnóstico de centroide.

- **[RESUELTO Y PUSHEADO] Job clustering roto en main** (2026-06-28) — 6e25379 (RUIDO_C/GEO_C
  + es_especifica). Fix `ce4af7f` (restauración a 9410713), en origin/main, cron verde.
- **[RESUELTO Y PUSHEADO] Centroide-por-medio (SPLIT)** (2026-06-29) — `centroide_neutralidad`
  validada (128 pares intactos, 23 anclas de-sesgadas), mergeada a main, Actions verde.
- **[NUEVA] Varianza de ancla en clústeres pequeños bajo un-voto** (2026-06-28) — el split hace
  perder cobertura de ancla en ~5 clústeres de 3-4 artículos (un-voto promedia 2-3 puntos, más
  ruidoso). Aceptado: clústeres de bajo tráfico. Disparador si molesta: medir una guarda de tamaño N.
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

>>> Ideas de la sesión 2026-06-28/29:
- **Texto de servicio idéntico entre notas (footer RCF, disclaimer de opinión)** — VIGILANCIA, no
  acción. Es contenido legítimo, se archiva. Solo si algún día liga clústeres NO relacionados por
  texto compartido, medir; hoy queda bajo el gate n_especificas≥3, sin evidencia de cruce.
- **La Silla Vacía: opinión vs reportería.** `/red-de-expertos/` es columna de opinión, no
  noticia (ej. "espacio de debate que no compromete la opinión de La Silla Vacía"). A futuro,
  filtro de sección para separarla. Además `red-de-expertos` (2 guiones) cae a sección=null
  por el guard de `primer_segmento` (≤1 guion) — refinar la regla si se quiere capturar esa sección.
- **RTVC: feed RSS limitado a 10 ítems + boilerplate.** Su `rss.xml` solo expone 10; para
  cobertura real hace falta su sitemap. Y 20% de la muestra fue chrome de navegación.


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
