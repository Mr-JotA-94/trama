// TRAMA — cliente Supabase de SOLO LECTURA.
// Usa la clave publishable: gracias al RLS (migración 2), esta clave
// puede leer todo y escribir nada. La sb_secret_ jamás toca este proyecto.
import { createClient } from "@supabase/supabase-js";

export const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL,
  process.env.NEXT_PUBLIC_SUPABASE_KEY,
  { auth: { persistSession: false } } // sitio público, sin sesiones
);
