# TRAMA — Estado del proyecto (traspaso a nueva sesión)

> **Propósito de este archivo:** dárselo a un chat nuevo de Claude para que retome
> el proyecto con todo el contexto, sin releer conversaciones viejas. Léelo junto
> con ARQUITECTURA.md (el plan completo) y BITACORA.md (decisiones y deuda).
> Última actualización: **2026-06-13**.

---

## Quién soy y cómo trabajamos

Soy Jota (Johan). Claude es "Claudio". Reglas de trabajo que NO deben perderse:
- **Challenge-first:** Claudio cuestiona enfoques con fallas ANTES de construir,
  nunca obedece en silencio. Honestidad por encima de complacencia.
- **Declarar Tier (0–3) + componentes load-bearing antes de construir.**
- **Directo y conciso**, enfoque instructivo (me explica la lógica para aprender,
  no solo me da código). Español.
- **Medir antes de arreglar:** no se mete código por reflejo; se evalúa impacto vs
  riesgo. Varias veces hoy decidimos NO arreglar un bug medido de bajo impacto.
- **Diagnóstico con datos reales, no suposiciones.** Cuando Claudio no puede
  verificar algo en su entorno (ej. los medios bloquean su IP de datacenter), me
  da un script para correr en mi máquina y decidimos sobre datos verdaderos.

## Qué es Trama (una frase)

Hemeroteca forense de medios colombianos: archiva el contenido públicamente
visible de cada noticia con hash SHA-256 y marca de tiempo, para (Fase 2+) rastrear
cómo un mismo hecho se cubre distinto entre medios y (Fase 3) señalar técnicas de
persuasión. Objetivo de fondo: que el lector vea todos los ángulos, sin sesgo.
Público: periodistas, verificadores, ciudadanos activos. NO el público general.

## Stack (todo gratis)
- **Crawler:** Python (httpx + trafilatura), corre en GitHub Actions cada 6h
- **BD:** Supabase (Postgres + pgvector), región São Paulo. Claves formato nuevo
  (sb_secret_ para crawler / sb_publishable_ para web). RLS = solo lectura pública.
- **Web:** Next.js 14 (Server Components), deploy en Vercel → trama-co.vercel.app
- **Repo:** GitHub JotaLabs/trama (privado). Estructura: /crawler, /web,
  /supabase/migrations, ARQUITECTURA.md, BITACORA.md
- **Esquema versionado** en migraciones numeradas (20260611000001 en adelante).

## DÓNDE ESTAMOS — estado real al 2026-06-13

**Fase 1 COMPLETA y desplegada.** El crawler corre solo, la web está pública.
- 5 medios balanceados: Vorágine, Las2orillas, El Espectador, El Tiempo, El Colombiano
- ~115 artículos por corrida, deduplicación por hash verificada en CI
- Web con 3 vistas: registro (feed), expediente (artículo+hash), perfil de medio
- Sistema de diseño propio: papel/tinta/resaltador/hilo rojo, tipografía Archivo
- Columnas reservadas para perfiles de medios (Fase 3)
- Sección temática extraída por URL (regla por medio); tipo (noticia/opinion/etc)

**Estamos en la semana de observación de Fase 1** (criterio: 7 días verde, ≥150
artículos, 5 medios, cero duplicados, tipos correctos ≥80%). Cerca de cumplirse.

**Lo último que hicimos (sesión 2026-06-13):** ronda intensa de calidad de datos
antes de Fase 2 — limpieza de boilerplate (cola promocional, reproductores de
audio), arreglo de subtítulo de El Colombiano (vía twitter:description), quitar
favor_precision (recupera cuerpo en El Tiempo), extracción de sección, y detección
de paywall vía isAccessibleForFree del JSON-LD.

## PRÓXIMO PASO cuando retomemos

**Fase 2 — clustering / el hilo rojo conecta versiones del mismo hecho.**
Pero ANTES de Fase 2, revisar BITACORA.md — hay deuda y un hallazgo grande:

1. **⭐ articleBody del JSON-LD (PRIORIDAD ALTA):** El Espectador expone el cuerpo
   completo en JSON-LD. Si los demás también, conviene migrar la extracción de
   "trafilatura adivina" a "leer articleBody" ANTES de Fase 2 — resolvería de raíz
   la deuda de El Tiempo y daría cuerpos más limpios para clustering. Requiere su
   propia mini-sesión de diagnóstico. (Ver BITACORA, sección Ideas.)
2. **Revertir rfind→find** en limpiar_contenido (cambio que no hace nada, ver BITACORA).
3. Deuda menor vigilada: extracción El Tiempo (~1.7% notas cortadas por embed),
   sección de Las2orillas (null), feed plano silencia medios de baja frecuencia.

**Decisiones de Fase 2 pendientes de cerrar** (están en ARQUITECTURA.md):
- Umbral de similitud (hipótesis 0.62, calibrar con datos reales)
- Ventana temporal (±72h, revisar)
- Qué hacer con clústeres de tamaño 1
- Idea de Jota a incorporar: grafo de historias RELACIONADAS (no solo clústeres
  aislados — una nota y su derivada/reacción se enlazan entre clústeres).

## Fase 2 NO obliga a reconstruir al agregar medios
El clustering opera sobre artículos, no sobre medios. Agregar un medio = config
nueva en outlets (feed + regla de sección), no toca el clustering. Solo los
umbrales se recalibran. Recomendación: validar clustering con 5 medios (que
conozco y puedo juzgar) antes de expandir. Cola: Colombia+20, La Silla Vacía,
Semana, Caracol/W Radio, RTVC (medio público estatal, buen ángulo).

## Cómo verificar el estado en cualquier momento
- Salud del archivo: en Supabase, `select * from salud_archivo;` (si se creó la
  vista) o contar artículos/tipos/secciones por medio.
- Corridas del crawler: pestaña Actions del repo (deben estar en verde).
- La web: trama-co.vercel.app
