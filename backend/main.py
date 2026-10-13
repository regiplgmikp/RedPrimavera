"""
App principal del backend RedPrimavera.

Correr en desarrollo:
    uvicorn main:app --reload

Docs automáticas (Swagger) una vez corriendo:
    http://localhost:8000/docs
"""

import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware

from .database import get_session, cerrar_driver
from .routers import grafo, celdas
from .routers import grafo, celdas, subgrafos

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # nada que inicializar al arrancar -- el driver se crea "lazy" en el
    # primer request (ver database.get_driver). Solo cerramos al apagar.
    yield
    cerrar_driver()


app = FastAPI(title="RedPrimavera API", version="0.1.0", lifespan=lifespan)
app.include_router(grafo.router)
app.include_router(celdas.router)
app.include_router(subgrafos.router)


cors_origins = os.environ.get("CORS_ORIGINS", "").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in cors_origins if o.strip()],
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(grafo.router)
app.include_router(celdas.router)


@app.get("/health")
def health(session=Depends(get_session)):
    """Confirma que la app está viva Y que puede hablar con Neo4j."""
    total = session.run("MATCH (n) RETURN count(n) AS total").single()["total"]
    return {"status": "ok", "nodos_en_base": total}