ALTER TABLE resumenes_dia ADD COLUMN hechos_corroborados jsonb NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE resumenes_dia ADD COLUMN solo_un_medio       jsonb NOT NULL DEFAULT '[]'::jsonb;