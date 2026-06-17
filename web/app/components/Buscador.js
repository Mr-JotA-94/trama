// TRAMA — Componente de búsqueda reutilizable.
// Server Component (sin estado), renderizable en cualquier ruta.
// Los filtros opcionales viven dentro del mismo form GET → un solo submit.
//
// Props de filtros:
//   opcionMedios  [{id, slug, nombre}]  — renders select de medio
//   conTipo       bool                  — renders select de tipo
//   conSeccion    bool                  — renders input de sección (ilike)
//   conFecha      bool                  — renders desde/hasta (date)
//   filtros       { medio, tipo, seccion, desde, hasta }  — pre-fill

const TIPOS = [
  { value: "noticia",     label: "Noticia" },
  { value: "opinion",     label: "Opinión" },
  { value: "editorial",   label: "Editorial" },
  { value: "analisis",    label: "Análisis" },
  { value: "agencia",     label: "Agencia" },
  { value: "desconocido", label: "Desconocido" },
];

export function Buscador({
  action = "/",
  q = "",
  url = "",
  labelTexto = "Buscar en el archivo",
  opcionMedios = [],
  conTipo = false,
  conSeccion = false,
  conFecha = false,
  filtros = {},
}) {
  const hayFiltros = opcionMedios.length > 0 || conTipo || conSeccion || conFecha;

  return (
    <div className="buscador">
      {/* ── Búsqueda de texto (por título) ── */}
      <form method="GET" action={action} className="buscador-form">
        <label htmlFor="buscador-q" className="buscador-label">
          {labelTexto}
        </label>
        <div className="buscador-fila">
          <input
            id="buscador-q"
            name="q"
            type="search"
            defaultValue={q}
            placeholder="ej. reforma tributaria"
            className="buscador-input"
            autoComplete="off"
          />
          <button type="submit" className="buscador-btn">Buscar</button>
        </div>

        {hayFiltros && (
          <div className="buscador-filtros">
            {opcionMedios.length > 0 && (
              <label className="buscador-filtro">
                <span className="buscador-filtro-label">Medio</span>
                <select name="medio" className="buscador-select" defaultValue={filtros.medio ?? ""}>
                  <option value="">Todos</option>
                  {opcionMedios.map((m) => (
                    <option key={m.slug} value={m.slug}>{m.nombre}</option>
                  ))}
                </select>
              </label>
            )}

            {conTipo && (
              <label className="buscador-filtro">
                <span className="buscador-filtro-label">Tipo</span>
                <select name="tipo" className="buscador-select" defaultValue={filtros.tipo ?? ""}>
                  <option value="">Todos</option>
                  {TIPOS.map((t) => (
                    <option key={t.value} value={t.value}>{t.label}</option>
                  ))}
                </select>
              </label>
            )}

            {conSeccion && (
              <label className="buscador-filtro">
                <span className="buscador-filtro-label">Sección</span>
                <input
                  name="seccion"
                  type="text"
                  defaultValue={filtros.seccion ?? ""}
                  placeholder="ej. colombia"
                  className="buscador-input-corto"
                />
              </label>
            )}

            {conFecha && (
              <>
                <label className="buscador-filtro">
                  <span className="buscador-filtro-label">Desde</span>
                  <input
                    name="desde"
                    type="date"
                    defaultValue={filtros.desde ?? ""}
                    className="buscador-input-fecha"
                  />
                </label>
                <label className="buscador-filtro">
                  <span className="buscador-filtro-label">Hasta</span>
                  <input
                    name="hasta"
                    type="date"
                    defaultValue={filtros.hasta ?? ""}
                    className="buscador-input-fecha"
                  />
                </label>
              </>
            )}
          </div>
        )}
      </form>

      {/* ── Búsqueda por URL exacta ── */}
      <form method="GET" action="/buscar" className="buscador-form buscador-form-url">
        <label htmlFor="buscador-url" className="buscador-label">
          Buscar URL en el archivo
        </label>
        <div className="buscador-fila">
          <input
            id="buscador-url"
            name="url"
            type="url"
            defaultValue={url}
            placeholder="https://eltiempo.com/politica/…"
            className="buscador-input"
            autoComplete="off"
          />
          <button type="submit" className="buscador-btn">Localizar</button>
        </div>
      </form>
    </div>
  );
}
