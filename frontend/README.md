# RedPrimavera · frontend (React + Vite + Deck.gl + Sigma)

    cd frontend
    cp .env.example .env      # VITE_API_URL=http://localhost:8000
    npm install
    npm run dev               # http://localhost:5173
    npm test                  # pruebas de la lógica pura (datos/colores/grafo)

Backend: uvicorn con CORS_ORIGINS que incluya http://localhost:5173 y los routers
subgrafos y capas (ver ../PARCHE_main.txt).

Capa demográfica: descargar el GPKG de Kontur México y correr
`python etls/etl_poblacion_kontur.py --gpkg <archivo> [--dry-run]`.

Panel izquierdo: filtros. Arriba: mapa (celdas H3 por IVC + círculos de población).
Abajo: grafo (Sigma). Casilla "sobreponer grafo al mapa" para verlo sobre el mapa.
