"""FastAPI routes: parse → RiskConfig → core → return. Zero scoring here."""

from __future__ import annotations

import contextvars
import csv
import datetime as dt
import io
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeout
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from api.config import config_from_params
from api.schemas import (
    AgentRequest,
    AgentResetRequest,
    BriefingRequest,
    CompareRequest,
    CrewMapUpdate,
    DecisionCreate,
    DispatchRequest,
    ForecastRequest,
)
from api.sessions import get_history, reset_session, set_history
from core import demo, mapdata, remote_ai
from core.agent import llm
from core.agent.budget import usage_summary
from core.agent.loop import MAX_TOOL_STEPS, UNAVAILABLE, run_agent, run_briefing
from core.assumptions import get_assumptions
from core.compare import compare, improvement_for, improvement_round
from core.crews import CrewMapError, dispatch, get_crews, update_crew_map
from core.forecast import alberta_today, corridor_location, forecast, model_info
from core.insights import washout_insight
from core.pg import try_connect
from core.readiness import readiness
from core.scoring import explain_corridor, score
from core.similar import find_similar, similar_to_incident
from core.storage import append_decision, read_decisions
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


def _submit(fn, *args, **kwargs):
    """Run in the agent pool with this request's context (demo visitor id)."""
    return _AGENT_POOL.submit(contextvars.copy_context().run, fn, *args, **kwargs)


def _start_prompt() -> dict[str, Any] | None:
    """Online demo: count one AI prompt for this visitor. Returns an error payload if
    the visitor (or the whole demo) has no prompts left today, else None."""
    if not demo.enabled():
        return None
    with _db_or_503() as conn:
        try:
            demo.consume_prompt(conn)
        except demo.QuotaExceeded as exc:
            return {**UNAVAILABLE, "reason": str(exc), "quota": demo.quota_status(conn)}
    return None


def _finish_prompt(result: dict[str, Any]) -> dict[str, Any]:
    """Online demo: give the prompt back if the AI failed, and report what's left."""
    if not demo.enabled():
        return result
    with _db_or_503() as conn:
        if result.get("error"):
            demo.refund_prompt(conn)
        result["quota"] = demo.quota_status(conn)
    return result


