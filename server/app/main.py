from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import Base, SessionLocal, engine
from .routers import auth, insights, preferences, ranking, parser, agent, pipeline
from .seed import seed_database


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()

    try:
        seed_database(db)
    finally:
        db.close()

    yield


app = FastAPI(
    title="Alfa Hack Backend",
    description="Backend API для frontend-прототипа.",
    version="1.0.0",
    lifespan=lifespan,
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(auth.router)
app.include_router(insights.router)
app.include_router(ranking.router)
app.include_router(preferences.router)
app.include_router(parser.router)
app.include_router(agent.router)
app.include_router(pipeline.router)


@app.get("/")
def root():
    return {
        "name": "Alfa Hack Backend",
        "status": "ok",
        "docs": "/docs",
    }
