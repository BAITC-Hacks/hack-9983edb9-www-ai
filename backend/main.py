from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

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
