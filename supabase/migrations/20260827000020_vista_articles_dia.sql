-- TRAMA — migración 000020
-- Vista articles_dia: articles + columna calculada dia_publicacion.
--
-- POR QUÉ: la línea de tiempo del expediente agrupaba por día de CAPTURA
-- (cuándo corrió nuestro cron) mientras Fase 3 trocea por día de PUBLICACIÓN
-- (el día periodístico). El rediseño del hilo por UNIÓN (ver especificación
-- de la unidad) necesita ese segundo calendario en el frontend, y el guard de
-- medianoche que lo calcula ya vive en el backend (_dia_bogota, analisis_fase3.py)
-- — se replica acá literal, en UN solo lugar del lado del servidor, para no
-- meter una tercera copia de una lógica que ya mordió dos veces (BITACORA
-- 2026-08-22 y 2026-08-26).
--
-- GUARD (idéntico a _dia_bogota):
--   1. fecha = fecha_publicacion, con fecha_captura como respaldo si es NULL.
--   2. Si esa fecha cae en medianoche UTC EXACTA (00:00:00.000000 — la marca de
--      "trafilatura solo trajo fecha, sin hora"), el día se toma TAL CUAL en
--      UTC, sin convertir de zona. Convertir de zona una fecha sin hora le
--      resta el offset de Bogotá (-5h) y la corre al día anterior — el bug
--      medido el 2026-08-22 en el 87,4% del corpus.
--   3. Si trae hora real, se convierte a America/Bogota normalmente.
--
-- SECURITY INVOKER: por defecto una vista en Postgres evalúa RLS con los
-- privilegios del DUEÑO de la vista, no del rol que consulta — el gotcha
-- documentado de Supabase. articles tiene policy "lectura_publica" con
-- using(true) (migración 000002), así que el resultado no cambia hoy, pero
-- se declara explícito para no depender de que esa policy siga siendo
-- incondicional si cambia en el futuro.

create or replace view public.articles_dia
  with (security_invoker = true)
as
select
  a.*,
  case
    when f.fecha is null then null
    when date_trunc('day', f.fecha at time zone 'utc') = (f.fecha at time zone 'utc')
      then (f.fecha at time zone 'utc')::date
    else (f.fecha at time zone 'America/Bogota')::date
  end as dia_publicacion
from public.articles a
cross join lateral (
  select coalesce(a.fecha_publicacion, a.fecha_captura) as fecha
) f;

grant select on public.articles_dia to anon, authenticated;

-- VERIFICACIÓN — correr las 3 ANTES de tocar page.js:

-- 1) La vista no pierde ni duplica filas frente a articles:
--   select (select count(*) from public.articles)      as n_articles,
--          (select count(*) from public.articles_dia)   as n_vista;
--   -> deben ser iguales.

-- 2) El guard de medianoche no corre el día en fecha_publicacion a medianoche
--    UTC exacta (reproduce el resultado ya validado en el backend: BITACORA
--    2026-08-23, "0 de 198 filas con el día corrido"):
--   select id, fecha_publicacion, dia_publicacion
--   from public.articles_dia
--   where fecha_publicacion is not null
--     and date_trunc('day', fecha_publicacion at time zone 'utc')
--         = (fecha_publicacion at time zone 'utc')
--   limit 5;
--   -> dia_publicacion debe ser igual a (fecha_publicacion at time zone 'utc')::date,
--      NUNCA un día antes.

-- 3) La vista es legible por el rol publishable (anon), igual que articles:
--   select relname, relacl from pg_class where relname = 'articles_dia';
--   -> debe incluir el grant de select a anon/authenticated agregado arriba.
