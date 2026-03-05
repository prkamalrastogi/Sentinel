"""Pydantic schemas for Sentinel API I/O."""

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.config import DURATION_OPTIONS_DAYS


class TriggerInputs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    terminal_strikes: float = Field(default=0, ge=0)
    blockade_alert_level: float = Field(default=0, ge=0)
    insurance_withdrawal_pct: float = Field(default=0, ge=0, le=100)


class CompanyProfileInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=2, max_length=200)
    daily_export_volume_bpd: float | None = Field(default=None, ge=0)
    fiscal_break_even_price_usd_per_bbl: float | None = Field(default=None, ge=0)
    debt_obligations_usd_bn: float | None = Field(default=None, ge=0)
    insurance_dependency_ratio: float | None = Field(default=None, ge=0, le=1)


class SimulationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tier: int = Field(..., ge=0, le=4)
    duration_days: int
    trigger_inputs: TriggerInputs = Field(default_factory=TriggerInputs)
    company_profile: CompanyProfileInput | None = None

    @field_validator("duration_days")
    @classmethod
    def validate_duration(cls, value: int) -> int:
        if value not in DURATION_OPTIONS_DAYS:
            raise ValueError(f"duration_days must be one of {DURATION_OPTIONS_DAYS}")
        return value


class LiveIntelOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lookback_hours: int = Field(default=72, ge=6, le=168)
    max_items: int = Field(default=40, ge=10, le=200)
    include_api_sources: bool = True
    providers: list[str] | None = None


class LiveSimulationRequest(SimulationRequest):
    model_config = ConfigDict(extra="forbid")

    live_intel: LiveIntelOptions = Field(default_factory=LiveIntelOptions)


class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: str = Field(..., pattern="^(user|assistant)$")
    content: str = Field(..., min_length=1, max_length=2000)


class AdvisorChatRequest(SimulationRequest):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(..., min_length=2, max_length=1000)
    enable_live_intel: bool = True
    use_ai_advisor: bool = True
    live_intel: LiveIntelOptions = Field(default_factory=LiveIntelOptions)
    chat_history: list[ChatMessage] = Field(default_factory=list, max_length=12)


class AdvisorChatResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str
    next_actions: list[str]
    next_action_reasons: list[dict[str, str]] = Field(default_factory=list)
    evidence: list[dict[str, str]]
    disclaimer: str
    advisor_mode: str
    context_snapshot: dict[str, object]


class LearningEntryInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(..., min_length=3, max_length=180)
    observation: str = Field(..., min_length=3, max_length=1500)
    action_taken: str = Field(..., min_length=3, max_length=1500)
    outcome: str = Field(..., min_length=3, max_length=1500)
    lesson: str = Field(..., min_length=3, max_length=1500)
    tags: list[str] = Field(default_factory=list, max_length=12)


class LearningEntry(LearningEntryInput):
    id: str
    created_utc: str


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
