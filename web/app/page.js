// TRAMA — Registro de capturas (página principal).
// Server Component: la consulta corre en el servidor, el navegador
// recibe HTML ya armado. Se revalida cada 5 minutos.
import Link from "next/link";
import { supabase } from "@/lib/supabase";

export const revalidate = 300;

// Agrupa las capturas por día (zona horaria de Colombia: el archivo
// vive en hora colombiana aunque el servidor esté en otra parte).
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

export default async function Registro() {
  const { data: articulos, error } = await supabase
    .from("articles")
    .select("id, titulo, tipo, es_parcial, fecha_captura, hash_sha256, outlets(nombre, slug)")
    .order("fecha_captura", { ascending: false })
    .limit(80);

  if (error) {
    return <p>El archivo no respondió. Recarga la página para reintentar.</p>;
  }
  if (!articulos?.length) {
    return <p>El archivo aún no tiene capturas. El crawler corre cada 6 horas.</p>;
  }

  const dias = agruparPorDia(articulos);

  return (
    <>
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
