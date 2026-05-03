"""
Skill Ontology Module.

Maintains a curated taxonomy of tech skills with:
  - Canonical names
  - Aliases / alternate spellings
  - Category groupings
  - Expansion rules (e.g., "React" → implies "JavaScript")

This is the knowledge backbone of skill extraction and gap analysis.
"""
import re
from functools import lru_cache

# ── Ontology definition ────────────────────────────────────────────────────────
# Format: canonical_name -> {aliases, category, implies}

SKILL_ONTOLOGY: dict[str, dict] = {
    # ── Languages ──────────────────────────────────────────────
    "Python": {"aliases": ["python3", "py"], "category": "language", "implies": []},
    "JavaScript": {"aliases": ["js", "javascript", "ecmascript", "es6", "es2015"], "category": "language", "implies": []},
    "TypeScript": {"aliases": ["ts", "typescript"], "category": "language", "implies": ["JavaScript"]},
    "Java": {"aliases": ["java"], "category": "language", "implies": []},
    "C++": {"aliases": ["cpp", "c plus plus", "c/c++"], "category": "language", "implies": []},
    "C#": {"aliases": ["csharp", "c sharp", ".net c#"], "category": "language", "implies": []},
    "Go": {"aliases": ["golang"], "category": "language", "implies": []},
    "Rust": {"aliases": ["rust-lang"], "category": "language", "implies": []},
    "Kotlin": {"aliases": ["kotlin"], "category": "language", "implies": ["Java"]},
    "Swift": {"aliases": ["swift"], "category": "language", "implies": []},
    "R": {"aliases": ["r programming", "r language"], "category": "language", "implies": []},
    "Scala": {"aliases": ["scala"], "category": "language", "implies": ["Java"]},
    "PHP": {"aliases": ["php7", "php8"], "category": "language", "implies": []},
    "Ruby": {"aliases": ["ruby"], "category": "language", "implies": []},

    # ── Web Frameworks ─────────────────────────────────────────
    "React": {"aliases": ["reactjs", "react.js", "react js"], "category": "framework", "implies": ["JavaScript"]},
    "Vue.js": {"aliases": ["vue", "vuejs", "vue js", "vue 3"], "category": "framework", "implies": ["JavaScript"]},
    "Angular": {"aliases": ["angularjs", "angular 2+", "angular2"], "category": "framework", "implies": ["TypeScript"]},
    "Next.js": {"aliases": ["nextjs", "next js"], "category": "framework", "implies": ["React"]},
    "FastAPI": {"aliases": ["fastapi"], "category": "framework", "implies": ["Python"]},
    "Django": {"aliases": ["django"], "category": "framework", "implies": ["Python"]},
    "Flask": {"aliases": ["flask"], "category": "framework", "implies": ["Python"]},
    "Spring Boot": {"aliases": ["spring", "springboot"], "category": "framework", "implies": ["Java"]},
    "Express.js": {"aliases": ["express", "expressjs"], "category": "framework", "implies": ["JavaScript"]},
    "Node.js": {"aliases": ["nodejs", "node js", "node"], "category": "framework", "implies": ["JavaScript"]},
    "GraphQL": {"aliases": ["graphql"], "category": "framework", "implies": []},

    # ── ML / AI ────────────────────────────────────────────────
    "TensorFlow": {"aliases": ["tensorflow", "tf"], "category": "ml", "implies": ["Python"]},
    "PyTorch": {"aliases": ["pytorch"], "category": "ml", "implies": ["Python"]},
    "scikit-learn": {"aliases": ["sklearn", "scikit learn"], "category": "ml", "implies": ["Python"]},
    "Keras": {"aliases": ["keras"], "category": "ml", "implies": ["Python"]},
    "Hugging Face": {"aliases": ["huggingface", "transformers"], "category": "ml", "implies": ["Python"]},
    "BERT": {"aliases": ["bert", "roberta", "distilbert"], "category": "ml", "implies": ["Hugging Face"]},
    "LangChain": {"aliases": ["langchain"], "category": "ml", "implies": ["Python"]},
    "OpenCV": {"aliases": ["opencv", "cv2"], "category": "ml", "implies": []},
    "spaCy": {"aliases": ["spacy"], "category": "ml", "implies": ["Python"]},
    "XGBoost": {"aliases": ["xgboost", "lightgbm", "lgbm"], "category": "ml", "implies": []},

    # ── Databases ─────────────────────────────────────────────
    "PostgreSQL": {"aliases": ["postgres", "psql", "postgresql"], "category": "database", "implies": ["SQL"]},
    "MySQL": {"aliases": ["mysql"], "category": "database", "implies": ["SQL"]},
    "SQL": {"aliases": ["sql", "t-sql", "plsql"], "category": "database", "implies": []},
    "MongoDB": {"aliases": ["mongo", "mongodb"], "category": "database", "implies": []},
    "Redis": {"aliases": ["redis"], "category": "database", "implies": []},
    "Elasticsearch": {"aliases": ["elastic", "elasticsearch", "opensearch"], "category": "database", "implies": []},
    "Cassandra": {"aliases": ["cassandra", "apache cassandra"], "category": "database", "implies": []},
    "DynamoDB": {"aliases": ["dynamodb"], "category": "database", "implies": []},
    "Snowflake": {"aliases": ["snowflake"], "category": "database", "implies": []},
    "BigQuery": {"aliases": ["bigquery", "bq"], "category": "database", "implies": []},

    # ── Cloud & DevOps ─────────────────────────────────────────
    "AWS": {"aliases": ["amazon web services", "aws cloud"], "category": "cloud", "implies": []},
    "GCP": {"aliases": ["google cloud", "google cloud platform"], "category": "cloud", "implies": []},
    "Azure": {"aliases": ["microsoft azure", "azure cloud"], "category": "cloud", "implies": []},
    "Docker": {"aliases": ["docker"], "category": "devops", "implies": []},
    "Kubernetes": {"aliases": ["k8s", "kubernetes"], "category": "devops", "implies": ["Docker"]},
    "Terraform": {"aliases": ["terraform", "tf"], "category": "devops", "implies": []},
    "GitHub Actions": {"aliases": ["github actions", "gh actions"], "category": "devops", "implies": []},
    "Jenkins": {"aliases": ["jenkins"], "category": "devops", "implies": []},
    "Ansible": {"aliases": ["ansible"], "category": "devops", "implies": []},
    "CI/CD": {"aliases": ["ci/cd", "cicd", "continuous integration", "continuous deployment"], "category": "devops", "implies": []},

    # ── Data Engineering ───────────────────────────────────────
    "Apache Spark": {"aliases": ["spark", "pyspark"], "category": "data", "implies": []},
    "Apache Kafka": {"aliases": ["kafka"], "category": "data", "implies": []},
    "Airflow": {"aliases": ["apache airflow", "airflow"], "category": "data", "implies": ["Python"]},
    "dbt": {"aliases": ["dbt", "data build tool"], "category": "data", "implies": ["SQL"]},
    "Pandas": {"aliases": ["pandas"], "category": "data", "implies": ["Python"]},
    "NumPy": {"aliases": ["numpy"], "category": "data", "implies": ["Python"]},

    # ── Soft skills ────────────────────────────────────────────
    "Agile": {"aliases": ["agile", "scrum", "kanban", "sprint"], "category": "methodology", "implies": []},
    "System Design": {"aliases": ["system design", "distributed systems"], "category": "methodology", "implies": []},
    "REST API": {"aliases": ["rest", "restful", "rest api", "api design"], "category": "methodology", "implies": []},
    "Microservices": {"aliases": ["microservices", "microservice"], "category": "methodology", "implies": []},
}


