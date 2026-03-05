from fastapi import APIRouter, Depends, FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

from app.schemas import (
    AdvisorChatRequest,
    AdvisorChatResponse,
    HealthResponse,
    LearningEntry,
    LearningEntryInput,
    LiveSimulationRequest,
    SimulationRequest,
)
from app.security import (
    BodySizeLimitMiddleware,
    InMemoryRateLimiter,
    RateLimitMiddleware,
    SecurityHeadersMiddleware,
    require_api_key,
)
from app.settings import get_settings
from app.service import (
    build_metadata,
    create_learning_entry,
    get_learning_entries,
    get_live_intelligence,
    run_advisor_chat,
    run_live_simulation,
    run_simulation,
)

settings = get_settings()

app = FastAPI(
    title="Sentinel - GCC Energy Escalation Simulator API",
    description=(
        "Decision-support demo translating escalation tiers into operational and "
        "financial exposure bands for GCC energy companies."
    ),
    version="0.1.0",
    docs_url="/docs" if settings.expose_docs else None,
    redoc_url="/redoc" if settings.expose_docs else None,
    openapi_url="/openapi.json" if settings.expose_docs else None,
)

allow_origins = settings.parsed_allowed_origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins if "*" not in allow_origins else ["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-API-Key"],
)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(BodySizeLimitMiddleware, max_body_bytes=settings.max_body_bytes)
app.add_middleware(
    RateLimitMiddleware,
    limiter=InMemoryRateLimiter(limit_per_minute=settings.rate_limit_per_minute),
)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


secure_router = APIRouter(dependencies=[Depends(require_api_key)])


@secure_router.get("/meta/tiers")
def metadata() -> dict:
    return build_metadata()


@secure_router.post("/simulate")
def simulate(payload: SimulationRequest) -> dict:
    company_profile = payload.company_profile.model_dump(exclude_none=True) if payload.company_profile else None
    return run_simulation(
        selected_tier=payload.tier,
        duration_days=payload.duration_days,
        trigger_inputs=payload.trigger_inputs.model_dump(),
        company_profile_override=company_profile,
    )


@secure_router.get("/intel/live")
def live_intel(
    lookback_hours: int = Query(default=72, ge=6, le=168),
    max_items: int = Query(default=40, ge=10, le=200),
    include_api_sources: bool = Query(default=True),
    providers: list[str] | None = Query(default=None),
) -> dict:
    return get_live_intelligence(
        lookback_hours=lookback_hours,
        max_items=max_items,
        providers=providers,
        include_api_sources=include_api_sources,
    )


@secure_router.post("/simulate/live")
def simulate_live(payload: LiveSimulationRequest) -> dict:
    company_profile = payload.company_profile.model_dump(exclude_none=True) if payload.company_profile else None
    return run_live_simulation(
        selected_tier=payload.tier,
        duration_days=payload.duration_days,
        trigger_inputs=payload.trigger_inputs.model_dump(),
        company_profile_override=company_profile,
        lookback_hours=payload.live_intel.lookback_hours,
        max_items=payload.live_intel.max_items,
        providers=payload.live_intel.providers,
        include_api_sources=payload.live_intel.include_api_sources,
    )


@secure_router.post("/advisor/chat", response_model=AdvisorChatResponse)
def advisor_chat(payload: AdvisorChatRequest) -> dict:
    company_profile = payload.company_profile.model_dump(exclude_none=True) if payload.company_profile else None
    return run_advisor_chat(
        selected_tier=payload.tier,
        duration_days=payload.duration_days,
        question=payload.question,
        trigger_inputs=payload.trigger_inputs.model_dump(),
        company_profile_override=company_profile,
        enable_live_intel=payload.enable_live_intel,
        lookback_hours=payload.live_intel.lookback_hours,
        max_items=payload.live_intel.max_items,
        providers=payload.live_intel.providers,
        include_api_sources=payload.live_intel.include_api_sources,
        use_ai_advisor=payload.use_ai_advisor,
    )


@secure_router.get("/learning/entries", response_model=list[LearningEntry])
def learning_entries(limit: int = Query(default=100, ge=1, le=500)) -> list[dict]:
    return get_learning_entries(limit=limit)


@secure_router.post("/learning/entries", response_model=LearningEntry)
def learning_add(payload: LearningEntryInput) -> dict:
    return create_learning_entry(payload.model_dump())


app.include_router(secure_router)
