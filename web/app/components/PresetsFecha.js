import Link from "next/link";

function hoyBogota() {
  // en-CA produce YYYY-MM-DD directamente
  return new Date().toLocaleDateString("en-CA", { timeZone: "America/Bogota" });
}

function restarDias(iso, n) {
  // T12:00:00 ancla a mediodía para evitar saltos por borde UTC/DST
  const d = new Date(iso + "T12:00:00");
  d.setDate(d.getDate() - n);
  return d.toLocaleDateString("en-CA");
}

export function PresetsFecha({ filtros, action }) {
  const hoy = hoyBogota();

  const presets = [
    { label: "Último día",    desde: hoy,                 hasta: hoy },
    { label: "Última semana", desde: restarDias(hoy, 6),  hasta: hoy },
    { label: "Último mes",    desde: restarDias(hoy, 29), hasta: hoy },
  ];

  function buildHref(preset, activo) {
    const desde = activo ? "" : preset.desde;
    const hasta = activo ? "" : preset.hasta;
    const params = { ...filtros, desde, hasta };
    const sp = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) if (v) sp.set(k, String(v));
    const qs = sp.toString();
    return qs ? `${action}?${qs}` : action;
  }

  return (
    <nav className="presets-fecha" aria-label="Filtrar por período">
      {presets.map((p) => {
        const activo = filtros.desde === p.desde && filtros.hasta === p.hasta;
        return (
          <Link
            key={p.label}
            href={buildHref(p, activo)}
            className={activo ? "activo" : ""}
            aria-current={activo ? "true" : undefined}
            aria-label={activo ? `Quitar filtro ${p.label}` : `Filtrar ${p.label}`}
          >
            {p.label}
          </Link>
        );
      })}
    </nav>
  );
}
