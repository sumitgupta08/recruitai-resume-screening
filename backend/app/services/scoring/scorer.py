"""
Resume Scoring & Ranking Engine.

Composite score formula:
    score = w_skill × skill_score
           + w_exp   × experience_score
           + w_edu   × education_score
           + w_sem   × semantic_score

All components are normalised to [0, 100].
SHAP-style contribution breakdown is generated for explainability.
"""
import logging
from typing import Any

import numpy as np
try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
from sklearn.metrics.pairwise import cosine_similarity

from app.core.config import settings
from app.services.nlp.skill_ontology import SkillOntology

logger = logging.getLogger(__name__)

_embedder = None
_ontology = None


def _get_embedder() -> SentenceTransformer:
    global _embedder
    if _embedder is None:
        _embedder = SentenceTransformer(settings.SENTENCE_TRANSFORMER_MODEL)
    return _embedder


def _get_ontology() -> SkillOntology:
    global _ontology
    if _ontology is None:
        _ontology = SkillOntology()
    return _ontology


# ─────────────────────────────────────────────────────────────
# Sub-score calculators
# ─────────────────────────────────────────────────────────────

def compute_skill_score(
    resume_skills: list[str],
    required_skills: list[str],
    preferred_skills: list[str] | None = None,
) -> tuple[float, dict]:
    """
    Compute skill match score with ontology expansion.
    Required skills are worth 80%, preferred 20%.
    Returns (score_0_100, gap_analysis_dict).
    """
    ontology = _get_ontology()
    preferred_skills = preferred_skills or []

    gap = ontology.compute_skill_gap(resume_skills, required_skills)
    required_score = gap["match_rate"]  # 0–1

    # Preferred skills bonus
    pref_gap = ontology.compute_skill_gap(resume_skills, preferred_skills)
    pref_score = pref_gap["match_rate"] if preferred_skills else 1.0

    final_score = (0.80 * required_score + 0.20 * pref_score) * 100

    return round(final_score, 2), gap


def compute_experience_score(
    candidate_years: float | None,
    required_years: int | None,
) -> float:
    """
    Score based on years of experience.
    Full score at or beyond required; partial below; capped at 100.
    """
    if required_years is None or required_years == 0:
        return 80.0  # no requirement = neutral score
    candidate_years = candidate_years or 0
    if candidate_years >= required_years:
        # Bonus for extra experience, max 10 extra points
        bonus = min((candidate_years - required_years) * 2, 10)
        return min(90.0 + bonus, 100.0)
    ratio = candidate_years / required_years
    return round(ratio * 90.0, 2)  # linear scale up to 90 when under-qualified


def compute_education_score(
    candidate_education: list[dict],
    required_level: str | None,
) -> float:
    """
    Score education match.
    Degree rank: PhD=5, Master=4, Bachelor=3, Associate=2, Diploma/Cert=1
    """
    LEVEL_MAP = {
        "phd": 5, "doctorate": 5,
        "master": 4, "msc": 4, "ms": 4,
        "bachelor": 3, "bs": 3, "be": 3, "btech": 3,
        "associate": 2,
        "diploma": 1, "certificate": 1,
        "any": 0,
    }
    if not required_level:
        return 75.0

    required_rank = 0
    rl = required_level.lower().replace("'s", "").replace("s", "").strip()
    for key, rank in LEVEL_MAP.items():
        if key in rl:
            required_rank = rank
            break

    if not candidate_education:
        return 10.0  # no education info parsed

    # Take highest degree
    candidate_max_rank = max(
        (e.get("degree_rank", 0) for e in candidate_education),
        default=0,
    )

    if candidate_max_rank >= required_rank:
        return 100.0
    if candidate_max_rank == required_rank - 1:
        return 70.0
    return max(30.0 - (required_rank - candidate_max_rank) * 10, 0.0)


def compute_semantic_score(
    resume_text: str,
    jd_text: str,
    resume_embedding: list[float] | None = None,
    jd_embedding: list[float] | None = None,
) -> float:
    """
    Semantic similarity between resume and JD using sentence embeddings.
    Uses cosine similarity → scaled to 0-100.
    """
    embedder = _get_embedder()

    if resume_embedding is None:
        resume_embedding = embedder.encode(resume_text[:512]).tolist()
    if jd_embedding is None:
        jd_embedding = embedder.encode(jd_text[:512]).tolist()

    r_vec = np.array(resume_embedding).reshape(1, -1)
    j_vec = np.array(jd_embedding).reshape(1, -1)
    sim = float(cosine_similarity(r_vec, j_vec)[0][0])

    # Cosine sim is [-1, 1] but text embeddings rarely go negative
    # Map [0, 1] → [0, 100] with slight curve to spread scores
    score = (sim ** 0.8) * 100
    return round(min(max(score, 0), 100), 2)


# ─────────────────────────────────────────────────────────────
# Composite scoring
# ─────────────────────────────────────────────────────────────

def compute_composite_score(
    skill_score: float,
    experience_score: float,
    education_score: float,
    semantic_score: float,
    weights: dict[str, float] | None = None,
) -> float:
    """Weighted composite score 0-100."""
    w = weights or {
        "skills": settings.WEIGHT_SKILLS,
        "experience": settings.WEIGHT_EXPERIENCE,
        "education": settings.WEIGHT_EDUCATION,
        "semantic": settings.WEIGHT_SEMANTIC,
    }
    total = (
        w["skills"] * skill_score
        + w["experience"] * experience_score
        + w["education"] * education_score
        + w["semantic"] * semantic_score
    )
    return round(min(max(total, 0), 100), 2)


