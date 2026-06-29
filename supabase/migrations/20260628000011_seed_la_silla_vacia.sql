insert into outlets (slug, nombre, url_base, nivel_paywall, extraccion, regla_seccion, fuentes)
select 'la-silla-vacia', 'La Silla Vacía', 'https://www.lasillavacia.com',
       'abierto', 'trafilatura',
       '{"metodo":"primer_segmento"}'::jsonb,
       '[{"url":"https://www.lasillavacia.com/feed/","tipo":"rss"}]'::jsonb
where not exists (select 1 from outlets where slug = 'la-silla-vacia');