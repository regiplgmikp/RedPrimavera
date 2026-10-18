# RedPrimavera · frontend (React + Vite + Deck.gl + Sigma)

    cd frontend
    cp .env.example .env      # VITE_API_URL=http://localhost:8000
    npm install
    npm run dev               # http://localhost:5173
    npm test                  # pruebas de la lógica pura (datos/colores/grafo)

Backend: desde la raíz del repositorio, configura `CORS_ORIGINS` con
`http://localhost:5173` y ejecuta:

    python -m uvicorn backend.main:app --reload

La API debe incluir los routers de `subgrafos` y `capas`; consulta
`../README.md` para la configuración completa y los endpoints disponibles.

Capa demográfica: descargar el GPKG de Kontur México y correr
`python etls/etl_poblacion_kontur.py --gpkg <archivo> [--dry-run]`.

Panel izquierdo: filtros. Arriba: mapa (celdas H3 por IVC + círculos de población).
Abajo: grafo (Sigma). Casilla "sobreponer grafo al mapa" para verlo sobre el mapa.
