from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .ai_service import analyze_simulation
from .comparison import compare_scenarios
from .data import BUDGET, DISTRICTS, INDICATOR_METADATA, MEASURES, REQUIRED_DECISIONS
from .simulation import calculate_baseline, simulate_scenario

app = FastAPI(title="QalaAI — Akim for 5 Hours")

# Allow local HTML files and development servers during the hackathon.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


class ScenarioRequest(BaseModel):
    selections: list[dict]


class AnalysisRequest(BaseModel):
    simulation_result: dict


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/initial-state")
def initial_state() -> dict:
    return {
        "budget": BUDGET,
        "required_decisions": REQUIRED_DECISIONS,
        "baseline_score": calculate_baseline()["score"],
        "districts": DISTRICTS,
        "measures": MEASURES,
        "indicator_metadata": INDICATOR_METADATA,
    }


@app.post("/api/simulate")
def simulate(scenario: ScenarioRequest) -> dict:
    # Scenario validation and every numerical calculation belong to the engine.
    return simulate_scenario(scenario.selections)


@app.post("/api/analyze")
def analyze(request: AnalysisRequest) -> dict:
    # Verify submitted results against the engine before selecting AI explanations.
    try:
        return analyze_simulation(request.simulation_result)
    except Exception:
        # Keep unexpected service failures controlled without exposing details.
        return {"error": {
            "code": "analysis_unavailable",
            "message": "AI analysis is temporarily unavailable.",
        }}


class ComparisonRequest(BaseModel):
    selections_a: list[dict]
    selections_b: list[dict]


@app.post("/api/compare")
def compare(request: ComparisonRequest) -> dict:
    return compare_scenarios(request.selections_a, request.selections_b)