def _db_or_503():
    conn = try_connect()
    if conn is None:
        raise HTTPException(
            status_code=503,
            detail="Database unavailable — start it with `docker compose up -d db` "
            "and load it with `python -m scripts.load_postgres`.",
        )
    return conn


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
    # utf-8-sig so Excel/Numbers open cleanly on macOS.
    payload = buf.getvalue().encode("utf-8-sig")
    return StreamingResponse(
        iter([payload]),
        media_type="text/csv; charset=utf-8",
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
def improvement(
    top: TopQ = 15,
    high: Annotated[float | None, Query()] = None,
) -> dict[str, Any]:
    if high is None:
        return improvement_round(top=top)
    cfg = _cfg_or_422(high, 1.5, 1.0, False)
    return improvement_for(cfg, top=top)


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
    if not llm.status()["available"] and remote_ai.url():
        return remote_ai.forward("/agent", body.model_dump())
    if (blocked := _start_prompt()) is not None:
        return blocked
    history = get_history(body.session_id)
    policy: dict[str, Any] | None = None
    if body.high is not None:
        if body.high == 1:
            policy = {"count_only": True}
        else:
            policy = {"high": body.high}
    future = _submit(run_agent, body.question, history, MAX_TOOL_STEPS, policy)
    try:
        result = future.result(timeout=AGENT_TIMEOUT_S)
    except FuturesTimeout:
        result = {**UNAVAILABLE, "history": history}
    new_history = result.get("history")
    if isinstance(new_history, list):
        set_history(body.session_id, new_history)
    # Handoff contract: chips only need name + input (drop bulky result).
    slim_calls: list[dict[str, Any]] = []
    for call in result.get("tool_calls", []) or []:
        if not isinstance(call, dict):
            continue
        slim_calls.append({"name": call.get("name"), "input": call.get("input", {})})
    payload: dict[str, Any] = {
        "answer": result.get("answer", ""),
        "tool_calls": slim_calls,
    }
    for key in (
        "numbers_verified",
        "unsupported_numbers",
        "provider",
        "usage",
        "reason",
    ):
        if key in result:
            payload[key] = result[key]
    if result.get("error"):
        payload["error"] = True
    return _finish_prompt(payload)


@router.post("/agent/reset")
def agent_reset(body: AgentResetRequest) -> dict[str, bool]:
    reset_session(body.session_id)
    return {"ok": True}


@router.get("/decisions")
def decisions() -> list[dict[str, Any]]:
    return read_decisions()


@router.post("/decisions")
def decisions_create(body: DecisionCreate) -> dict[str, Any]:
    """Record a planner decision directly (the 'Approve' buttons; no AI call)."""
    try:
        return append_decision(
            {
                "ts": dt.datetime.now(dt.UTC).isoformat(),
                "corridor": body.corridor,
                "action": body.action,
                "priority": body.priority,
                "reason": body.reason,
                "policy": body.policy or {},
                "source": "planner",
            }
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/demo/status")
def demo_status() -> dict[str, Any]:
    """Online demo flag, the visitor's AI prompts left today, and the demo note."""
    if not demo.enabled():
        return {"demo": False}
    with _db_or_503() as conn:
        return demo.quota_status(conn)


@router.get("/crews")
def crews() -> dict[str, Any]:
    """Hazard -> crew -> equipment table and crew bases (sample data is flagged)."""
    with _db_or_503() as conn:
        return get_crews(conn)


@router.put("/crews/map")
def crews_map(body: CrewMapUpdate) -> dict[str, Any]:
    """Replace the crews and equipment recommended for one hazard group."""
    with _db_or_503() as conn:
        try:
            crews_out = update_crew_map(
                conn,
                body.hazard_group,
                [c.model_dump(exclude_none=True) for c in body.crews],
            )
        except CrewMapError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"hazard_group": body.hazard_group, "crews": crews_out}


@router.post("/dispatch/route")
def dispatch_route(body: DispatchRequest) -> dict[str, Any]:
    """Nearest crew bases with a matching crew, ranked by drive time, with routes."""
    with _db_or_503() as conn:
        try:
            return dispatch(
                conn,
                lat=body.latitude,
                lon=body.longitude,
                hazard_group=body.hazard_group,
                k=body.k,
            )
        except CrewMapError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc


def _point_or_404(
    conn: Any, lat: float | None, lon: float | None, corridor: str | None
) -> tuple[float, float]:
    if lat is not None and lon is not None:
        return lat, lon
    if corridor:
        loc = corridor_location(conn, corridor)
        if loc is None:
            raise HTTPException(
                status_code=404, detail=f"unknown corridor {corridor!r}"
            )
        return loc
    raise HTTPException(status_code=422, detail="give lat and lon, or a corridor name")


@router.post("/forecast")
def forecast_route(body: ForecastRequest) -> dict[str, Any]:
    """Hazard-mix forecast at a point or corridor for a date (default today)."""
    with _db_or_503() as conn:
        lat, lon = _point_or_404(conn, body.latitude, body.longitude, body.corridor)
        out = forecast(
            conn,
            lat=lat,
            lon=lon,
            when=body.date or alberta_today(),
            operator_group=body.operator_group,
        )
    if body.corridor:
        out["corridor"] = body.corridor
    return out


LatQ = Annotated[float | None, Query(ge=-90, le=90)]
LonQ = Annotated[float | None, Query(ge=-180, le=180)]
WeatherQ = Annotated[float | None, Query()]


@router.get("/similar")
def similar_route(
    lat: LatQ = None,
    lon: LonQ = None,
    date: dt.date | None = None,
    k: Annotated[int, Query(ge=1, le=20)] = 5,
    incident_id: str | None = None,
    commodity: str | None = None,
    temp_mean_7d: WeatherQ = None,
    precip_30d: WeatherQ = None,
    freeze_thaw_30d: WeatherQ = None,
    snow_on_ground_d0: WeatherQ = None,
) -> dict[str, Any]:
    """Most similar past incidents (strictly before the reference date)."""
    with _db_or_503() as conn:
        if incident_id:
            out = similar_to_incident(conn, incident_id, k)
            if "error" in out:
                raise HTTPException(status_code=404, detail=out["error"])
            return out
        if lat is None or lon is None:
            raise HTTPException(
                status_code=422, detail="give lat and lon, or incident_id"
            )
        weather = {
            "temp_mean_7d": temp_mean_7d,
            "precip_30d": precip_30d,
            "freeze_thaw_30d": freeze_thaw_30d,
            "snow_on_ground_d0": snow_on_ground_d0,
        }
        return find_similar(
            conn,
            lat=lat,
            lon=lon,
            when=date or alberta_today(),
            weather=weather,
            commodity=commodity,
            k=k,
        )


@router.get("/readiness")
def readiness_route(
    lat: LatQ = None,
    lon: LonQ = None,
    corridor: str | None = None,
    start: dt.date | None = None,
    operator_group: str | None = None,
) -> dict[str, Any]:
    """Next-7-day readiness: forecast mix, recommended crews, evidence, weather context."""
    with _db_or_503() as conn:
        la, lo = _point_or_404(conn, lat, lon, corridor)
        return readiness(
            conn,
            lat=la,
            lon=lo,
            start=start or alberta_today(),
            operator_group=operator_group,
        )


@router.get("/model/info")
def model_info_route() -> dict[str, Any]:
    """'About this model': held-out performance for Canada and Alberta, plainly."""
    info = model_info()
    if "error" in info:
        raise HTTPException(status_code=503, detail=info["error"])
    return info


@router.get("/insights/washout")
def washout_route() -> dict[str, Any]:
    """Observed post-2022 washout pattern in Alberta (not a model forecast)."""
    with _db_or_503() as conn:
        return washout_insight(conn)


@router.get("/agent/status")
def agent_status() -> dict[str, Any]:
    """Whether the AI briefing/chat is available (no key = disabled, app still works)."""
    local = llm.status()
    if not local["available"] and remote_ai.url():
        remote = remote_ai.status()
        if remote and remote.get("available"):
            return {
                "available": True,
                "provider": "online demo",
                "model": remote.get("model"),
                "via_online_demo": True,
                "quota": remote.get("quota"),
            }
    out: dict[str, Any] = {**local, "usage": usage_summary()}
    if demo.enabled():
        out.pop("usage")  # spend details stay private on the public demo
        with _db_or_503() as conn:
            out["quota"] = demo.quota_status(conn)
    return out


@router.get("/agent/usage")
def agent_usage() -> dict[str, Any]:
    """Token usage and estimated spend from logs/agent_usage.jsonl (dev-console counter)."""
    if demo.enabled():
        return {"hidden": "Usage details are private on the online demo."}
    return usage_summary()


@router.post("/briefing")
def briefing(body: BriefingRequest) -> dict[str, Any]:
    """Readiness briefing written by the agent; every number comes from tool results."""
    if not llm.status()["available"]:
        if remote_ai.url():
            return remote_ai.forward("/briefing", body.model_dump(mode="json"))
        return {**UNAVAILABLE, "reason": llm.status()["reason"]}
    if (blocked := _start_prompt()) is not None:
        return blocked
    future = _submit(
        run_briefing,
        latitude=body.latitude,
        longitude=body.longitude,
        corridor=body.corridor,
        start=body.start.isoformat() if body.start else None,
        operator_group=body.operator_group,
    )
    try:
        result = future.result(timeout=AGENT_TIMEOUT_S)
    except FuturesTimeout:
        return _finish_prompt({**UNAVAILABLE, "reason": "The briefing timed out."})
    result["tool_calls"] = [
        {"name": c.get("name"), "input": c.get("input", {})}
        for c in result.get("tool_calls", [])
    ]
    return _finish_prompt(result)


@router.get("/corridors")
def corridors_route() -> list[dict[str, Any]]:
    """Ranking corridors with centroids (area search)."""
    with _db_or_503() as conn:
        return mapdata.corridors(conn)


@router.get("/map/incidents")
def map_incidents() -> dict[str, Any]:
    """All incidents as GeoJSON points, coloured by hazard group."""
    with _db_or_503() as conn:
        return mapdata.incident_points(conn)


@router.get("/map/incidents/{incident_number}")
def map_incident(incident_number: str) -> dict[str, Any]:
    """One incident for the map popup, cause codes in plain English."""
    with _db_or_503() as conn:
        detail = mapdata.incident_detail(conn, incident_number)
    if detail is None:
        raise HTTPException(status_code=404, detail="Unknown incident")
    return detail


@router.get("/map/crossings")
def map_crossings() -> dict[str, Any]:
    """Pipeline–waterway crossings (display only; empty if not built)."""
    with _db_or_503() as conn:
        return mapdata.waterway_crossings(conn)


@router.get("/map/pipelines")
def map_pipelines() -> dict[str, Any]:
    """CER pipeline systems (simplified) as GeoJSON, display only."""
    with _db_or_503() as conn:
        return mapdata.pipelines(conn)
