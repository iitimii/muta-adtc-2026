"""Request/response models for the public `/v1` surface — the source of truth.

Kept deliberately small: the minimum endpoint surface from ROADMAP.md (16 Jul). The
`subject` axis carries physics/chemistry/biology from day one (the competition domain is
Math *and* Scientific Reasoning), so downstream consumers never have to retrofit it.
"""

from __future__ import annotations

import unicodedata
from enum import Enum
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictFloat,
    StrictInt,
    StringConstraints,
    field_validator,
    model_validator,
)
from pydantic_core import PydanticCustomError

ResourceId = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{32}$")]
CourseId = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{32}$")]
ClassPostId = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{32}$")]
ClassReplyId = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{32}$")]
AnimationStepText = Annotated[str, StringConstraints(min_length=1, max_length=120)]
AnimationInteger = StrictInt
AnimationNumber = StrictFloat


class TutoringMode(str, Enum):
    """Learner- and teacher-selectable tutoring modes."""

    socratic = "socratic"
    subgoal = "subgoal"
    analogy = "analogy"
    hints = "hints"


class Persona(str, Enum):
    teacher = "teacher"
    friend = "friend"
    professor = "professor"
    exam = "exam"  # minimal-hints exam mode


class Subject(str, Enum):
    math = "math"
    physics = "physics"
    chemistry = "chemistry"
    biology = "biology"


# --- Ops -------------------------------------------------------------------------------


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    service: str
    version: str = Field("0.0.0", description="Semantic version of the running build.")
    git_sha: str = Field("unknown", description="Commit the running image was built from.")


class ReadyResponse(BaseModel):
    ready: bool
    checks: dict[str, bool] = Field(
        default_factory=dict, description="Per-dependency readiness (llama-server, sub-apps)."
    )
    # Deliberately NOT a check: ready = all(checks), and an offline-but-healthy stack is
    # still ready — offline is a state, not a failure (design P2, 2026-08-08).
    online: bool | None = Field(
        None, description="Internet reachability; null until the first probe completes."
    )


class ProductAnalyticsConsentRequest(BaseModel):
    allowed: bool = Field(
        description=(
            "Whether the laptop operator permits pseudonymous installation heartbeats and "
            "coarse, network-derived location."
        )
    )


class ProductAnalyticsStatus(BaseModel):
    configured: bool = Field(
        description="True when this build has a fleet collector URL and ingest credential."
    )
    manageable: bool = Field(description="True only on the laptop operator's local surface.")
    consent: Literal["unknown", "granted", "declined"]
    prompt_required: bool = False
    location_mode: Literal["none", "approximate_ip"] = "none"
    last_synced_at: str | None = None
    deletion_pending: bool = False
    data_shared: list[str] = Field(default_factory=list)


class ModelBackend(BaseModel):
    """One safe backend from the local registry; browser clients never send paths."""

    id: str
    label: str
    kind: Literal["local", "cloud"]
    description: str
    available: bool
    active: bool
    disabled_reason: str | None = None
    size_bytes: int | None = None
    arc_easy: float | None = None
    audit_proxy_tps: float | None = None
    recommended: bool = False
    user_added: bool = Field(
        False,
        description="True for an operator-supplied GGUF discovered below models/custom.",
    )
    supports_images: bool = Field(
        False,
        description="True only when this model's verified projector is installed.",
    )
    image_input_reason: str | None = Field(
        None,
        description="Why image input is unavailable while text inference can still work.",
    )


class ModelCatalogResponse(BaseModel):
    active_id: str | None = None
    switching: bool = False
    selection_enabled: bool = False
    models: list[ModelBackend] = Field(default_factory=list)


class ModelSelectRequest(BaseModel):
    model_id: str = Field(min_length=1, max_length=128)


class ModelSelectResponse(ModelCatalogResponse):
    pass


# --- /chat -----------------------------------------------------------------------------


