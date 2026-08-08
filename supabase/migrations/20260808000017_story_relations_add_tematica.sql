-- story_relations: tipo de arista. 'tematica' = motor n_especificas + guardia coseno
-- (comportamiento histórico). 'misma_trama' = subhistorias hermanas nacidas del
-- mismo componente union-find partido por Louvain (verdad mecánica, sin umbral).
-- Caché derivada pura (delete-then-insert cada corrida): riesgo de datos nulo.
alter table story_relations
  add column tipo text not null default 'tematica';

alter table story_relations
  add constraint story_relations_tipo_check
  check (tipo in ('tematica', 'misma_trama'));