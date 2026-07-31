-- Fase 3 v1: comparación inter-medio (por par) + resumen (por clúster).
-- NOTA: esta migración YA fue aplicada a mano en Supabase. Este archivo es el
-- espejo documental (regla de doble migración). NO re-ejecutar: fallaría.
-- La tabla analyses previa (carril per-artículo, cerrado) estaba vacía: eliminada.
drop table if exists analyses;

create table comparaciones (
  id uuid primary key default gen_random_uuid(),
  hash_a text not null,
  hash_b text not null,
  article_a uuid references articles(id) on delete set null,
  article_b uuid references articles(id) on delete set null,
  diferencias jsonb not null default '[]'::jsonb,
  es_mismo_hecho boolean not null,
  divergencia_relevante boolean not null,
  desfase_temporal text,
  modelo text not null,
  prompt_version text not null,
  created_at timestamptz not null default now(),
  constraint comparaciones_par_uniq unique (hash_a, hash_b),
  constraint comparaciones_orden check (hash_a < hash_b)
);
create index comparaciones_article_a_idx on comparaciones(article_a);
create index comparaciones_article_b_idx on comparaciones(article_b);

create table resumenes (
  id uuid primary key default gen_random_uuid(),
  cluster_key text not null unique,
  story_id uuid references stories(id) on delete set null,
  article_ids uuid[] not null,
  member_hashes text[] not null,
  hechos_corroborados jsonb not null default '[]'::jsonb,
  solo_un_medio jsonb not null default '[]'::jsonb,
  sintesis text,
  modelo text not null,
  prompt_version text not null,
  created_at timestamptz not null default now()
);
create index resumenes_story_id_idx on resumenes(story_id);
