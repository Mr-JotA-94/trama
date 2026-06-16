-- supabase/migrations/20260616000008_corregir_esquema_stories.sql
-- La base tenía stories/story_articles de un boceto previo, con esquema que NO
-- corresponde al contrato de Fase 2. La 000007 no las recreó por su 'if not exists'.
-- Esta migración las reemplaza por el esquema correcto. Las tablas no tienen datos
-- de valor (clustering nunca escribió). NO toca articles (archivo inmutable intacto).

drop table if exists story_articles cascade;
drop table if exists stories cascade;

create table stories (
  id            uuid primary key default gen_random_uuid(),
  titulo        text,
  fecha_inicio  timestamptz,
  fecha_fin     timestamptz,
  n_articulos   int default 0,
  n_medios      int default 0,
  created_at    timestamptz default now()
);

create table story_articles (
  story_id          uuid not null references stories(id) on delete cascade,
  article_id        uuid not null references articles(id) on delete cascade,
  score_neutralidad real,
  score_cobertura   real,
  score_divergencia real,
  es_ancla          boolean default false,
  primary key (story_id, article_id),
  unique (article_id)
);

create index idx_story_articles_story on story_articles(story_id);