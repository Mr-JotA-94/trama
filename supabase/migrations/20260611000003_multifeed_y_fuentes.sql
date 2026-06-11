-- =====================================================================
-- TRAMA — Migración 3: multi-feed por medio + feeds confirmados
-- Archivo: supabase/migrations/20260611000003_multifeed_y_fuentes.sql
-- Razón: El Tiempo tiene 3 feeds RSS válidos de 10 ítems cada uno;
--        un solo rss_url perdería cobertura. El Espectador no tiene
--        RSS funcional y entrará por sitemap (tipo de fuente distinto).
-- =====================================================================

-- Nueva columna: lista de fuentes, cada una con tipo y url
alter table outlets add column fuentes jsonb default '[]'::jsonb;

-- Migrar los feeds confirmados por verificar_feeds.py (2026-06-11)
update outlets set fuentes = '[{"tipo":"rss","url":"https://voragine.co/feed/"}]'::jsonb
  where slug = 'voragine';

update outlets set fuentes = '[{"tipo":"rss","url":"https://www.las2orillas.co/feed/"}]'::jsonb
  where slug = 'las2orillas';

update outlets set fuentes = '[
  {"tipo":"rss","url":"https://www.eltiempo.com/rss/colombia.xml"},
  {"tipo":"rss","url":"https://www.eltiempo.com/rss/politica.xml"},
  {"tipo":"rss","url":"https://www.eltiempo.com/rss/justicia.xml"}
]'::jsonb
  where slug = 'el-tiempo';

update outlets set fuentes = '[{"tipo":"rss","url":"https://www.elcolombiano.com/rss/colombia.xml"}]'::jsonb
  where slug = 'el-colombiano';

-- El Espectador: sin RSS confirmado. Candidatos de sitemap a verificar
-- desde tu máquina (el crawler los prueba en orden y usa el primero válido).
update outlets set fuentes = '[
  {"tipo":"sitemap","url":"https://www.elespectador.com/arc/outboundfeeds/news-sitemap/?outputType=xml"},
  {"tipo":"sitemap","url":"https://www.elespectador.com/sitemap/news.xml"},
  {"tipo":"sitemap","url":"https://www.elespectador.com/sitemap.xml"}
]'::jsonb
  where slug = 'el-espectador';

-- La columna vieja queda obsoleta; no se borra (historial), no se usa más.
comment on column outlets.rss_url is 'OBSOLETA desde migración 3. Usar columna fuentes.';

-- Verificación
select slug, jsonb_array_length(fuentes) as num_fuentes from outlets order by slug;
