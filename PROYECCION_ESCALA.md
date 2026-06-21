# PROYECCIÓN DE ESCALA — TRAMA

> **Qué es esto:** notas de proyección de infraestructura, almacenamiento y cómputo
> a medida que crece el archivo. NO es deuda técnica (eso vive en BITACORA) ni
> arquitectura vinculante (ARQUITECTURA.md). Es exploración para no improvisar
> cuando un límite se acerque.
>
> **Documento VIVO:** se reemplaza/actualiza al re-medir. NO es append-only.
> **Principio rector (igual que el código):** medir antes de optimizar. Nada de
> esto se implementa hasta que su disparador se cumpla. Optimización prematura =
> complejidad gratis.
>
> Última medición: **2026-06-21** (1645 artículos).

---

## 1. Dato real medido (no estimado)

Query usado:
```sql
select pg_size_pretty(pg_total_relation_size('articles')) as articles_total,
       pg_total_relation_size('articles') / greatest(count(*),1) as por_articulo,
       count(*) as n
from articles;
```

Resultado 2026-06-21:
- **articles_total:** 12 MB
- **por_artículo:** 7.569 bytes
- **n:** 1645 artículos

⚠️ **OJO con el promedio:** 7.569 bytes/art está temporalmente BAJO. ~663 artículos
nuevos (crawler desde 06-18) aún NO tienen embedding (backfill manual pendiente), y
el embedding vector(384) es lo que más pesa por fila. La medición previa (06-18, 982
artículos TODOS embebidos) dio **9.451 bytes/art (~9.5 KB)**. Ese es el peso de un
artículo PROCESADO, y es el número a usar para proyectar (conservador). Cuando se
corra el backfill de los 663 pendientes, el promedio volverá a subir hacia ~9.5 KB y
el total hacia ~15–16 MB.

**Peso de trabajo para proyección: ~9.5 KB por artículo procesado.**

---

## 2. Proyección contra el free tier de Supabase (500 MB de BD)

- Techo aproximado: 500 MB / 9.5 KB ≈ **~53.000 artículos** (sin cambio).
- **Ingreso real MEDIDO 2026-06-21: ~188 artículos/día** (antes ESTIMADO 100–150).
  Query: `select count(*)/7.0 from articles where fecha_captura > now() - interval '7 days';`
  El ingreso real es ~50% mayor que la estimación previa. Posible inflación temporal
  por cobertura electoral (segunda vuelta) en la ventana medida; re-medir fuera de
  pico para confirmar el régimen base.
- Horizonte recalculado: 53.000 / 188 ≈ 282 días ≈ **~9 meses** hasta rozar 500 MB a
  5 medios (antes 10–14 meses; se acortó al medir el ingreso real).

**Variable de control = número de medios, NO el tiempo.** A medios constantes el
ingreso diario es estable (los medios publican volumen acotado). El crecimiento se
dispara al ACTIVAR medios nuevos. Pasar de 5 a 10 medios ~duplica el ritmo y parte
el horizonte a la mitad (~4–5 meses). Re-medir y re-proyectar cada vez que se active
un medio.

---

## 3. Los cuellos de botella reales (ordenados por cuándo muerden)

El storage NO es el primer problema. En orden de aparición probable:

### a) Cron de GitHub Actions se desactiva tras 60 días sin commits
- Ya documentado en BITACORA/Notas de operación. NO es de escala (no empeora con
  volumen), pero es lo que más probablemente rompa el pipeline EN SILENCIO.
- Mitigación: cualquier commit al repo lo reactiva. Tenerlo en el radar.

### b) Clustering O(n²) — el primer límite DE ESCALA real
- `clustering_fase2.py` compara cada par de artículos dentro de la ventana ±72h.
  El costo crece con el CUADRADO del número de artículos por ventana, no con el
  storage.
- A 5 medios la ventana de 72h tiene pocos cientos de artículos → corre en segundos.
- A más medios / más volumen, una ventana de 72h puede tener miles → el O(n²)
  empieza a doler en TIEMPO DE CÓMPUTO (la corrida manual se vuelve lenta), mucho
  antes de tocar los 500 MB de disco.
- **NO confundir con "clustering incremental"** (recalcular solo lo reciente), que se
  DESCARTÓ en BITACORA 2026-06-21: eso es no-recalcular-clústeres-viejos (cambia la
  semántica de stories de caché a estado). Esto de aquí es acelerar la COMPARACIÓN de
  pares manteniendo el recompute-todo. Son problemas distintos.
- **Disparador para atacarlo:** antes de activar varios medios nuevos, o si la
  corrida manual de clustering empieza a tardar de forma molesta.
- **Candidatos (no implementar aún):**
  - Pre-filtro por bloque: agrupar candidatos por sección/fecha antes de comparar
    pares.
  - Índice invertido por entidad: solo comparar pares que comparten ≥1 entidad
    (evita el grueso de comparaciones que de antemano dan peso_idf=0).
  - Índice vectorial en pgvector (HNSW/IVFFlat): hoy la similitud se hace en numpy
    cargando embeddings a RAM; a escala grande, búsqueda aproximada en Postgres
    evita traer miles de vectores por corrida. A escala chica, numpy es más simple
    y está bien.

---

## 4. Tensión inmutabilidad ↔ storage (decisión de principio, tomarla en frío)

Trama es hemeroteca forense: el archivo es inmutable, nada se borra. Consecuencia:
**el storage solo crece, nunca se poda.** Al llegar a 500 MB, las opciones NO
incluyen "borrar lo viejo" (violaría la identidad del proyecto). Las opciones reales:

1. **Pagar el siguiente tier de Supabase** (Pro: 8 GB de BD; ~16× el techo actual →
   años más de margen).
2. **Migrar el archivo histórico** a almacenamiento más barato (p. ej. el texto
   crudo a object storage), MANTENIENDO el hash y la verificabilidad. La BD activa
   guarda lo reciente + embeddings; el archivo frío vive más barato sin perder la
   propiedad de inmutabilidad.

**Decisión registrada (en frío, hoy):** a 500 MB se PAGA o se MIGRA-SIN-BORRAR.
Nunca se poda bajo presión. Dejarlo escrito ahora evita la tentación de podar
cuando el límite apriete.

---

## 5. Qué NO hacer ahora (optimización prematura)

Con ~2–3% del free tier usado (12 MB / 500 MB) y ~9 meses de horizonte a 5 medios,
NO se justifica:
- Comprimir o cuantizar embeddings.
- Mover texto a object storage.
- Particionar o archivar tablas.
- Tocar el O(n²) del clustering (corre en segundos a esta escala).

Todo esto resuelve un problema de 500 MB que no existe hoy. Implementarlo ahora es
complejidad gratis. Esperar al disparador.

---

## 6. Resumen ejecutivo

- **Storage NO es problema:** ~9 meses de margen a 5 medios (ingreso real medido
  188/día). El multiplicador es agregar medios, no el tiempo.
- **Primer límite real = cómputo del clustering O(n²)**, no disco. Aparece al
  escalar medios.
- **Plan a 500 MB ya decidido:** pagar o migrar-sin-borrar (inmutabilidad manda).
- **Acción inmediata:** ninguna técnica. Solo re-medir al activar cada medio nuevo,
  y re-medir el ingreso/día fuera de pico electoral para confirmar el régimen base.
