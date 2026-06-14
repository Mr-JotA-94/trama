-- 20260614000001_extraccion_por_medio.sql
-- Método de extracción de cuerpo por medio (bucket), decidido por diagnóstico.
--
--   'articlebody' = preferir articleBody del JSON-LD; trafilatura de respaldo
--                   si el medio no lo expone en una nota dada.
--   'trafilatura' = solo trafilatura (medios donde articleBody no existe o,
--                   a futuro, donde se mida que es peor que trafilatura).
--
-- Default 'articlebody': comportamiento seguro para un medio nuevo (intenta el
-- cuerpo declarado por el medio, cae a trafilatura si falta). Aun así, la regla
-- del proyecto es DIAGNOSTICAR cada medio nuevo y fijar su bucket explícito.
--
-- Esta migración toca SOLO config (outlets). No toca articles: no altera
-- contenido ni hashes. La inmutabilidad del archivo queda intacta.

alter table outlets
  add column extraccion text not null default 'articlebody'
  check (extraccion in ('articlebody', 'trafilatura'));

-- Buckets fijados por el diagnóstico del 2026-06-14:
-- Vorágine no expone JSON-LD; Las2orillas no expone articleBody. En ambos
-- trafilatura ya extrae cuerpos limpios y largos. Se les fija el método probado
-- (y se les blinda ante un futuro rediseño de CMS que metiera articleBody malo).
update outlets set extraccion = 'trafilatura'
  where slug in ('voragine', 'las2orillas');

-- El Tiempo, El Colombiano y El Espectador quedan en 'articlebody' (default):
-- cobertura medida 100% / 100% / 83%, con cuerpos más limpios que trafilatura
-- (sin cookies, sin "Escucha este artículo", sin cola promocional de boletines).