class SkillOntology:
    """Skill extraction and ontology reasoning engine."""

    def __init__(self):
        # Build reverse lookup: alias (lowercase) → canonical name
        self._alias_map: dict[str, str] = {}
        for canonical, meta in SKILL_ONTOLOGY.items():
            self._alias_map[canonical.lower()] = canonical
            for alias in meta.get("aliases", []):
                self._alias_map[alias.lower()] = canonical
        # Sort by length desc for greedy matching
        self._sorted_aliases = sorted(self._alias_map.keys(), key=len, reverse=True)

    def extract_skills(self, text: str) -> list[str]:
        """Extract canonical skill names from free text."""
        text_lower = text.lower()
        found: set[str] = set()
        for alias in self._sorted_aliases:
            # Word-boundary match
            pattern = r"(?<![a-zA-Z0-9\+#])" + re.escape(alias) + r"(?![a-zA-Z0-9\+#])"
            if re.search(pattern, text_lower):
                canonical = self._alias_map[alias]
                found.add(canonical)
        return sorted(found)

    def expand_skills(self, skills: list[str]) -> list[str]:
        """
        Expand skill list using implication rules.
        e.g., ["React"] → ["React", "JavaScript"]
        """
        expanded = set(skills)
        queue = list(skills)
        while queue:
            skill = queue.pop()
            meta = SKILL_ONTOLOGY.get(skill, {})
            for implied in meta.get("implies", []):
                if implied not in expanded:
                    expanded.add(implied)
                    queue.append(implied)
        return sorted(expanded)

    def get_skill_category(self, skill: str) -> str:
        """Return category for a skill."""
        return SKILL_ONTOLOGY.get(skill, {}).get("category", "other")

    def compute_skill_gap(self, resume_skills: list[str], required_skills: list[str]) -> dict:
        """
        Compute skill gap between resume and job requirements.
        Returns matched, missing, and expanded matches.
        """
        expanded_resume = set(self.expand_skills(resume_skills))
        required_set = set(required_skills)

        matched = sorted(required_set & expanded_resume)
        missing = sorted(required_set - expanded_resume)
        bonus = sorted(expanded_resume - required_set)  # skills beyond requirements

        match_rate = len(matched) / len(required_set) if required_set else 1.0

        return {
            "matched": matched,
            "missing": missing,
            "bonus_skills": bonus,
            "match_rate": round(match_rate, 4),
            "matched_count": len(matched),
            "required_count": len(required_set),
        }

    @lru_cache(maxsize=256)
    def get_related_skills(self, skill: str) -> list[str]:
        """Get skills in the same category as the given skill."""
        category = self.get_skill_category(skill)
        return [s for s, m in SKILL_ONTOLOGY.items() if m.get("category") == category and s != skill]
