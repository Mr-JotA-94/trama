// TRAMA — Página de medio. Hoy: identificación básica + capturas recientes.
// El perfil completo (propiedad, financiación, historial) llega en Fase 3
// sobre las columnas ya reservadas en la base de datos.
import Link from "next/link";
import { notFound } from "next/navigation";
import { supabase } from "@/lib/supabase";

export const revalidate = 300;

export default async function Medio({ params }) {
  const { data: medio, error } = await supabase
    .from("outlets")
    .select("id, nombre, url_base, nivel_paywall")
    .eq("slug", params.slug)
    .single();

  if (error || !medio) notFound();

  const { count } = await supabase
    .from("articles")
    .select("id", { count: "exact", head: true })
    .eq("outlet_id", medio.id);

  const { data: capturas } = await supabase
    .from("articles")
    .select("id, titulo, tipo, fecha_captura")
    .eq("outlet_id", medio.id)
    .order("fecha_captura", { ascending: false })
    .limit(30);

  return (
    <>
      <div className={`medio-cabecera medio-${params.slug}`}>
        <h1 className="medio-nombre">{medio.nombre}</h1>
        <span className="tag tag-medio">paywall {medio.nivel_paywall}</span>
      </div>
      <p className="medio-stats">
        {count ?? 0} capturas en el archivo · {medio.url_base}
      </p>

      <div className="perfil-pendiente">
        Perfil del medio en construcción: propiedad, grupo económico,
        financiación e historial documentado llegarán en una fase futura,
        cada dato con su fuente citable.
      </div>

      <h2 className="dia-titulo">Capturas recientes</h2>
      {capturas?.map((a) => (
        <article key={a.id} className="captura">
          <div className="captura-meta">
            <span>
              {new Date(a.fecha_captura).toLocaleDateString("es-CO", {
                timeZone: "America/Bogota", day: "2-digit", month: "short",
              })}
            </span>
            {a.tipo !== "noticia" && <span className="tag">{a.tipo}</span>}
          </div>
          <h3 className="captura-titulo">
            <Link href={`/articulo/${a.id}`}>{a.titulo}</Link>
          </h3>
        </article>
      ))}
    </>
  );
}