class ChatRequest(BaseModel):
    student_id: str = Field(
        max_length=128, description="Stable per-learner id; keys the learning twin."
    )
    # Input cap (prompt-bomb guard): the primary browser path was previously unbounded while
    # the sibling /tutor path capped its text — one multi-MB message blows the 2048-token
    # context and drives prefill RAM/CPU on the shared 8GB box, degrading every other student.
    message: str = Field(max_length=8000)
    conversation_id: str | None = Field(
        None,
        max_length=64,
        description="Omit to start a new thread; pass to continue one (multi-turn memory).",
    )
    client_request_id: str | None = Field(
        None,
        max_length=64,
        description=(
            "Browser-generated id for recovering a new-chat start across an immediate refresh."
        ),
    )
    mode: TutoringMode = TutoringMode.socratic
    persona: Persona = Persona.teacher
    subject: Subject = Subject.math
    language: str = Field(
        "en",
        min_length=2,
        max_length=16,
        pattern=r"^(?:auto|[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8}){0,2})$",
        description=(
            "Preferred response language as 'auto' or a BCP 47 tag (for example en, de, "
            "sw, ar, pga-Latn). Auto follows the primary language in the latest user "
            "message. The gateway places this preference in the system prompt; it does not "
            "modify the user's message."
        ),
    )
    stream: bool = Field(
        False, description="When true the server replies with an SSE token stream instead."
    )
    thinking: Literal["off", "auto", "extended"] | None = Field(
        None,
        description=(
            "Reasoning effort for this turn: 'off' answers directly (no thinking, fastest), "
            "'auto' thinks first (default behaviour), 'extended' thinks and gives a fuller "
            "answer. Null uses the server default."
        ),
    )
    regenerate: bool = Field(
        False,
        description=(
            "Re-answer the current last user turn WITHOUT adding a new user message. Used by "
            "'answer now' to replace an in-flight reply (e.g. skip the thinking phase)."
        ),
    )
    continue_reply: bool = Field(
        False,
        description=(
            "Extend the conversation's interrupted final answer in place WITHOUT adding a user "
            "message (streamed generations only; requires conversation_id). The stored question "
            "is re-used for retrieval and `message` is ignored. The stream first sends a "
            "`replace` event carrying the stored answer, then only the new text."
        ),
    )
    use_web: bool = Field(
        False,
        description=(
            "Opt-in web grounding: when the box is online and a search endpoint is "
            "configured, the answer is grounded with fresh snippets and their sources "
            "are returned. Ignored (silently) offline or unconfigured."
        ),
    )
    use_rag: bool = Field(
        False,
        description=(
            "Opt-in retrieval over learner-owned resources. When enabled, resource_ids must "
            "identify the ready files selected with the chat @ picker."
        ),
    )
    resource_ids: list[ResourceId] = Field(
        default_factory=list,
        max_length=8,
        description=(
            "Opaque ids of learner-owned resources selected for this turn. Display names are "
            "never used for authorization or retrieval scope."
        ),
    )
    attachment_ids: list[int] = Field(
        default_factory=list,
        max_length=32,
        description="Previously-uploaded attachments to link to this message.",
    )
    course_id: CourseId | None = Field(
        None,
        description=(
            "Optional Muta Share course. The gateway resolves its teacher policy server-side; "
            "a locked course overrides the request mode."
        ),
    )


class ResourceCitation(BaseModel):
    resource_id: ResourceId
    title: str
    page: int = Field(
        ge=1,
        description=(
            "One-based physical PDF page number; for Markdown/text resources, the one-based "
            "section ordinal shown by GET /v1/resources/{id}/sections."
        ),
    )
    chunk_index: int = Field(ge=0)
    excerpt: str = Field(max_length=500)
    section: str | None = Field(
        None,
        max_length=400,
        description=(
            "Markdown/text resources only: the cited section's heading path joined with ' › ' "
            "(empty for an untitled passage). Null for PDF citations."
        ),
    )


class ChatResponse(BaseModel):
    student_id: str
    conversation_id: str = Field(
        description="Pass back in the next request to continue the thread."
    )
    mode: TutoringMode
    reply: str = Field(
        description=(
            "Assistant Markdown. A visual text turn may end with one fenced `muta-viz` JSON "
            "object; clients may validate/render it as documented in docs/api/EXAMPLES.md."
        )
    )
    verified: bool = Field(
        False, description="Whether math in the reply was checked by the `math` service."
    )
    citations: list[str] = Field(default_factory=list, description="RAG source references.")
    resource_citations: list[ResourceCitation] = Field(
        default_factory=list,
        description=(
            "Structured, server-owned citations into uploaded learner resources, numbered by "
            "the reply's [R#] markers. When a grounded reply contains no marker, these are the "
            "strongest passages it was grounded on (sources consulted), not inline citations."
        ),
    )


# --- /animation/plan -------------------------------------------------------------------


class AnimationPlanRequest(BaseModel):
    """A bounded lesson brief for the installed local model."""

    model_config = ConfigDict(extra="forbid")

    student_id: str = Field(max_length=128)
    topic: str = Field(min_length=1, max_length=240)
    level: Literal["early-primary", "upper-primary", "secondary", "tertiary"]
    concept: str = Field(default="", max_length=240)
    requirements: str = Field(default="", max_length=1000)

    @field_validator("topic")
    @classmethod
    def topic_must_have_visible_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("topic must contain visible text")
        return value


