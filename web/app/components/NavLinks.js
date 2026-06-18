"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";

export default function NavLinks() {
  const path = usePathname();
  const enHistorias = path === "/historias" || path.startsWith("/historias/") || path.startsWith("/historia/");
  const enRegistro  = !enHistorias;

  return (
    <>
      <Link href="/historias" className={`nav-link${enHistorias ? " nav-link-activo" : ""}`}>Historias</Link>
      <Link href="/"          className={`nav-link${enRegistro  ? " nav-link-activo" : ""}`}>Registro</Link>
    </>
  );
}
