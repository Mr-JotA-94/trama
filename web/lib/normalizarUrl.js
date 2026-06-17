// Normalización de URL para lookup de artículos en el archivo.
//
// Regla medida (2026-06-17): ningún medio del archivo usa query params para
// identificar artículos — el ID vive en el path. Se usa allowlist vacía
// (quitar TODOS los params) en vez de denylist de trackers.
//
// Deuda best-effort documentada: variantes AMP (amp.medio.com), móvil (m.medio.com)
// y subdominios inusuales fallan silencioso — el archivo almacena la URL exacta
// que entregó el RSS/sitemap, sin normalización previa.

/**
 * http → https, lowercase host, sin query params, sin fragment.
 * Trailing slash y www se preservan tal como vienen — se cubren en variantesUrl().
 *
 * @param {string} rawUrl
 * @returns {{ url: string|null, error: string|null }}
 */
export function normalizarUrl(rawUrl) {
  try {
    const p = new URL(rawUrl.trim());
    const host = p.hostname.toLowerCase();
    const port = p.port ? `:${p.port}` : "";
    return { url: `https://${host}${port}${p.pathname}`, error: null };
  } catch {
    return { url: null, error: "URL inválida — debe empezar con https:// o http://" };
  }
}

/**
 * Genera las 4 combinaciones acotadas: con/sin www × con/sin trailing slash.
 * Incluye la URL de entrada. Retorna array deduplicado.
 * Usar con .in("url", variantes) para un solo query a la BD.
 *
 * Cubre el caso medido (2026-06-17): El Espectador y Las2orillas almacenan
 * URLs con trailing slash; los demás medios no. Un usuario que pega sin slash
 * necesita la variante con slash para hacer match.
 *
 * @param {string} url URL ya normalizada por normalizarUrl()
 * @returns {string[]}
 */
export function variantesUrl(url) {
  const p    = new URL(url);
  const host = p.hostname;
  const port = p.port ? `:${p.port}` : "";
  const path = p.pathname;

  const conWww   = host.startsWith("www.") ? host : `www.${host}`;
  const sinWww   = host.startsWith("www.") ? host.slice(4) : host;
  const conSlash = path.endsWith("/") ? path : `${path}/`;
  const sinSlash = path.endsWith("/") && path.length > 1 ? path.slice(0, -1) : path;

  return [...new Set([
    `https://${conWww}${port}${conSlash}`,
    `https://${conWww}${port}${sinSlash}`,
    `https://${sinWww}${port}${conSlash}`,
    `https://${sinWww}${port}${sinSlash}`,
  ])];
}
