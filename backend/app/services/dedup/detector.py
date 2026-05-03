"""
Duplicate Resume Detection using MinHash + LSH.

Uses locality-sensitive hashing (LSH) to efficiently detect near-duplicate
resumes without O(n²) comparison. Candidates with Jaccard similarity above
the threshold are flagged as duplicates.
"""
import logging
from datasketch import MinHash, MinHashLSH

logger = logging.getLogger(__name__)

MINHASH_NUM_PERM = 128
SIMILARITY_THRESHOLD = 0.80  # Jaccard similarity threshold


class DuplicateDetector:
    """
    In-memory MinHash LSH index for batch processing.
    For production, persist LSH state to Redis/DB between sessions.
    """

    def __init__(self, threshold: float = SIMILARITY_THRESHOLD):
        self.threshold = threshold
        self.lsh = MinHashLSH(threshold=threshold, num_perm=MINHASH_NUM_PERM)
        self._minhashes: dict[str, MinHash] = {}

    def add(self, resume_id: str, minhash_signature: list[int]) -> list[str]:
        """
        Add a resume to the LSH index.
        Returns list of duplicate resume IDs found.
        """
        m = MinHash(num_perm=MINHASH_NUM_PERM)
        m.hashvalues = list(minhash_signature)  # restore from stored signature

        # Query before inserting to find existing duplicates
        try:
            duplicates = self.lsh.query(m)
        except Exception:
            duplicates = []

        # Insert the new resume
        try:
            self.lsh.insert(resume_id, m)
            self._minhashes[resume_id] = m
        except Exception as e:
            logger.warning(f"LSH insert failed for {resume_id}: {e}")

        return [d for d in duplicates if d != resume_id]

    def compute_similarity(self, sig_a: list[int], sig_b: list[int]) -> float:
        """Compute Jaccard similarity between two MinHash signatures."""
        m_a = MinHash(num_perm=MINHASH_NUM_PERM)
        m_b = MinHash(num_perm=MINHASH_NUM_PERM)
        m_a.hashvalues = list(sig_a)
        m_b.hashvalues = list(sig_b)
        return m_a.jaccard(m_b)

    def batch_check(self, resumes: list[dict]) -> list[dict]:
        """
        Process a batch of resumes and flag duplicates.
        Each resume dict must have 'id' and 'minhash_signature'.
        Returns updated list with 'is_duplicate' and 'duplicate_of' fields.
        """
        results = []
        seen: dict[str, str] = {}  # minhash_key → first_resume_id (simplified)

        for resume in resumes:
            rid = resume["id"]
            sig = resume.get("minhash_signature", [])
            if not sig:
                results.append({**resume, "is_duplicate": False, "duplicate_of": None})
                continue

            dups = self.add(rid, sig)
            is_dup = len(dups) > 0
            dup_of = dups[0] if dups else None

            results.append({
                **resume,
                "is_duplicate": is_dup,
                "duplicate_of": dup_of,
            })
            if not is_dup:
                seen[rid] = rid

        return results
