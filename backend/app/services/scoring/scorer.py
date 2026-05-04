"""
Resume Scoring & Ranking Engine.
"""
import logging
from typing import Any

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    SentenceTransformer = None

from app.core.config import settings
from app.services.nlp.skill_ontology import SkillOntology

logger = logging.getLogger(__name__)

_embedder = None
_ontology = None


def _get_embedder():
    global _embedder
    if _embedder is None:
        if SENTENCE_TRANSFORMERS_AVAILABLE:
            try:
                _embedder = SentenceTransformer(settings.SENTENCE_TRANSFORMER_MODEL)
            except Exception as e:
                logger.warning(f"Failed to load SentenceTransformer: {e}")
                _embedder = None
        else:
            _embedder = None
    return _embedder


def _get_ontology():
    global _ontology
    if _ontology is None:
        _ontology = SkillOntology()
    return _ontology


def compute_skill_score(
    resume_skills: list,
    required_skills: list,
    preferred_skills: list | None = None,
) -> tuple:
    ontology = _get_ontology()
    preferred_skills = preferred_skills or []
    gap = ontology.compute_skill_gap(resume_skills, require
