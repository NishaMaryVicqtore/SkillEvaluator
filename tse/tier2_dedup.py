import os
from pathlib import Path
from typing import Any

import numpy as np
import yaml
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from tse.models import Tier2Result


REGISTRY_SKILLS = (
    {
        "name": "trimble-connect-bcf-manager",
        "version": "0.0.9",
        "composite_score": 85.0,
        "description": (
            "Manages BCF issue topics, clashes, and comments in Trimble Connect."
        ),
    },
    {
        "name": "tekla-drawing-exporter",
        "version": "1.2.0",
        "composite_score": 87.0,
        "description": (
            "Exports structural assembly drawings and IFC files from Tekla Structures."
        ),
    },
    {
        "name": "projectsight-budget-sync",
        "version": "2.0.0",
        "composite_score": 90.0,
        "description": (
            "Synchronizes cost codes and budget line items in ProjectSight."
        ),
    },
)

FASTEMBED_MODEL = "BAAI/bge-small-en-v1.5"


def _error_result(message: str) -> Tier2Result:
    return Tier2Result(
        status="ERROR",
        max_similarity_score=0.0,
        closest_match=None,
        recommendation=message,
        similarity_backend="none",
    )


def _load_metadata(metadata_path: Path) -> dict[str, Any]:
    with metadata_path.open(encoding="utf-8") as metadata_file:
        metadata = yaml.safe_load(metadata_file)
    if not isinstance(metadata, dict):
        raise ValueError("metadata.yaml must contain a YAML mapping")
    return metadata


def _skill_body(skill_path: Path) -> str:
    text = skill_path.read_text(encoding="utf-8")
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) == 3:
            return parts[2].strip()
    return text.strip()


def _skill_text(skill_dir: Path) -> tuple[str, str]:
    metadata_path = skill_dir / "metadata.yaml"
    skill_path = skill_dir / "SKILL.md"

    if not metadata_path.is_file():
        raise FileNotFoundError("metadata.yaml is missing")
    if not skill_path.is_file():
        raise FileNotFoundError("SKILL.md is missing")

    metadata = _load_metadata(metadata_path)
    tags = metadata.get("tags", [])
    if isinstance(tags, list):
        tags_text = " ".join(str(tag) for tag in tags)
    else:
        tags_text = str(tags)

    skill_id = str(metadata.get("id", "")).strip()
    fields = (
        metadata.get("name", ""),
        metadata.get("domain", ""),
        metadata.get("description", ""),
        tags_text,
        _skill_body(skill_path),
    )
    text = "\n".join(
        str(field).strip() for field in fields if str(field).strip()
    )
    return skill_id, text


def _registry_text(skill: dict[str, Any]) -> str:
    return str(skill["description"])


def _cosine_from_embeddings(vectors: np.ndarray) -> list[float]:
    candidate = vectors[0]
    registry_vectors = vectors[1:]
    candidate_norm = np.linalg.norm(candidate)
    registry_norms = np.linalg.norm(registry_vectors, axis=1)
    denominators = registry_norms * candidate_norm
    scores = np.divide(
        registry_vectors @ candidate,
        denominators,
        out=np.zeros_like(registry_norms, dtype=float),
        where=denominators != 0,
    )
    return [float(score) for score in scores]


def _fastembed_scores(texts: list[str]) -> list[float] | None:
    try:
        from fastembed import TextEmbedding
    except ImportError:
        return None

    previous_hf_offline = os.environ.get("HF_HUB_OFFLINE")
    previous_transformers_offline = os.environ.get("TRANSFORMERS_OFFLINE")
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    try:
        model = TextEmbedding(
            model_name=FASTEMBED_MODEL,
            local_files_only=True,
        )
        vectors = np.asarray(list(model.embed(texts)), dtype=float)
        return _cosine_from_embeddings(vectors)
    except Exception:
        return None
    finally:
        if previous_hf_offline is None:
            os.environ.pop("HF_HUB_OFFLINE", None)
        else:
            os.environ["HF_HUB_OFFLINE"] = previous_hf_offline
        if previous_transformers_offline is None:
            os.environ.pop("TRANSFORMERS_OFFLINE", None)
        else:
            os.environ["TRANSFORMERS_OFFLINE"] = previous_transformers_offline


def _tfidf_scores(texts: list[str]) -> list[float]:
    candidate_text = texts[0]
    registry_texts = texts[1:]
    candidate_fragments = [
        candidate_text,
        *(
            line.strip()
            for line in candidate_text.splitlines()
            if len(line.strip()) >= 20
        ),
    ]
    vectorizer = TfidfVectorizer(
        lowercase=True,
        stop_words="english",
        ngram_range=(1, 2),
        sublinear_tf=True,
    )
    vectors = vectorizer.fit_transform([*candidate_fragments, *registry_texts])
    candidate_vectors = vectors[: len(candidate_fragments)]
    registry_vectors = vectors[len(candidate_fragments) :]
    scores = cosine_similarity(candidate_vectors, registry_vectors).max(axis=0)
    return [float(score) for score in scores]


def _classify(score: float, closest_match: str) -> Tier2Result:
    score = max(0.0, min(1.0, score))
    if score >= 0.85:
        return Tier2Result(
            status="REJECTED_DUPLICATE",
            max_similarity_score=score,
            closest_match=closest_match,
            recommendation=(
                f"Reject: Skill is {score:.0%} similar to existing skill "
                f"'{closest_match}'. Do not create a duplicate skill; submit "
                f"an update PR to '{closest_match}' instead."
            ),
        )
    if score >= 0.60:
        return Tier2Result(
            status="WARNING_DISAMBIGUATE",
            max_similarity_score=score,
            closest_match=closest_match,
            recommendation="Refine the skill description and triggers to disambiguate it.",
        )
    return Tier2Result(
        status="PASSED_UNIQUE",
        max_similarity_score=score,
        closest_match=closest_match,
        recommendation="The skill is sufficiently distinct from the current catalog.",
    )


def run_tier2_dedup(skill_dir: Path) -> Tier2Result:
    """Compare a skill with the offline mock registry."""
    skill_dir = Path(skill_dir)
    if not skill_dir.is_dir():
        return _error_result(f"Skill directory does not exist: {skill_dir}")

    try:
        skill_id, candidate_text = _skill_text(skill_dir)
    except (OSError, UnicodeError, ValueError, yaml.YAMLError) as exc:
        return _error_result(str(exc))

    for registry_skill in REGISTRY_SKILLS:
        if skill_id == registry_skill["name"]:
            previous_version = str(registry_skill["version"])
            previous_score = float(registry_skill["composite_score"])
            return Tier2Result(
                status="VERSION_UPDATE",
                max_similarity_score=1.0,
                closest_match=registry_skill["name"],
                previous_version=previous_version,
                previous_composite_score=previous_score,
                similarity_backend="catalog-id",
                recommendation=(
                    f"Compare this update with version {previous_version}; "
                    f"Tier 3 must not regress below {previous_score:.1f}%."
                ),
            )

    texts = [candidate_text, *(_registry_text(skill) for skill in REGISTRY_SKILLS)]
    scores = _fastembed_scores(texts)
    if scores is None:
        scores = _tfidf_scores(texts)
        similarity_backend = "tfidf-local"
    else:
        similarity_backend = FASTEMBED_MODEL

    closest_index = int(np.argmax(scores))
    closest_match = REGISTRY_SKILLS[closest_index]["name"]
    result = _classify(scores[closest_index], closest_match)
    result.similarity_backend = similarity_backend
    return result
