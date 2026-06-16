-- NOTA: el esquema de stories/story_articles aquí quedó inerte (if not exists sobre tablas preexistentes con otro esquema). Corregido en 000008. 
-- supabase/migrations/20260616000007_fase2_clustering.sql
-- Fase 2: estructuras de clustering. Aditiva: solo agrega columnas/tablas,
-- no toca ni borra nada existente. Preserva la inmutabilidad del archivo.

-- 1) Campos de procesamiento sobre articles (NULL hasta que el pipeline los llene).
--    Idempotencia del backfill: WHERE embedding IS NULL.
alter table articles
  add column if not exists entidades jsonb,
  add column if not exists embedding vector(384);

-- Índice para búsqueda de vecinos por similitud coseno (lo usa el clustering
-- y, en Fase 2 avanzada, el grafo). ivfflat necesita datos para entrenarse;
-- se crea ahora vacío y rinde cuando haya volumen.
create index if not exists idx_articles_embedding
  on articles using ivfflat (embedding vector_cosine_ops) with (lists = 100);

-- 2) Clústeres (historias). Un clúster agrupa snapshots del MISMO hecho.
create table if not exists stories (
  id            bigint generated always as identity primary key,
  titulo        text,                    -- provisional: título del ancla principal
  fecha_inicio  timestamptz,             -- captura más antigua del clúster
  fecha_fin     timestamptz,             -- captura más reciente
  n_articulos   int default 0,
  n_medios      int default 0,           -- medios distintos (señal de relevancia)
  created_at    timestamptz default now()
);

-- 3) Pertenencia artículo→clúster + los tres scores (contrato con la UI, §6).
--    Un artículo puede estar en una sola historia (unique).
create table if not exists story_articles (
  story_id          bigint not null references stories(id) on delete cascade,
  article_id        bigint not null references articles(id) on delete cascade,
  score_neutralidad real,   -- cercanía al centroide (mayor = más central/neutral)
  score_cobertura   real,   -- proporción de entidades del clúster que menciona
  score_divergencia real,   -- distancia al artículo más similar (qué tan único)
  es_ancla          boolean default false,
  primary key (story_id, article_id),
  unique (article_id)       -- un artículo, una historia
);

create index if not exists idx_story_articles_story on story_articles(story_id);

-- NOTA: story_relations (grafo entre clústeres) NO se crea aquí.
-- Es Fase 2 avanzada — se diseña cuando haya clústeres reales que medir.
-- Boceto registrado en BITACORA.md.