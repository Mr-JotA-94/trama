-- 20260705000013_analyses_story_id_set_null.sql
-- Corrige el FK de analyses.story_id -> stories(id).
--
-- CONTEXTO (hallazgo de esta unidad, no asumido): la migración 000001 creó ese FK
-- apuntando a la `stories` de ese momento (esquema viejo: titulo_descriptivo,
-- fecha_evento, articulo_origen_id, estado). La migración 000008 hizo
-- `drop table stories cascade` para reemplazarla por el esquema correcto de Fase 2.
-- Ese CASCADE se llevó por delante el FK de analyses (dependía de la tabla vieja);
-- la `stories` nueva es un objeto distinto y nada la volvió a enlazar. Resultado:
-- a día de hoy analyses.story_id probablemente NO tiene ningún FK — peor que la
-- landmine original (RESTRICT), porque hoy una story borrada deja story_id
-- apuntando a un id inexistente en silencio, sin error.
--
-- Por eso este bloque DESCUBRE el estado real en vez de asumirlo: si existe
-- cualquier FK de analyses.story_id -> stories (con el nombre que sea), lo borra;
-- luego agrega siempre el FK correcto con ON DELETE SET NULL. Correcto sin
-- importar cuál de los dos estados tenga la base viva.
--
-- Por qué SET NULL y no CASCADE: clustering_fase2.py recomputa stories cada 6h.
-- CASCADE borraría los analyses (Fase 3, caros de generar vía LLM) cada vez que su
-- story se re-semilla o se disuelve. SET NULL conserva el texto del análisis; solo
-- pierde el enlace a la story, que se puede re-derivar por article_id si hiciera falta.
do $$
declare
  fk_actual text;
begin
  select conname into fk_actual
  from pg_constraint
  where conrelid = 'analyses'::regclass
    and confrelid = 'stories'::regclass
    and contype = 'f';

  if fk_actual is not null then
    execute format('alter table analyses drop constraint %I', fk_actual);
  end if;
end $$;

alter table analyses
  add constraint analyses_story_id_fkey
  foreign key (story_id) references stories(id) on delete set null;
