CREATE TABLE resumenes_dia (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    story_id       uuid REFERENCES stories(id) ON DELETE CASCADE,
    dia            date NOT NULL,
    dia_key        text NOT NULL UNIQUE,   -- hash del set de member_hashes del día
    sintesis       text,
    article_ids    uuid[],
    member_hashes  text[],
    medios         text[],
    modelo         text,
    prompt_version text,
    created_at     timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_resumenes_dia_story ON resumenes_dia(story_id);