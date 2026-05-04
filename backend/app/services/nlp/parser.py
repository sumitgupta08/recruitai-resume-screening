"""
NLP Resume Parsing Service.

Pipeline:
  1. Extract raw text from PDF/DOCX
  2. Detect language
  3. Run spaCy NER for name, email, phone, location
  4. Skill extraction via ontology + NER + regex
  5. Experience & education extraction using section headers + rules
  6. Compute sentence-transformer embedding
  7. Compute MinHash signature for duplicate detection
"""
import io
import re
import logging
from typing import Any
from datetime import datetime

import spacy
try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
from datasketch import MinHash
from langdetect import detect, LangDetectException
import pdfminer.high_level as pdfminer
from docx import Document as DocxDocument
import fitz  # PyMuPDF - fallback

from app.core.config import settings
from .skill_ontology import SkillOntology

logger = logging.getLogger(__name__)

# ── Singleton model loading (loaded once per worker) ──────────
_nlp = None
_embedder = None
_ontology = None


def _get_nlp():
    global _nlp
    if _nlp is None:
        logger.info(f"Loading spaCy model: {settings.SPACY_MODEL}")
        _nlp = spacy.load(settings.SPACY_MODEL)
    return _nlp


def _get_embedder():
    global _embedder
    if _embedder is None:
        logger.info(f"Loading SentenceTransformer: {settings.SENTENCE_TRANSFORMER_MODEL}")
        _embedder = SentenceTransformer(settings.SENTENCE_TRANSFORMER_MODEL)
    return _embedder


def _get_ontology():
    global _ontology
    if _ontology is None:
        _ontology = SkillOntology()
    return _ontology


# ─────────────────────────────────────────────────────────────
# Text Extraction
# ─────────────────────────────────────────────────────────────

