-- 000018: resumenes_dia sobrevive a re-splits. El trabajo LLM se ancla a dia_key
-- (contenido inmutable); story_id pasa a etiqueta re-vinculable. CASCADE → SET NULL.
BEGIN;
ALTER TABLE resumenes_dia DROP CONSTRAINT resumenes_dia_story_id_fkey;
ALTER TABLE resumenes_dia
  ADD CONSTRAINT resumenes_dia_story_id_fkey
  FOREIGN KEY (story_id) REFERENCES stories(id) ON DELETE SET NULL;
COMMIT;