// TRAMA — Registro de capturas (página principal).
// Server Component: la consulta corre en el servidor, el navegador
// recibe HTML ya armado. Se revalida cada 5 minutos.
// Con searchParams la página se renderiza dinámicamente en cada request.
import Link from "next/link";
import { supabase } from "@/lib/supabase";
import { Buscador } from "@/app/components/Buscador";
import { PresetsFecha } from "@/app/components/PresetsFecha";

export const revalidate = 300;

function agruparPorDia(articulos) {
  const dias = new Map();
  for (const a of articulos) {
    const dia = new Date(a.fecha_captura).toLocaleDateString("es-CO", {
      timeZone: "America/Bogota",
      weekday: "long", day: "numeric", month: "long", year: "numeric",
    });
    if (!dias.has(dia)) dias.set(dia, []);
    dias.get(dia).push(a);
  }
  return dias;
}

function horaCO(ts) {
  return new Date(ts).toLocaleTimeString("es-CO", {
    timeZone: "America/Bogota", hour: "2-digit", minute: "2-digit",
  });
}

export default async function Registro({ searchParams }) {
  const q       = (searchParams?.q       ?? "").trim();
  const medio   = (searchParams?.medio   ?? "").trim();
  const tipo    = (searchParams?.tipo    ?? "").trim();
  const seccion = (searchParams?.seccion ?? "").trim();
  const desde   = (searchParams?.desde  ?? "").trim();
  const hasta   = (searchParams?.hasta  ?? "").trim();

  // Outlets: necesarios para el dropdown Y para resolver outlet_id del filtro.
  // Query pequeña (5 filas), se hace primero para poder filtrar artículos.
  const { data: outlets } = await supabase
    .from("outlets")
    .select("id, slug, nombre")
    .order("nombre");

  // Resolver outlet_id desde slug sin query extra
  const outletId = medio && outlets
    ? (outlets.find((o) => o.slug === medio)?.id ?? null)
    : null;

  let query = supabase
    .from("articles")
    .select("id, titulo, tipo, seccion, es_parcial, fecha_captura, hash_sha256, outlets(nombre, slug)")
    .order("fecha_captura", { ascending: false })
    .limit(80);

  if (q)        query = query.ilike("titulo",   `%${q}%`);
  if (outletId) query = query.eq("outlet_id",   outletId);
  if (tipo)     query = query.eq("tipo",         tipo);
  if (seccion)  query = query.ilike("seccion",  `%${seccion}%`);
  if (desde)    query = query.gte("fecha_captura", `${desde}T00:00:00`);
  if (hasta)    query = query.lte("fecha_captura", `${hasta}T23:59:59`);

  const { data: articulos, error } = await query;

  const filtros = { q, medio, tipo, seccion, desde, hasta };

  const buscador = (
    <Buscador
      q={q}
      opcionMedios={outlets ?? []}
      conTipo
      conSeccion
      conFecha
      filtros={filtros}
    />
  );

  if (error) {
    return (
      <>
        {buscador}
        <p>El archivo no respondió. Recarga la página para reintentar.</p>
      </>
    );
  }

  if (!articulos?.length) {
    return (
      <>
        {buscador}
        {q || medio || tipo || seccion || desde || hasta ? (
          <>
            <PresetsFecha filtros={filtros} action="/" />
            <p className="buscar-resultado-sub">Sin resultados para los filtros aplicados.</p>
          </>
        ) : (
          <p>El archivo aún no tiene capturas. El crawler corre cada 6 horas.</p>
        )}
      </>
    );
  }

  const dias = agruparPorDia(articulos);
  const hayFiltroActivo = q || medio || tipo || seccion || desde || hasta;

  return (
    <>
      {buscador}
      <PresetsFecha filtros={filtros} action="/" />
      {hayFiltroActivo && (
        <p className="buscar-resultado-sub">
          {articulos.length} {articulos.length === 1 ? "captura" : "capturas"}
        </p>
      )}
      {[...dias.entries()].map(([dia, capturas]) => (
        <section key={dia}>
          <h2 className="dia-titulo">{dia} · hora de Colombia</h2>
          {capturas.map((a) => (
            <article key={a.id} className="captura">
              <div className="captura-meta">
                <span>{horaCO(a.fecha_captura)}</span>
                <Link href={`/medio/${a.outlets.slug}`} className={`tag tag-medio medio-${a.outlets.slug}`}>
                  {a.outlets.nombre}
                </Link>
                {a.tipo !== "noticia" && (
                  <span className={`tag ${a.tipo === "opinion" ? "tag-opinion" : ""}`}>{a.tipo}</span>
                )}
                {a.seccion && <span className="tag tag-seccion">{a.seccion}</span>}
                {a.es_parcial && <span className="tag tag-parcial">captura parcial</span>}
                <span title="SHA-256 de la captura">{a.hash_sha256.slice(0, 12)}…</span>
              </div>
              <h3 className="captura-titulo">
                <Link href={`/articulo/${a.id}`}>{a.titulo}</Link>
              </h3>
            </article>
          ))}
        </section>
      ))}
    </>
  );
}
