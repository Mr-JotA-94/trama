-- Migración: supabase/migrations/20260611000002_rls_lectura_publica.sql

-- Habilitar RLS en todas las tablas
alter table outlets        enable row level security;
alter table articles       enable row level security;
alter table stories        enable row level security;
alter table story_articles enable row level security;
alter table analyses       enable row level security;
alter table audit_log      enable row level security;

-- Política única por tabla: lectura pública, escritura para nadie
-- (el crawler escribe con service_role, que ignora RLS)
create policy "lectura_publica" on outlets        for select using (true);
create policy "lectura_publica" on articles       for select using (true);
create policy "lectura_publica" on stories        for select using (true);
create policy "lectura_publica" on story_articles for select using (true);
create policy "lectura_publica" on analyses       for select using (true);
create policy "lectura_publica" on audit_log      for select using (true);