# ─────────────────────────────────────────────────────────────
# Explainability (XAI)
# ─────────────────────────────────────────────────────────────

def generate_explanation(
    candidate_name: str | None,
    composite_score: float,
    skill_score: float,
    experience_score: float,
    education_score: float,
    semantic_score: float,
    matched_skills: list[str],
    missing_skills: list[str],
    candidate_years: float | None,
    required_years: int | None,
) -> str:
    """Generate a human-readable XAI explanation for the scoring decision."""
    name = candidate_name or "The candidate"
    decision = "SHORTLISTED" if composite_score >= 70 else ("REVIEW" if composite_score >= 50 else "REJECTED")

    lines = [
        f"**Decision: {decision}** (Overall Score: {composite_score:.0f}/100)\n",
        f"{name} achieved a composite score of {composite_score:.1f}/100 based on four weighted dimensions:\n",
        f"• **Skills Match ({settings.WEIGHT_SKILLS*100:.0f}% weight):** {skill_score:.0f}/100",
    ]
    if matched_skills:
        lines.append(f"  Matched: {', '.join(matched_skills[:8])}" + (" and more." if len(matched_skills) > 8 else "."))
    if missing_skills:
        lines.append(f"  Missing: {', '.join(missing_skills[:5])}" + (" and others." if len(missing_skills) > 5 else "."))

    lines.append(f"\n• **Experience ({settings.WEIGHT_EXPERIENCE*100:.0f}% weight):** {experience_score:.0f}/100")
    if required_years and candidate_years is not None:
        if candidate_years >= required_years:
            lines.append(f"  Has {candidate_years:.0f} years vs. {required_years} required — exceeds threshold.")
        else:
            lines.append(f"  Has ~{candidate_years:.0f} years vs. {required_years} required.")

    lines.append(f"\n• **Education ({settings.WEIGHT_EDUCATION*100:.0f}% weight):** {education_score:.0f}/100")
    lines.append(f"\n• **Semantic Relevance ({settings.WEIGHT_SEMANTIC*100:.0f}% weight):** {semantic_score:.0f}/100")
    lines.append("  (Contextual alignment between resume content and job description)")

    if decision == "REJECTED":
        lines.append("\n**Primary rejection factors:**")
        weak = []
        if skill_score < 50: weak.append("insufficient skill match")
        if experience_score < 50: weak.append("below required experience")
        if education_score < 50: weak.append("education below requirement")
        lines.append("  " + "; ".join(weak) if weak else "  Low overall relevance.")

    return "\n".join(lines)


def compute_shap_contributions(
    skill_score: float,
    experience_score: float,
    education_score: float,
    semantic_score: float,
) -> dict[str, float]:
    """
    Compute SHAP-style additive contributions.
    Each component's marginal contribution relative to the mean baseline (50).
    """
    BASELINE = 50.0
    w = {
        "skills": settings.WEIGHT_SKILLS,
        "experience": settings.WEIGHT_EXPERIENCE,
        "education": settings.WEIGHT_EDUCATION,
        "semantic": settings.WEIGHT_SEMANTIC,
    }
    return {
        "baseline": BASELINE,
        "skills_contribution": round(w["skills"] * (skill_score - BASELINE), 2),
        "experience_contribution": round(w["experience"] * (experience_score - BASELINE), 2),
        "education_contribution": round(w["education"] * (education_score - BASELINE), 2),
        "semantic_contribution": round(w["semantic"] * (semantic_score - BASELINE), 2),
    }


# ─────────────────────────────────────────────────────────────
# Main scoring function
# ─────────────────────────────────────────────────────────────

def score_resume_against_job(
    resume: dict[str, Any],
    job: dict[str, Any],
) -> dict[str, Any]:
    """
    Score a parsed resume against a job description.
    
    Args:
        resume: dict with keys from Resume model (skills, experience, education, embedding, ...)
        job: dict with keys from JobDescription model (required_skills, required_experience_years, ...)
    
    Returns:
        dict with all scoring components, explanation, and gap analysis.
    """
    skill_score, gap_analysis = compute_skill_score(
        resume.get("skills", []),
        job.get("required_skills", []),
        job.get("preferred_skills", []),
    )
    exp_score = compute_experience_score(
        resume.get("total_experience_years"),
        job.get("required_experience_years"),
    )
    edu_score = compute_education_score(
        resume.get("education", []),
        job.get("required_education"),
    )
    sem_score = compute_semantic_score(
        resume_text=resume.get("raw_text", "")[:2000],
        jd_text=job.get("description", "")[:2000],
        resume_embedding=resume.get("embedding"),
        jd_embedding=job.get("embedding"),
    )
    composite = compute_composite_score(skill_score, exp_score, edu_score, sem_score)
    explanation = generate_explanation(
        candidate_name=resume.get("candidate_name"),
        composite_score=composite,
        skill_score=skill_score,
        experience_score=exp_score,
        education_score=edu_score,
        semantic_score=sem_score,
        matched_skills=gap_analysis["matched"],
        missing_skills=gap_analysis["missing"],
        candidate_years=resume.get("total_experience_years"),
        required_years=job.get("required_experience_years"),
    )
    shap_values = compute_shap_contributions(skill_score, exp_score, edu_score, sem_score)

    return {
        "score": composite,
        "skill_score": skill_score,
        "experience_score": exp_score,
        "education_score": edu_score,
        "semantic_score": sem_score,
        "matched_skills": gap_analysis["matched"],
        "missing_skills": gap_analysis["missing"],
        "skill_gap_analysis": gap_analysis,
        "explanation": explanation,
        "shap_values": shap_values,
    }
