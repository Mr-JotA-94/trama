INSERT INTO outlets (
    slug, nombre, url_base, rss_url,
    propietario, grupo_economico, ano_fundacion,
    linea_editorial_declarada, fuentes_financiacion,
    nivel_paywall, notas_perfil, fuentes, regla_seccion, extraccion
) VALUES (
    'rtvc',
    'RTVC Noticias',
    'https://www.rtvcnoticias.com',
    null,
    null, null, null,
    null, null,
    'abierto',
    '{}'::jsonb,
    '[{"url":"https://www.rtvcnoticias.com/sitemap-news.xml","tipo":"sitemap"}]'::jsonb,
    '{"metodo":"primer_segmento"}'::jsonb,
    'trafilatura'
)
ON CONFLICT (slug) DO NOTHING;