class AnimationProcessData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    steps: list[AnimationStepText] = Field(min_length=2, max_length=8)
    active: AnimationInteger = Field(ge=0, le=7)

    @field_validator("steps")
    @classmethod
    def steps_must_be_bounded_visible_text(cls, values: list[str]) -> list[str]:
        normalized: list[str] = []
        for value in values:
            value = value.strip()
            if not value:
                raise ValueError("process steps must contain visible text")
            categories = [unicodedata.category(character) for character in value]
            if any(category in {"Cc", "Cf"} for category in categories):
                raise ValueError("process steps cannot contain control or format characters")
            if not any(category[0] in {"L", "N", "P", "S"} for category in categories):
                raise ValueError("process steps must contain a visible base character")
            normalized.append(value)
        return normalized

    @model_validator(mode="after")
    def active_step_exists(self) -> AnimationProcessData:
        if self.active >= len(self.steps):
            raise ValueError("active process step must exist")
        return self


class AnimationFractionData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    numerator: AnimationInteger = Field(ge=0, le=48)
    denominator: AnimationInteger = Field(ge=2, le=12)
    phase: Literal["partition", "shade", "recap"]

    @field_validator("denominator")
    @classmethod
    def numerator_fits_four_bars(cls, value: int, info) -> int:
        numerator = info.data.get("numerator")
        if numerator is not None and numerator > value * 4:
            raise ValueError("fraction may use at most four whole bars")
        return value


class AnimationArrayData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rows: AnimationInteger = Field(ge=1, le=12)
    columns: AnimationInteger = Field(ge=1, le=12)
    phase: Literal["build", "addition", "equation"]


class AnimationDivisionData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dividend: AnimationInteger = Field(ge=0, le=144)
    divisor: AnimationInteger = Field(ge=1, le=12)
    phase: Literal["count", "share", "recap"]

    @model_validator(mode="after")
    def readable_quotient(self) -> AnimationDivisionData:
        if self.dividend // self.divisor > 12:
            raise ValueError("equal-sharing diagrams support at most twelve objects per group")
        return self


class AnimationFunctionData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expression_ast: dict[str, Any]
    expression_text: str = Field(min_length=1, max_length=180)
    domain: tuple[AnimationNumber, AnimationNumber]
    variable: Literal["x", "t"]
    output: Literal["y", "z", "s", "v"]
    mode: Literal["curve", "derivative", "integral"]
    parameter: AnimationNumber | None = Field(default=None, ge=-1000, le=1000)
    bounds: tuple[AnimationNumber, AnimationNumber] | None = None

    @field_validator("expression_ast")
    @classmethod
    def expression_numbers_are_strict_json_numbers(cls, value: dict[str, Any]) -> dict[str, Any]:
        stack: list[Any] = [value]
        visited = 0
        while stack:
            current = stack.pop()
            visited += 1
            if visited > 256:
                raise ValueError("function expression exceeds the structural budget")
            if isinstance(current, dict):
                if current.get("type") == "number":
                    number = current.get("value")
                    if isinstance(number, bool) or not isinstance(number, (int, float)):
                        raise ValueError("function expression numbers must be JSON numbers")
                stack.extend(current.values())
            elif isinstance(current, list):
                stack.extend(current)
        return value

    @field_validator("domain")
    @classmethod
    def domain_is_bounded_and_ordered(cls, value: tuple[float, float]) -> tuple[float, float]:
        if not all(-1000 <= item <= 1000 for item in value) or value[0] >= value[1]:
            raise ValueError("function domain must be a bounded increasing pair")
        return value

    @model_validator(mode="after")
    def mode_fields_are_consistent(self) -> AnimationFunctionData:
        if self.mode == "derivative":
            if self.parameter is None or not self.domain[0] <= self.parameter <= self.domain[1]:
                raise ValueError("derivative parameter must lie inside the function domain")
            if self.bounds is not None:
                raise ValueError("derivative scenes do not accept integral bounds")
        elif self.mode == "integral":
            if (
                self.bounds is None
                or self.bounds[0] == self.bounds[1]
                or not all(self.domain[0] <= value <= self.domain[1] for value in self.bounds)
            ):
                raise ValueError("integral bounds must be distinct points inside the domain")
            if self.parameter is not None:
                raise ValueError("integral scenes do not accept a derivative parameter")
        elif self.parameter is not None or self.bounds is not None:
            raise ValueError("curve scenes do not accept calculus probe fields")
        return self


class AnimationVectorData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    x: AnimationNumber = Field(ge=-1000, le=1000)
    y: AnimationNumber = Field(ge=-1000, le=1000)
    label: str = Field(min_length=1, max_length=80)


class AnimationCircleData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    radius: AnimationNumber = Field(ge=0.001, le=1000, multiple_of=0.000001)
    phase: Literal["construct", "radius"]

    @field_validator("radius")
    @classmethod
    def radius_has_at_most_six_decimal_places(cls, value: float) -> float:
        canonical = round(float(value) * 1_000_000) / 1_000_000
        if abs(float(value) - canonical) > 1e-12:
            raise ValueError("circle radius must have at most six decimal places")
        return value


