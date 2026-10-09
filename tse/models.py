from typing import Any

from pydantic import BaseModel


class SkillMetadata(BaseModel):
    id: str
    name: str
    version: str
    author: str
    domain: str
    description: str
    tid_scopes_required: list[str]
    tags: list[str]


class TestCase(BaseModel):
    id: str
    category: str
    user_prompt: str
    expected_behavior: dict[str, Any]


class Tier1Result(BaseModel):
    passed: bool
    violations: list[str]


class Tier2Result(BaseModel):
    status: str
    max_similarity_score: float
    closest_match: str | None
    recommendation: str
    similarity_backend: str = "unknown"
    previous_version: str | None = None
    previous_composite_score: float | None = None


class Tier3Result(BaseModel):
    composite_score: float
    control_composite_score: float
    uplift_score: float
    correctness: float
    discoverability: float
    efficiency: float
    tool_reliability: float
    safety: float
    case_count: int
    passed: bool


class OverallEvalReport(BaseModel):
    skill_id: str
    skill_version: str
    author: str
    skill_hash: str
    agl_manifest: str | None = None
    overall_passed: bool
    tier1: Tier1Result
    tier2: Tier2Result | None = None
    tier3: Tier3Result | None = None
