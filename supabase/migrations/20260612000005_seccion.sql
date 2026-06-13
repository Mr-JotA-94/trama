-- =====================================================================
-- TRAMA — Migración 5: sección temática
-- Archivo: supabase/migrations/20260612000005_seccion.sql
--
-- La sección NO se normaliza: se guarda cruda tal como cada medio la
-- nombra ('mundo', 'justicia', 'colombia'). Normalizar es un pozo sin
-- fondo; mejor guardar la verdad y normalizar después si hace falta.
--
-- La regla de extracción es POR MEDIO porque las URLs no comparten
-- estructura (verificado con datos reales 2026-06-12):
--   El Colombiano / El Espectador / El Tiempo → primer segmento del path
--   Las2orillas → la sección no vive en la URL del artículo → null
--   Vorágine → medio monotemático → fijo 'investigacion'
-- =====================================================================

-- Columna nueva en artículos (cruda, puede ser null)
alter table articles add column seccion text;

create index idx_articles_seccion on articles(seccion);

-- Regla de sección por medio, guardada junto a su config (como las fuentes).
-- metodo: 'primer_segmento' | 'fijo' | 'ninguno'
-- valor:  usado solo cuando metodo='fijo'
alter table outlets add column regla_seccion jsonb default '{"metodo":"primer_segmento"}'::jsonb;

update outlets set regla_seccion = '{"metodo":"primer_segmento"}'::jsonb
  where slug in ('el-colombiano','el-espectador','el-tiempo');

update outlets set regla_seccion = '{"metodo":"ninguno"}'::jsonb
  where slug = 'las2orillas';

update outlets set regla_seccion = '{"metodo":"fijo","valor":"investigacion"}'::jsonb
  where slug = 'voragine';

-- Verificación
select slug, regla_seccion from outlets order by slug;
