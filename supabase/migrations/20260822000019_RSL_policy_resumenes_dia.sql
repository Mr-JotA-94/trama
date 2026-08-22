-- TRAMA — migración 000019
-- RLS: policy de lectura pública para resumenes_dia.
--
-- POR QUÉ (medido 2026-08-22, no supuesto):
--   select c.relname, c.relrowsecurity, p.polname from pg_class c
--   left join pg_policy p on p.polrelid = c.oid where c.relname='resumenes_dia';
--   -> rls_activo = true, polname = NULL
--
-- resumenes_dia nació con RLS ACTIVO y SIN policy de SELECT. El crawler escribe con
-- la clave sb_secret_ (ignora RLS) y por eso nunca lo notó: los 166 días están ahí.
-- La web lee con sb_publishable_, que SÍ respeta RLS, y sin policy vería CERO filas
-- SIN ERROR — RLS no falla, filtra en silencio. Es exactamente el hueco de la
-- migración 000009 (BITACORA 2026-06-17: "la web mostraba 'Fase 2 en construcción'
-- con datos reales presentes").
--
-- Copia literal de la policy de articles/outlets/stories/story_relations.
-- ADITIVA: no toca datos, no toca esquema, no toca la escritura del crawler
-- (la clave secreta sigue ignorando RLS). Riesgo de datos: cero.
--
-- ALCANCE DELIBERADO: `comparaciones` NO se expone en esta migración. Tiene el mismo
-- hueco, pero su deuda de auditoría sigue abierta (BITACORA 2026-07-30: "hay 103
-- comparaciones de GLM en DB que NADIE ha leído"). Se le abre la lectura pública el
-- día que su unidad de frontend pase por la lectura a ojo, no antes: no se expone
-- material no auditado, ni siquiera de forma latente.

alter table public.resumenes_dia enable row level security;

create policy lectura_publica
  on public.resumenes_dia
  for select
  to public
  using (true);

-- VERIFICACIÓN post-aplicación (debe devolver una fila con polcmd='r'):
--   select p.polname, p.polcmd, pg_get_expr(p.polqual, p.oid)
--   from pg_policy p join pg_class c on c.oid = p.polrelid
--   where c.relname = 'resumenes_dia';