-- 20260625000010_story_relations.sql
-- Fase 2 avanzada — grafo de historias relacionadas (clúster <-> clúster).
--
-- story_relations = CACHÉ DERIVADA PURA: se borra y se recomputa en cada corrida del
-- clustering, junto a stories/story_articles. NO es estado. NO toca articles (inmutable).
--
-- MODELO: DIRIGIDO-ESPEJO. Cada par relacionado produce DOS filas (A->B y B->A) con
-- los mismos n_especificas / coseno / entidades_compartidas. Razones:
--   (1) el cap de grado en lectura es "top-K vecinos de la historia foco" =
--       WHERE origen_id = X ORDER BY n_especificas DESC LIMIT K, con índice limpio;
--   (2) la semántica de Fase 3 (derivada / reacción) es dirigida — esta forma la
--       admite sin rediseño (solo se añadirá la dirección, no se reestructura).
--   El coste 2x en filas es trivial: tabla diminuta y derivada.
--
-- tipo_relacion NO se incluye a propósito (decisión 2026-06-25): la tabla se vacía
-- cada corrida; una anotación de LLM (Fase 3) se borraría en la siguiente. Cuando
-- llegue, vivirá en tabla aparte no-volátil (como analyses es aparte de articles), o
-- la relación ganará identidad estable. Disparador registrado en BITACORA.
--
-- NOTA: sin IF NOT EXISTS en tabla load-bearing (lección migración 000007: el create
-- inerte falla en silencio). Si la tabla ya existe, este create DEBE fallar y avisar.

create table story_relations (
  origen_id             uuid    not null references stories(id) on delete cascade,
  destino_id            uuid    not null references stories(id) on delete cascade,
  n_especificas         integer not null,   -- MOTOR: entidades específicas compartidas (rareza ya limpia)
  coseno                real    not null,    -- GUARDIA: coseno entre centroides (valor que pasó el umbral)
  entidades_compartidas jsonb   not null,    -- EVIDENCIA: qué entidades ligan el par (auditable + UI)
  created_at            timestamptz not null default now(),
  primary key (origen_id, destino_id),
  check (origen_id <> destino_id)            -- sin auto-lazos
);

-- Sirve el cap de lectura: vecinos de X ordenados por fuerza, sin escaneo.
-- (Bajo aristas-espejo, in-degree(X) == out-degree(X), así que este índice basta
--  para fan-out por foco; no se añade índice sobre destino_id hasta que un query lo pida.)
create index idx_story_relations_origen_fuerza
  on story_relations (origen_id, n_especificas desc);

-- RLS: la web lee con clave publishable. Tabla nueva con RLS necesita policy de
-- SELECT explícita, o la web ve CERO filas en silencio (lección migración 000009).
-- La escritura sigue siendo solo del clustering con clave secreta (ignora RLS).
alter table story_relations enable row level security;

create policy lectura_publica on story_relations
  for select to public using (true);