def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract text from PDF using pdfminer with PyMuPDF fallback."""
    try:
        text = pdfminer.extract_text(io.BytesIO(file_bytes))
        if text and len(text.strip()) > 100:
            return text
    except Exception as e:
        logger.warning(f"pdfminer extraction failed: {e}, trying PyMuPDF")

    # Fallback: PyMuPDF (better for scanned/complex PDFs)
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        pages = [page.get_text() for page in doc]
        return "\n".join(pages)
    except Exception as e:
        logger.error(f"PyMuPDF extraction also failed: {e}")
        raise ValueError("Could not extract text from PDF") from e


def extract_text_from_docx(file_bytes: bytes) -> str:
    """Extract text from DOCX preserving paragraph structure."""
    doc = DocxDocument(io.BytesIO(file_bytes))
    paragraphs = []
    for para in doc.paragraphs:
        if para.text.strip():
            paragraphs.append(para.text.strip())
    # Also extract tables
    for table in doc.tables:
        for row in table.rows:
            row_text = " | ".join(cell.text.strip() for cell in row.cells if cell.text.strip())
            if row_text:
                paragraphs.append(row_text)
    return "\n".join(paragraphs)


def extract_text(file_bytes: bytes, mime_type: str) -> str:
    """Route to correct extractor based on MIME type."""
    if mime_type == "application/pdf":
        return extract_text_from_pdf(file_bytes)
    elif "wordprocessingml" in mime_type:
        return extract_text_from_docx(file_bytes)
    raise ValueError(f"Unsupported MIME type: {mime_type}")


# ─────────────────────────────────────────────────────────────
# Entity Extraction
# ─────────────────────────────────────────────────────────────

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
PHONE_RE = re.compile(r"[\+]?[\d\s\-\(\)]{7,20}")
YEARS_RE = re.compile(r"(20\d{2}|19\d{2})")


def extract_contact_info(text: str, doc) -> dict[str, str | None]:
    """Extract name, email, phone from parsed spaCy doc."""
    email = next(iter(EMAIL_RE.findall(text)), None)
    phone_candidates = PHONE_RE.findall(text)
    phone = next(
        (p.strip() for p in phone_candidates if len(re.sub(r"\D", "", p)) >= 7),
        None,
    )
    # Name: first PERSON entity in top 300 chars (usually the header)
    name = None
    for ent in doc.ents:
        if ent.label_ == "PERSON" and ent.start_char < 400:
            name = ent.text
            break
    # Location: first GPE entity
    location = next((ent.text for ent in doc.ents if ent.label_ == "GPE"), None)

    return {"name": name, "email": email, "phone": phone, "location": location}


def extract_skills(text: str) -> list[str]:
    """Extract skills using skill ontology + NER."""
    ontology = _get_ontology()
    return ontology.extract_skills(text)


# ── Section parser ────────────────────────────────────────────

SECTION_HEADERS = {
    "experience": [
        "experience", "work experience", "employment", "work history",
        "professional experience", "career history",
    ],
    "education": ["education", "academic background", "qualifications", "degrees"],
    "skills": ["skills", "technical skills", "core competencies", "expertise"],
    "projects": ["projects", "personal projects", "portfolio", "side projects"],
    "certifications": ["certifications", "certificates", "licenses"],
}


def _split_sections(text: str) -> dict[str, str]:
    """Split resume text into labelled sections based on header detection."""
    lines = text.split("\n")
    sections: dict[str, list[str]] = {"preamble": []}
    current = "preamble"

    for line in lines:
        lower = line.strip().lower().rstrip(":")
        matched = False
        for section, keywords in SECTION_HEADERS.items():
            if lower in keywords or any(kw in lower for kw in keywords):
                current = section
                sections.setdefault(current, [])
                matched = True
                break
        if not matched:
            sections.setdefault(current, []).append(line)

    return {k: "\n".join(v) for k, v in sections.items()}


def parse_experience(exp_text: str) -> tuple[list[dict], float]:
    """
    Parse experience section into structured records.
    Returns (experience_list, total_years).
    """
    experiences = []
    years_found = YEARS_RE.findall(exp_text)
    year_ints = sorted(set(int(y) for y in years_found))

    # Heuristic: sum non-overlapping year spans
    total_years = 0.0
    if len(year_ints) >= 2:
        # Pair consecutive years
        pairs = list(zip(year_ints[::2], year_ints[1::2]))
        for start, end in pairs:
            duration = min(end - start, 10)  # cap unrealistic spans
            if 0 < duration <= 40:
                total_years += duration

    # Basic block segmentation by blank lines / bullet patterns
    blocks = re.split(r"\n{2,}", exp_text.strip())
    for block in blocks[:10]:  # limit to 10 positions
        lines = [l.strip() for l in block.split("\n") if l.strip()]
        if not lines:
            continue
        entry = {"raw": block.strip(), "title": lines[0] if lines else ""}
        if len(lines) > 1:
            entry["company"] = lines[1]
        year_match = YEARS_RE.findall(block)
        if year_match:
            entry["years"] = year_match
        experiences.append(entry)

    return experiences, min(total_years, 40)


def parse_education(edu_text: str) -> list[dict]:
    """Parse education section into structured records."""
    degrees = []
    degree_patterns = [
        r"(Ph\.?D\.?|Doctorate)",
        r"(M\.?S\.?|M\.?Sc\.?|Master[s']?)",
        r"(B\.?S\.?|B\.?Sc\.?|Bachelor[s']?|B\.?E\.?|B\.?Tech\.?)",
        r"(Associate[s']?|A\.?A\.?|A\.?S\.?)",
        r"(Diploma|Certificate|Certification)",
    ]
    DEGREE_RANK = {"phd": 5, "doctorate": 5, "master": 4, "ms": 4, "msc": 4,
                   "bachelor": 3, "bs": 3, "be": 3, "btech": 3, "associate": 2,
                   "diploma": 1, "certificate": 1}

    blocks = re.split(r"\n{2,}", edu_text.strip())
    for block in blocks[:5]:
        entry: dict[str, Any] = {"raw": block.strip()}
        for pattern in degree_patterns:
            match = re.search(pattern, block, re.IGNORECASE)
            if match:
                entry["degree"] = match.group(0)
                dl = entry["degree"].lower().replace(".", "")
                entry["degree_rank"] = max(
                    (v for k, v in DEGREE_RANK.items() if k in dl), default=0
                )
                break
        year_match = YEARS_RE.findall(block)
        if year_match:
            entry["year"] = int(year_match[-1])
        lines = [l.strip() for l in block.split("\n") if l.strip()]
        if len(lines) > 1:
            entry["institution"] = lines[1]
        if entry.get("degree") or entry.get("institution"):
            degrees.append(entry)

    return degrees


# ─────────────────────────────────────────────────────────────
# Embedding & Deduplication
# ─────────────────────────────────────────────────────────────

def compute_embedding(text: str) -> list[float]:
    """Compute sentence embedding for semantic similarity."""
    embedder = _get_embedder()
    embedding = embedder.encode(text[:512], convert_to_numpy=True)  # truncate for speed
    return embedding.tolist()


def compute_minhash(text: str, num_perm: int = 128) -> list[int]:
    """Compute MinHash signature for near-duplicate detection (LSH)."""
    m = MinHash(num_perm=num_perm)
    tokens = re.findall(r"\w+", text.lower())
    # 3-shingles for better accuracy
    shingles = [" ".join(tokens[i:i+3]) for i in range(len(tokens) - 2)]
    for shingle in shingles:
        m.update(shingle.encode("utf-8"))
    return m.hashvalues.tolist()


# ─────────────────────────────────────────────────────────────
# Main entry point
# ─────────────────────────────────────────────────────────────

def parse_resume(file_bytes: bytes, mime_type: str, file_name: str) -> dict[str, Any]:
    """
    Full resume parsing pipeline.
    Returns a dict ready to populate the Resume model.
    """
    # 1. Extract text
    raw_text = extract_text(file_bytes, mime_type)

    # 2. Detect language
    try:
        language = detect(raw_text[:500])
    except LangDetectException:
        language = "en"

    # 3. spaCy NLP
    nlp = _get_nlp()
    # Truncate for NLP to avoid memory issues on large docs
    doc = nlp(raw_text[:10_000])

    # 4. Contact info
    contact = extract_contact_info(raw_text, doc)

    # 5. Section-aware parsing
    sections = _split_sections(raw_text)
    skills = extract_skills(raw_text)
    experience, total_exp_years = parse_experience(sections.get("experience", ""))
    education = parse_education(sections.get("education", ""))
    projects_raw = sections.get("projects", "")
    projects = [{"raw": b.strip()} for b in re.split(r"\n{2,}", projects_raw) if b.strip()][:10]

    # 6. Embedding
    embedding = compute_embedding(raw_text[:2000])

    # 7. MinHash for dedup
    minhash = compute_minhash(raw_text)

    return {
        "raw_text": raw_text,
        "language": language,
        "candidate_name": contact["name"],
        "candidate_email": contact["email"],
        "candidate_phone": contact["phone"],
        "candidate_location": contact["location"],
        "skills": skills,
        "experience": experience,
        "education": education,
        "projects": projects,
        "total_experience_years": total_exp_years,
        "embedding": embedding,
        "minhash_signature": minhash,
        "parse_status": "done",
    }
