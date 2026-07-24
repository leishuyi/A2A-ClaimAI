from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database.session import engine, Base
from app.routers import cases, agents, human_gate

Base.metadata.create_all(bind=engine)

app = FastAPI(title="A2A 智能理赔助手 API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(cases.router, prefix="/api/cases", tags=["cases"])
app.include_router(agents.router, prefix="/api/cases", tags=["agents"])
app.include_router(human_gate.router, prefix="/api/cases", tags=["human_gate"])


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "A2A智能理赔助手"}
