import Link from "next/link";

export default function ArticuloSinHistoria({ articulos }) {
  return (
    <>
      {(articulos ?? []).map((a) => (
        <div key={a.id} className="buscar-resultado">
          <p className="buscar-resultado-titulo">{a.titulo}</p>
          <p className="buscar-resultado-sub">Archivada · aún sin historia.</p>
          <Link href={`/articulo/${a.id}`} className="enlace-original">
            Ver la nota archivada →
          </Link>
        </div>
      ))}
    </>
  );
}
