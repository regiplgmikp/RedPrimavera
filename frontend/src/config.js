export const API = (import.meta.env?.VITE_API_URL || 'http://127.0.0.1:8000').replace(/\/$/, '');

// Resolución H3 automática según el zoom del mapa
export const ZOOM_PARA_RES_9 = 12.2;
export const ATRIBUCION_MAPA = 'Tiles © Esri — Esri, HERE, Garmin, © OpenStreetMap contributors';