class _AnimationSceneBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{0,79}$")
    title: str = Field(min_length=1, max_length=140)
    narration: str = Field(min_length=1, max_length=700)
    duration_ms: AnimationInteger = Field(ge=900, le=10000)


class AnimationProcessScene(_AnimationSceneBase):
    kind: Literal["process"] = "process"
    data: AnimationProcessData


class AnimationFractionScene(_AnimationSceneBase):
    kind: Literal["fraction"] = "fraction"
    data: AnimationFractionData


class AnimationArrayScene(_AnimationSceneBase):
    kind: Literal["array"] = "array"
    data: AnimationArrayData


class AnimationDivisionScene(_AnimationSceneBase):
    kind: Literal["division"] = "division"
    data: AnimationDivisionData


class AnimationFunctionScene(_AnimationSceneBase):
    kind: Literal["function"] = "function"
    data: AnimationFunctionData


class AnimationVectorScene(_AnimationSceneBase):
    kind: Literal["vector"] = "vector"
    data: AnimationVectorData


class AnimationCircleScene(_AnimationSceneBase):
    kind: Literal["circle"] = "circle"
    data: AnimationCircleData


AnimationPlanScene = Annotated[
    AnimationProcessScene
    | AnimationFractionScene
    | AnimationArrayScene
    | AnimationDivisionScene
    | AnimationFunctionScene
    | AnimationVectorScene
    | AnimationCircleScene,
    Field(discriminator="kind"),
]


