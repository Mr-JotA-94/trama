# TRAMA — web (Fase 1, Paso 4)

Sitio público de solo lectura del archivo. Next.js 14 + Supabase (clave publishable, RLS de solo lectura).

## Correr local
1. `npm install`
2. Copia `.env.local.example` a `.env.local` y llena la URL y la clave `sb_publishable_` (Supabase → Settings → API). JAMÁS la sb_secret_.
3. `npm run dev` → http://localhost:3000

## Estructura
- `app/page.js` — registro de capturas agrupado por día (hora de Colombia)
- `app/articulo/[id]/page.js` — el expediente: hash, timestamps, contenido archivado
- `app/medio/[slug]/page.js` — identificación del medio + capturas (perfil completo: Fase 3)
- `app/globals.css` — sistema de diseño: papel, tinta, resaltador, hilo
- `lib/supabase.js` — cliente de solo lectura

## Deploy (gratis)
Vercel: importar el repo, root directory = `web/`, agregar las dos variables de entorno, deploy.
Netlify: igual (base directory = `web/`, build `npm run build`).
