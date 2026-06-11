-- =====================================================================
-- TRAMA — Esquema de base de datos v1.0
-- Fase 1, Paso 1
-- Pegar completo en Supabase → SQL Editor → New query → Run
-- =====================================================================

-- Extensiones necesarias ----------------------------------------------
create extension if not exists "pgcrypto";   -- gen_random_uuid()
create extension if not exists "vector";      -- embeddings (pgvector)

-- =====================================================================
-- MEDIOS
-- El perfil queda reservado desde el día 1 (columnas listas, UI después)
-- =====================================================================
create table outlets (
  id              uuid primary key default gen_random_uuid(),
  slug            text unique not null,          -- 'el-espectador'
  nombre          text not null,
  url_base        text not null,
  rss_url         text,
  -- Perfil (se llena en Fase 3, cada dato necesita fuente citable):
  propietario             text,
  grupo_economico         text,
  ano_fundacion           int,
  linea_editorial_declarada text,
  fuentes_financiacion    text,
  nivel_paywall           text check (nivel_paywall in ('abierto','parcial','duro')),
  notas_perfil            jsonb default '{}'::jsonb,
  created_at      timestamptz default now()
);

-- =====================================================================
-- ARTÍCULOS
-- Regla inmutable: nunca se hace UPDATE sobre contenido_visible ni hash.
-- Si el artículo cambia, se inserta una fila nueva (mismo url, hash distinto).
-- =====================================================================
create table articles (
  id                 uuid primary key default gen_random_uuid(),
  outlet_id          uuid references outlets(id) not null,
  url                text not null,
  titulo             text not null,
  subtitulo          text,
  autor              text,
  fecha_publicacion  timestamptz,
  fecha_captura      timestamptz default now() not null,
  contenido_visible  text,                       -- SOLO lo público, jamás saltar paywall
  es_parcial         boolean default false,      -- true si hay muro de pago
  tipo               text check (tipo in ('noticia','opinion','editorial','analisis','agencia','desconocido')) default 'desconocido',
  hash_sha256        text not null,              -- sha256(titulo|subtitulo|contenido_visible)
  entidades          jsonb default '[]'::jsonb,  -- ["Petro","Fiscalía",...] (Fase 2)
  embedding          vector(384),                -- (Fase 2)
  -- Un mismo url puede tener N filas SIEMPRE que el hash difiera.
  -- Una re-captura idéntica (mismo url + mismo hash) es rechazada por esta unique.
  unique (url, hash_sha256)
);

create index idx_articles_outlet      on articles(outlet_id);
create index idx_articles_url         on articles(url);
create index idx_articles_fecha_cap   on articles(fecha_captura desc);

-- =====================================================================
-- HISTORIAS (clústeres) — estructura lista, se usa en Fase 2
-- =====================================================================
create table stories (
  id                 uuid primary key default gen_random_uuid(),
  titulo_descriptivo text not null,
  fecha_evento       date,
  articulo_origen_id uuid references articles(id),
  estado             text default 'auto' check (estado in ('auto','revisado','dudoso')),
  created_at         timestamptz default now()
);

create table story_articles (
  story_id   uuid references stories(id) on delete cascade,
  article_id uuid references articles(id) on delete cascade,
  similitud  float,
  primary key (story_id, article_id)
);

-- =====================================================================
-- ANÁLISIS DE PERSUASIÓN — estructura lista, se usa en Fase 3
-- =====================================================================
create table analyses (
  id              uuid primary key default gen_random_uuid(),
  article_id      uuid references articles(id) unique not null,
  story_id        uuid references stories(id),
  tecnicas        jsonb not null default '[]'::jsonb,
  omisiones       jsonb default '[]'::jsonb,
  resumen_neutral text,
  modelo          text not null,
  created_at      timestamptz default now()
);

-- =====================================================================
-- LOG DE AUDITORÍA — espejo en BD de lo que va al repo Git público
-- =====================================================================
create table audit_log (
  id          bigserial primary key,
  article_id  uuid references articles(id),
  hash_sha256 text not null,
  git_commit  text,
  created_at  timestamptz default now()
);

-- =====================================================================
-- SEMILLA: los 5 medios de la estructura central (Fase 1)
-- El rss_url se confirma con el script verificar_feeds.py antes de usar.
-- Déjalos en NULL si el feed aún no está confirmado.
-- =====================================================================
insert into outlets (slug, nombre, url_base, nivel_paywall) values
  ('voragine',      'Vorágine',      'https://voragine.co',          'abierto'),
  ('las2orillas',   'Las2orillas',   'https://www.las2orillas.co',   'abierto'),
  ('el-espectador', 'El Espectador', 'https://www.elespectador.com', 'parcial'),
  ('el-tiempo',     'El Tiempo',     'https://www.eltiempo.com',     'parcial'),
  ('el-colombiano', 'El Colombiano', 'https://www.elcolombiano.com', 'parcial');

-- Verificación rápida
select slug, nombre, nivel_paywall from outlets order by nombre;
