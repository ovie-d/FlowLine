"""FastAPI routes: parse → RiskConfig → core → return. Zero scoring here."""

from __future__ import annotations

import csv
import io
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeout
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from api.config import config_from_params
from api.schemas import AgentRequest, AgentResetRequest, CompareRequest
from api.sessions import get_history, reset_session, set_history
from core.agent.loop import UNAVAILABLE, run_agent
from core.assumptions import get_assumptions
from core.compare import compare, improvement_round
from core.scoring import explain_corridor, score
from core.storage import read_decisions
from core.triage import draft_triage

AGENT_TIMEOUT_S = 30.0
_AGENT_POOL = ThreadPoolExecutor(max_workers=2)

router = APIRouter()

HighQ = Annotated[float, Query(description="Consequence weight slider (1–8)")]
MediumQ = Annotated[float, Query()]
LowQ = Annotated[float, Query()]
CountOnlyQ = Annotated[bool, Query()]
TopQ = Annotated[int, Query(ge=1)]


def _cfg_or_422(
    high: float,
    medium: float,
    low: float,
    count_only: bool,
) -> Any:
    try:
        return config_from_params(
            high=high, medium=medium, low=low, count_only=count_only
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _csv_filename(*, high: float, count_only: bool) -> str:
    if count_only or high == 1:
        return "ranking_count_only.csv"
    if float(high).is_integer():
        return f"ranking_high{int(high)}.csv"
    return f"ranking_high{high}.csv".replace(".", "_")


@router.get("/health")
def health() -> dict[str, bool]:
    return {"ok": True}


@router.get("/ranking")
def ranking(
    high: HighQ = 3.0,
    medium: MediumQ = 1.5,
    low: LowQ = 1.0,
    count_only: CountOnlyQ = False,
    top: TopQ = 15,
) -> list[dict[str, Any]]:
    cfg = _cfg_or_422(high, medium, low, count_only)
    return score(cfg, top=top)


@router.get("/ranking.csv")
def ranking_csv(
    high: HighQ = 3.0,
    medium: MediumQ = 1.5,
    low: LowQ = 1.0,
    count_only: CountOnlyQ = False,
    top: TopQ = 15,
) -> StreamingResponse:
    cfg = _cfg_or_422(high, medium, low, count_only)
    rows = score(cfg, top=top)
    columns = [
        "rank",
        "corridor",
        "score",
        "n",
        "n_high",
        "confidence",
        "operator",
        "last_incident",
    ]
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({k: row.get(k) for k in columns})
    buf.seek(0)
    filename = _csv_filename(high=high, count_only=count_only)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/triage")
def triage(
    high: HighQ = 3.0,
    medium: MediumQ = 1.5,
    low: LowQ = 1.0,
    count_only: CountOnlyQ = False,
    top: TopQ = 15,
) -> dict[str, Any]:
    cfg = _cfg_or_422(high, medium, low, count_only)
    return draft_triage(cfg, top=top)


@router.get("/corridor/{name}")
def corridor(
    name: str,
    high: HighQ = 3.0,
    medium: MediumQ = 1.5,
    low: LowQ = 1.0,
    count_only: CountOnlyQ = False,
) -> dict[str, Any]:
    cfg = _cfg_or_422(high, medium, low, count_only)
    result = explain_corridor(name, cfg)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.get("/improvement")
def improvement(top: TopQ = 15) -> dict[str, Any]:
    return improvement_round(top=top)


@router.post("/compare")
def compare_configs(body: CompareRequest) -> dict[str, Any]:
    try:
        cfg_a = config_from_params(
            high=body.a.high,
            medium=body.a.medium,
            low=body.a.low,
            count_only=body.a.count_only,
        )
        cfg_b = config_from_params(
            high=body.b.high,
            medium=body.b.medium,
            low=body.b.low,
            count_only=body.b.count_only,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if body.top < 1:
        raise HTTPException(status_code=422, detail="top must be >= 1")
    return compare(cfg_a, cfg_b, top=body.top)


@router.get("/assumptions")
def assumptions() -> list[dict[str, Any]]:
    return get_assumptions()


@router.post("/agent")
def agent(body: AgentRequest) -> dict[str, Any]:
    history = get_history(body.session_id)
    future = _AGENT_POOL.submit(run_agent, body.question, history)
    try:
        result = future.result(timeout=AGENT_TIMEOUT_S)
    except FuturesTimeout:
        result = {**UNAVAILABLE, "history": history}
    new_history = result.get("history")
    if isinstance(new_history, list):
        set_history(body.session_id, new_history)
    payload: dict[str, Any] = {
        "answer": result.get("answer", ""),
        "tool_calls": result.get("tool_calls", []),
    }
    if result.get("error"):
        payload["error"] = True
    return payload


@router.post("/agent/reset")
def agent_reset(body: AgentResetRequest) -> dict[str, bool]:
    reset_session(body.session_id)
    return {"ok": True}


@router.get("/decisions")
def decisions() -> list[dict[str, Any]]:
    return read_decisions()