class AnimationPlanProject(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: Literal[1] = 1
    kind: Literal["lesson-animation"] = "lesson-animation"
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{0,79}$")
    title: str = Field(min_length=1, max_length=180)
    topic: str = Field(min_length=1, max_length=240)
    level: Literal["early-primary", "upper-primary", "secondary", "tertiary"]
    summary: str = Field(min_length=1, max_length=700)
    created_at: str = Field(min_length=1, max_length=40)
    updated_at: str = Field(min_length=1, max_length=40)
    scenes: list[AnimationPlanScene] = Field(min_length=1, max_length=10)

    @field_validator("version", mode="before")
    @classmethod
    def version_is_strict_integer_one(cls, value: Any) -> Any:
        if isinstance(value, bool) or not isinstance(value, int):
            raise PydanticCustomError(
                "animation_version_type", "animation version must be integer 1"
            )
        return value

    @model_validator(mode="after")
    def scene_budget_is_bounded(self) -> AnimationPlanProject:
        if len({scene.id for scene in self.scenes}) != len(self.scenes):
            raise ValueError("scene identifiers must be unique")
        if sum(scene.duration_ms for scene in self.scenes) > 60000:
            raise ValueError("animation duration exceeds one minute")
        return self


class AnimationSourceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project: AnimationPlanProject


class AnimationSourceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str
    filename: str
    renderer: Literal["manim"] = "manim"


class AnimationRenderCapability(BaseModel):
    model_config = ConfigDict(extra="forbid")

    available: bool
    renderer: Literal["manim"] = "manim"
    detail: str
    program_available: bool = False
    program_detail: str = "Isolated model-authored Manim is not available in this build."


class AnimationProgramRequest(AnimationPlanRequest):
    """One local-model Manim authoring/repair turn; source is never trusted for execution."""

    concept: str = Field(default="", max_length=1600)
    previous_source: str = Field(default="", max_length=24000)
    feedback: str = Field(default="", max_length=1200)


class AnimationProgram(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: Literal[1] = 1
    kind: Literal["manim-program"] = "manim-program"
    id: str = Field(pattern=r"^program-[a-f0-9]{24}$")
    title: str = Field(min_length=1, max_length=180)
    level: Literal["early-primary", "upper-primary", "secondary", "tertiary"]
    source: str = Field(min_length=1, max_length=24000)
    source_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    model_id: str = Field(default="", max_length=180)
    generation_token: str = Field(default="", pattern=r"^(?:[a-f0-9]{64})?$")
    created_at: str = Field(min_length=1, max_length=64)
    brief: str = Field(min_length=1, max_length=20000)


class AnimationProgramResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    program: AnimationProgram


class AnimationProgramRenderRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    program: AnimationProgram


class AnimationPlanResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project: AnimationPlanProject
    repaired: bool = False


class GenerationStarted(BaseModel):
    """A server-owned generation that can be re-subscribed after browser navigation."""

    job_id: str
    conversation_id: str
    client_request_id: str | None = None
    state: Literal["queued", "running"] = "running"
    queue_position: int = 0


class GenerationStatus(BaseModel):
    job_id: str
    conversation_id: str
    state: Literal["queued", "running", "completed", "failed", "stopped"]
    created_at: str
    client_request_id: str | None = None
    queue_position: int = 0


class GenerationList(BaseModel):
    generations: list[GenerationStatus] = Field(default_factory=list)


class GenerationStopped(BaseModel):
    job_id: str
    stopping: bool


class UserSettings(BaseModel):
    """Learner-facing product preferences stored with the existing private user record."""

    allow_parallel_chats: bool = Field(
        True,
        description=(
            "Allow a learner to use more than one of the operator-budgeted inference slots "
            "across separate conversations. This never changes the server's slot/RAM ceiling."
        ),
    )
    power_optimization_enabled: bool = Field(
        True,
        description=(
            "Use battery-aware response limits for this learner when the host is discharging. "
            "Memory, thermal and critical host safeguards cannot be disabled."
        ),
    )
    preferred_style: TutoringMode = Field(
        TutoringMode.socratic,
        description=(
            "Teaching strategy used for a new conversation. Existing conversations retain "
            "their own mode."
        ),
    )
    study_country: str | None = Field(
        None,
        min_length=2,
        max_length=2,
        pattern=r"^[A-Z]{2}$",
        description=(
            "Optional ISO 3166-1 alpha-2 African study country used only for locally relevant "
            "currency and exam framing. It never changes factual or mathematical truth."
        ),
    )


# --- Muta Share (offline LAN accounts + host control) ---------------------------------


class ShareStatus(BaseModel):
    enabled: bool = False
    secure: bool = False
    authenticated: bool = False
    role: Literal["host", "member"] | None = None
    user_id: str | None = None
    username: str | None = None
    join_url: str | None = None
    message: str = ""


class ShareCredentials(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=8, max_length=256)


class ShareSignupResponse(BaseModel):
    enrollment_id: str
    enrollment_secret: str = Field(
        description="One-time secret used only to poll/exchange this approval request."
    )
    status: Literal["pending"] = "pending"
    username: str
    expires_at: str


class ShareEnrollmentExchange(BaseModel):
    secret: str = Field(min_length=32, max_length=128)


class ShareEnrollmentResponse(BaseModel):
    status: Literal["pending", "approved", "rejected", "removed", "expired"]
    username: str | None = None
    authenticated: bool = False
    user_id: str | None = None
    can_login: bool = False


class ShareSessionResponse(BaseModel):
    authenticated: bool = True
    user_id: str
    username: str
    role: Literal["member"] = "member"
    expires_at: str


class ShareLogoutResponse(BaseModel):
    logged_out: bool = True


class ShareUser(BaseModel):
    id: str
    username: str
    status: Literal["pending", "approved", "deleting"]
    created_at: str
    approved_at: str | None = None
    last_login_at: str | None = None


class ShareHostUpdate(BaseModel):
    enabled: bool
    memory_mode: Literal["competition", "system"] = "competition"


class ShareHostStatus(BaseModel):
    enabled: bool
    memory_mode: Literal["competition", "system"]
    listener_running: bool = False
    join_urls: list[str] = Field(default_factory=list)
    certificate_fingerprint: str | None = None
    users: list[ShareUser] = Field(default_factory=list)
    capacity: dict = Field(default_factory=dict)
    updated_at: str
    warning: str | None = None


class ShareUserAction(BaseModel):
    id: str
    status: Literal["approved", "rejected", "removed"]
    erased: dict[str, int] = Field(default_factory=dict)


CourseTeachingStyle = Literal["socratic", "subgoal", "analogy", "hints"]


class ShareCourseWrite(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    teaching_style: CourseTeachingStyle = "socratic"
    lock_style: bool = False
    withhold_final_answers: bool = False
    teacher_note: str = Field("", max_length=400)


class ShareCourse(ShareCourseWrite):
    id: CourseId
    created_at: str
    updated_at: str


class ShareCourseList(BaseModel):
    courses: list[ShareCourse] = Field(default_factory=list)


class ShareCourseDeleted(BaseModel):
    id: CourseId
    deleted: bool = True


class ShareClassAuthor(BaseModel):
    id: str
    username: str


class ShareClassPostCreate(BaseModel):
    body: str = Field(min_length=1, max_length=4000)
    addressed_to_teacher: bool = False


class ShareClassReplyCreate(BaseModel):
    body: str = Field(min_length=1, max_length=4000)


class ShareClassReplyVerification(BaseModel):
    verified: bool = True


class ShareClassReply(BaseModel):
    id: ClassReplyId
    post_id: ClassPostId
    author: ShareClassAuthor
    body: str
    teacher_verified: bool = False
    verified_at: str | None = None
    created_at: str
    updated_at: str


class ShareClassPost(BaseModel):
    id: ClassPostId
    author: ShareClassAuthor
    body: str
    addressed_to_teacher: bool = False
    reply_count: int = Field(0, ge=0)
    verified_reply_count: int = Field(0, ge=0)
    created_at: str
    updated_at: str


class ShareClassPostList(BaseModel):
    posts: list[ShareClassPost] = Field(default_factory=list)


class ShareClassThread(BaseModel):
    post: ShareClassPost
    replies: list[ShareClassReply] = Field(default_factory=list)


class ShareClassPostDeleted(BaseModel):
    id: ClassPostId
    deleted: bool = True


class PowerStatus(BaseModel):
    """Battery state of the laptop serving Muta, plus the effective learner policy."""

    optimization_enabled: bool = True
    available: bool = False
    mode: Literal["normal", "eco", "critical"] = Field(
        "normal", description="Effective response policy for this learner."
    )
    host_mode: Literal["normal", "eco", "critical"] = Field(
        "normal", description="Shared serving laptop state before the learner preference."
    )
    on_battery: bool | None = None
    external_power_connected: bool | None = None
    charging: bool | None = None
    percentage: float | None = Field(None, ge=0, le=100)
    energy_wh: float | None = Field(None, ge=0)
    energy_full_wh: float | None = Field(None, ge=0)
    energy_rate_w: float | None = Field(None, ge=0)
    time_to_empty_s: int | None = Field(None, ge=0)
    source: str = "unavailable"
    actions: list[str] = Field(default_factory=list)


# --- /diagnose -------------------------------------------------------------------------


class DiagnoseRequest(BaseModel):
    student_id: str
    subject: Subject = Subject.math
    topic: str | None = Field(None, description="Optional focus; otherwise diagnose broadly.")


class DiagnoseResponse(BaseModel):
    student_id: str
    weak_topics: list[str] = Field(default_factory=list)
    plan: list[str] = Field(default_factory=list, description="Concrete next steps (e.g. 7-day).")


# --- /generate_question ----------------------------------------------------------------


class GenerateQuestionRequest(BaseModel):
    subject: Subject = Subject.math
    topic: str
    difficulty: int = Field(3, ge=1, le=5)
    exam_board: str = "WAEC"
    count: int = Field(1, ge=1, le=20)


class GeneratedQuestion(BaseModel):
    question_text: str
    options: list[str] | None = Field(None, description="Present for objective (Paper 1) items.")
    correct_answer: str
    worked_solution: str
    marking_scheme: str | None = Field(None, description="Method + answer marks (Paper 2).")
    topic_tags: list[str] = Field(default_factory=list)
    difficulty: int = Field(3, ge=1, le=5)


class GenerateQuestionResponse(BaseModel):
    questions: list[GeneratedQuestion] = Field(default_factory=list)


# --- /mastery/{student_id} -------------------------------------------------------------


class MasteryResponse(BaseModel):
    student_id: str
    subject: Subject
    mastery: dict[str, float] = Field(
        default_factory=dict, description="topic_id -> mastery in [0, 1] on the curriculum DAG."
    )
    next_topic: str | None = Field(None, description="Next-best lesson given prerequisites.")


# --- /verify (SymPy) -------------------------------------------------------------------


class VerifyRequest(BaseModel):
    expression: str = Field(description="A claim/step to check, e.g. 'd/dx(x^2) == 2*x'.")
    context: str | None = Field(None, description="Optional assumptions/variable domains.")


class VerifyResponse(BaseModel):
    verified: bool
    normalized: str | None = Field(None, description="Canonical form the checker computed.")
    detail: str | None = Field(None, description="Why it failed, when it did.")


# --- /tutor/* — the TDD §7.2 surface ----------------------------------------------------
# Added alongside the original endpoints rather than replacing them: the contract rule is
# additive-only from 2026-08-01, and existing clients (the TUI, bench/) already bind to
# /chat and /verify. Same shapes, different entry points.


class TutorMode(str, Enum):
    """TDD Appendix D. `dialogue` and `solution` differ in sampling (§6.5), `marking` also in
    grammar, `hint` also in which model answers (§7.6)."""

    dialogue = "dialogue"
    solution = "solution"
    marking = "marking"
    hint = "hint"


class ChatTurn(BaseModel):
    session_id: str = Field(description="One student's tutoring session; keys slot + twin.")
    text: str = Field(max_length=4096, description="Input cap per turn (S12: prompt-bomb guard).")
    mode: TutorMode = TutorMode.dialogue
    lang: str = Field(
        "en",
        min_length=2,
        max_length=16,
        pattern=r"^(?:auto|[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8}){0,2})$",
        description=(
            "Preferred response language as 'auto' or a BCP 47 tag. It is generation "
            "metadata and is never added to the learner's text."
        ),
    )
    student_id: str | None = Field(None, description="Defaults to session_id when omitted.")
    stream: bool = Field(
        False,
        description=(
            "Kept for client symmetry. Token streaming has its own path — POST "
            "/v1/tutor/chat/stream (text/event-stream) — because one operation cannot "
            "honestly declare two response media types in the schema."
        ),
    )


class TutorReply(BaseModel):
    session_id: str
    reply: str = Field(
        description="Assistant Markdown, optionally ending in one fenced `muta-viz` JSON object."
    )
    mode: TutorMode
    verified: bool = False
    citations: list[str] = Field(default_factory=list)
    queued: bool = Field(False, description="True when the turn waited for a slot (§8.2).")
    queue_position: int = 0
    degradation_level: str = Field("L0", description="Ladder level at the time of the turn (§5.3).")


class VisionReply(BaseModel):
    session_id: str
    transcription: str = Field(
        "",
        description="Deprecated; images are now sent directly with a chat turn.",
    )
    analysis: str = ""
    accepted: bool = Field(True, description="False when the image upload guard refused it.")
    detail: str = Field("", description="Upload outcome in words a student can act on.")
    attachment_id: int | None = Field(
        None, description="Stored image attachment; pass in ChatRequest.attachment_ids."
    )


class ImageUploadReply(BaseModel):
    attachment_id: int
    kind: Literal["image"] = "image"
    mime: Literal["image/jpeg", "image/png", "image/webp"]
    width: int = Field(ge=1)
    height: int = Field(ge=1)


class AnswerCheckRequest(BaseModel):
    candidate: str = Field(description="The answer to check — bare, boxed, or inside prose.")
    expected: str
    tolerance: float = Field(0.0, ge=0.0, le=1.0, description="Relative tolerance; 0 = exact.")


class AnswerCheckResponse(BaseModel):
    verified: bool
    checked: bool = Field(description="False when no verdict was possible — not the same as wrong.")
    normalized_candidate: str = ""
    normalized_expected: str = ""
    detail: str = ""


class ExamAnswerRequest(BaseModel):
    """Score a student's answer to a known question and move their mastery on that topic. The
    expected answer comes from the question bank, so this is real evidence — unlike free-chat
    volume, which never touches mastery."""

    student_id: str = Field(max_length=128)
    topic: str = Field(max_length=80, description="Curriculum topic the answer scores mastery on.")
    candidate: str = Field(max_length=4096, description="The student's submitted answer.")
    expected: str = Field(max_length=4096, description="The correct answer (from the question).")
    tolerance: float = Field(0.0, ge=0.0, le=1.0)


class UnitCheckpointRequest(BaseModel):
    """Answers for one server-known offline learning unit."""

    student_id: str = Field(max_length=128)
    unit_id: str = Field(min_length=1, max_length=128, pattern=r"^[a-z0-9][a-z0-9-]*$")
    answers: dict[str, Annotated[str, StringConstraints(max_length=4096)]] = Field(
        min_length=1,
        max_length=20,
        description=(
            "Question id to learner answer. The server re-scores every value against its "
            "allowlisted unit copy and never trusts browser-supplied answer keys."
        ),
    )


class UnitQuestionResult(BaseModel):
    question_id: str
    verified: bool
    checked: bool
    detail: str = ""


class UnitCheckpointResponse(BaseModel):
    unit_id: str
    topic: str
    score: float = Field(ge=0.0, le=1.0)
    mastery: float = Field(ge=0.0, le=1.0)
    checked: bool
    progress_saved: bool = Field(
        True,
        description=(
            "Whether the verified checkpoint result was recorded on the learner twin. "
            "A false value preserves the checked score while progress storage degrades."
        ),
    )
    results: list[UnitQuestionResult] = Field(default_factory=list)


class RenderRequest(BaseModel):
    kind: Literal["matplotlib", "svg"] = "matplotlib"
    code: str = Field(max_length=8192)


class RenderResponse(BaseModel):
    svg: str = ""
    ok: bool = True
    error: str = ""
    fallback_text: str = Field("", description="Description to show when rendering failed (S5).")


class SessionActionResponse(BaseModel):
    session_id: str
    action: Literal["suspend", "resume"]
    ok: bool
    detail: str = ""


class SystemStatus(BaseModel):
    """`/v1/metrics` — the local health panel's data (TDD §12). All local, no exporter."""

    degradation: dict = Field(default_factory=dict)
    sessions: dict = Field(default_factory=dict)
    vision: dict = Field(default_factory=dict)
    engine: dict = Field(default_factory=dict)


# --- conversations & attachments (web UI surface; additive) ----------------------------


class LearningResource(BaseModel):
    id: ResourceId
    name: str
    mime: Literal["application/pdf", "text/markdown", "text/plain"] = "application/pdf"
    status: Literal["processing", "ready", "failed"]
    page_count: int | None = Field(
        None,
        ge=1,
        description="PDF pages, or the number of sections in a Markdown/text resource.",
    )
    error: str | None = None
    created_at: str
    updated_at: str


class ResourceList(BaseModel):
    resources: list[LearningResource] = Field(default_factory=list)


class ResourceSection(BaseModel):
    ordinal: int = Field(ge=1, description="Matches ResourceCitation.page for this resource.")
    path: list[str] = Field(
        default_factory=list, description="Heading path; empty for an untitled passage."
    )
    level: int = Field(ge=0, le=6, description="Markdown heading level; 0 for a passage.")
    text: str = Field(description="The section's source text (Markdown or plain text).")


class ResourceSections(BaseModel):
    """A Markdown/text resource split exactly as it was indexed, for the in-app reader."""

    id: ResourceId
    name: str
    mime: Literal["text/markdown", "text/plain"]
    sections: list[ResourceSection] = Field(default_factory=list)


class ResourceDeleted(BaseModel):
    id: ResourceId
    deleted: bool = True


class AttachmentRef(BaseModel):
    id: int
    kind: Literal["image", "audio"]
    mime: str


class MessageOut(BaseModel):
    id: int
    role: str
    content: str = Field(
        description=(
            "Persisted message text. Assistant messages may include the fenced `muta-viz` "
            "protocol described in docs/api/EXAMPLES.md."
        )
    )
    created_at: str
    completion_state: Literal["complete", "streaming", "failed", "stopped"] | None = Field(
        default=None,
        description=(
            "How an assistant row ended. Null is a legacy completed row; streaming means a "
            "persisted partial whose owning process ended before terminal settlement."
        ),
    )
    attachments: list[AttachmentRef] = Field(default_factory=list)
    resource_citations: list[ResourceCitation] = Field(default_factory=list)


class ConversationOut(BaseModel):
    id: str
    student_id: str
    title: str | None = None
    # Historical tutor conversations also store TutorMode values such as
    # "dialogue" and "marking". Keep the read model open while new style
    # writes are constrained by ConversationStyleRequest.
    mode: str | None = None
    persona: Persona | None = None
    pinned: bool = False
    created_at: str
    updated_at: str


class ConversationList(BaseModel):
    conversations: list[ConversationOut] = Field(default_factory=list)


class MessageList(BaseModel):
    conversation_id: str
    mode: str | None = None
    persona: Persona | None = None
    messages: list[MessageOut] = Field(default_factory=list)


class ConversationDeleted(BaseModel):
    id: str
    deleted: bool = True


class ConversationPinRequest(BaseModel):
    pinned: bool


class ConversationPinned(BaseModel):
    id: str
    pinned: bool


class ConversationStyleRequest(BaseModel):
    mode: TutoringMode


class ConversationStyleResponse(BaseModel):
    id: str
    mode: TutoringMode


# --- auth & data-subject rights (additive) ---------------------------------------------


class AuthTokenRequest(BaseModel):
    student_id: str = Field(max_length=128, description="The per-device learner id to bind.")


class AuthTokenResponse(BaseModel):
    student_id: str
    token: str = Field(
        description=(
            "Bearer token for the /v1 data endpoints. Send as `Authorization: Bearer <token>` "
            "(or `?token=` on attachment URLs). Opaque; treat as a per-device secret."
        )
    )
    role: Literal["host", "member", "legacy"] = "legacy"
    csrf_token: str | None = None


class StudentErased(BaseModel):
    """Result of a data-subject erasure — the counts removed, for an auditable receipt."""

    student_id: str
    conversations: int = 0
    orphan_attachments: int = 0
    resources: int = 0
    settings: int = 0


class TranscribeResponse(BaseModel):
    text: str = Field(description="What the ASR heard; empty when nothing was recognised.")
    attachment_id: int | None = Field(None, description="Stored copy of the uploaded audio.")


class TelemetrySnapshot(BaseModel):
    """Per-conversation live telemetry. Unmeasurable metrics are null (the UI shows —),
    never an error: Docker-on-macOS has no CPU temperature, for example."""

    rss_gb: float = Field(description="Current RSS of the whole backend process tree.")
    peak_rss_gb: float = Field(description="Peak tree RSS since the backend started.")
    cpu_temp_c: float | None = Field(None, description="CPU package temp; null if unreadable.")
    throttled: bool | None = Field(
        None, description="temp > 85 °C; null when the temperature is unreadable."
    )
    tokens_per_second: float | None = Field(
        None, description="Rolling decode rate of this conversation's active generation."
    )
    generating: bool = False
