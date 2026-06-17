-- 20260617000009_rls_lectura_stories.sql
-- Abre lectura pública a las tablas de clustering (Fase 2), igual que
-- articles/outlets. RLS ya estaba activo pero sin policy de SELECT, así que
-- la clave publishable veía cero filas sin error. La escritura sigue siendo
-- solo del crawler con clave secreta (ignora RLS); esto solo habilita lectura.

create policy lectura_publica on public.stories
  for select to public using (true);

create policy lectura_publica on public.story_articles
  for select to public using (true);