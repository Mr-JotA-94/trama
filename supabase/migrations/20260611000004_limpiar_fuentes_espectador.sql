-- supabase/migrations/20260611000004_limpiar_fuentes_espectador.sql
-- Los sitemaps de respaldo dan 404 (verificado en corrida CI 2026-06-11).
-- Queda solo el news-sitemap oficial declarado en su robots.txt.
update outlets set fuentes = '[
  {"tipo":"sitemap","url":"https://www.elespectador.com/arc/outboundfeeds/news-sitemap/?outputType=xml"}
]'::jsonb
where slug = 'el-espectador';