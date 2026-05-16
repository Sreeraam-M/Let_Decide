from fastapi import FastAPI
from pydantic import BaseModel
import simulator
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="F1 Strategy Simulator API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class StrategyRequest(BaseModel):
    year: int
    gp: str
    session_type: str
    driver: str
    decision_lap: int
    strategy: str

@app.post("/api/simulate")
def simulate_strategy(req: StrategyRequest):
    result = simulator.compare_strategies_api(
        req.year, req.gp, req.session_type, req.driver, req.decision_lap, req.strategy
    )
    return result

@app.get("/api/health")
def health_check():
    return {"status": "ok"}
