// Consulta a iNaturalist (API pública) para armar la tarjeta de una especie.
// Guarda lo ya consultado para no repetir peticiones al volver a elegir la misma.
const URL_TAXA = 'https://api.inaturalist.org/v1/taxa';
const cache = new Map(); // nombre científico -> info (o null si no se encontró)

// iNaturalist devuelve el resumen de Wikipedia como HTML: aquí se deja solo el texto.
function textoPlano(html) {
  if (!html) return '';
  return html.replace(/<[^>]+>/g, '').replace(/&nbsp;/g, ' ').replace(/&amp;/g, '&').trim();
}

export async function infoEspecie(nombre, signal) {
  if (cache.has(nombre)) return cache.get(nombre);
  const url = `${URL_TAXA}?q=${encodeURIComponent(nombre)}&rank=species&per_page=5&locale=es`;
  const res = await fetch(url, { signal });
  if (!res.ok) throw new Error(`iNaturalist respondió ${res.status}`);
  const json = await res.json();
  // Solo se acepta coincidencia exacta del nombre científico, para no mostrar otra especie
  const t = (json.results || []).find((r) => r.name?.toLowerCase() === nombre.toLowerCase());
  const info = t ? {
    nombre: t.name,
    comun: t.preferred_common_name || null,
    foto: t.default_photo?.medium_url || null,
    credito: t.default_photo?.attribution || null,
    resumen: textoPlano(t.wikipedia_summary),
    estado: t.conservation_status?.status_name || null, // estado de conservación, si lo hay
    observaciones: t.observations_count ?? null,
    enlace: `https://www.inaturalist.org/taxa/${t.id}`,
  } : null;
  cache.set(nombre, info);
  return info;
}