from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .models.schemas import ChatRequest, EligibilityRequest, DisruptionRequest
from .services.data_loader import load_all
from .agent.agent import SarvamAgent
from .agent.tools import *
from .engine.recommendations import find_replacements, rank_options
from .engine.disruption import analyze_disruption


app = FastAPI(
    title="dCortex Agentic Crew Ops Advisor",
    version="1.0.0"
)

# CORS
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


DATA = load_all()
agent = SarvamAgent()


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "sarvam_configured": agent.client is not None
    }


@app.post("/api/chat")
def chat(req: ChatRequest):
    try:
        return {"answer": agent.run(req.message, req.history)}
    except Exception as e:
        print(f"Chat error: {e}")

        raise HTTPException(
            status_code=503,
            detail="The AI service is temporarily unavailable. Please try again."
        )


@app.get("/api/crew")
def crew_list(role: str | None = None):
    rows = DATA["crew"]

    if role:
        rows = [c for c in rows if c.get("rank") == role]

    return rows


@app.get("/api/crew/{crew_id}")
def crew(crew_id: str):
    rows = search_crew(crew_id=crew_id)

    if not rows:
        raise HTTPException(
            status_code=404,
            detail=f"Crew member {crew_id} not found"
        )

    return rows[0]


@app.get("/api/flights")
def flights(
    date: str | None = None,
    dep_station: str | None = None,
    arr_station: str | None = None,
    flight_no: str | None = None
):
    return search_flights(
        date,
        dep_station,
        arr_station,
        flight_no
    )


@app.get("/api/reserves")
def reserves(
    date: str | None = None,
    base: str | None = None
):
    return get_reserve_crew(date, base)


@app.get("/api/certifications")
def certifications(
    crew_id: str | None = None,
    expires_before: str | None = None
):
    return get_certifications(crew_id, expires_before)


@app.get("/api/rules")
def rules():
    return DATA["rules"]


@app.post("/api/disruptions/analyze")
def disruption(req: DisruptionRequest):
    return analyze_disruption(
        req.crew_id,
        req.date,
        DATA,
        req.pairing_id
    )


@app.post("/api/replacements/find")
def replacements(req: dict):
    return find_replacements(
        req["pairing_id"],
        req["role"],
        DATA
    )


@app.post("/api/recommendations/rank")
def rank(req: dict):
    pairing_id = req.get("pairing_id")
    role = req.get("role")

    if not pairing_id or not role:
        raise HTTPException(
            status_code=400,
            detail="pairing_id and role are required"
        )

    candidates = find_replacements(
        pairing_id,
        role,
        DATA
    )

    return rank_options(
        candidates,
        DATA
    )
    
    