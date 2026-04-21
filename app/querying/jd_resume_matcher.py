import json
import re
from typing import Any


STOPWORDS = {
    "and",
    "or",
    "for",
    "with",
    "the",
    "a",
    "an",
    "to",
    "of",
    "in",
    "on",
    "at",
    "from",
    "as",
    "is",
    "are",
    "be",
    "this",
    "that",
    "role",
    "candidate",
    "candidates",
    "job",
    "description",
}


DEGREE_KEYWORDS = [
    "b.tech",
    "btech",
    "b.e",
    "be",
    "m.tech",
    "mtech",
    "m.e",
    "me",
    "b.sc",
    "bsc",
    "m.sc",
    "msc",
    "mba",
    "phd",
    "doctorate",
]


def _safe_json_list(value: Any) -> list[str]:
    if value is None:
        return []

    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]

    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return []

        try:
            parsed = json.loads(stripped)
            if isinstance(parsed, list):
                return [str(v).strip() for v in parsed if str(v).strip()]
        except Exception:
            # Fall back to comma-separated text parsing.
            pass

        return [part.strip() for part in stripped.split(",") if part.strip()]

    return []


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9+.# ]", " ", text.lower())).strip()


def _tokenize(text: str) -> set[str]:
    tokens = set(_normalize(text).split())
    return {t for t in tokens if len(t) > 2 and t not in STOPWORDS}


def _extract_min_experience_years(jd_record: dict[str, Any]) -> float | None:
    corpus = " ".join(
        [
            str(jd_record.get("role_summary") or ""),
            str(jd_record.get("original_text") or ""),
        ]
    )

    # Capture ranges first, e.g. "3-5 years" -> min 3.
    range_matches = re.findall(r"(\d+(?:\.\d+)?)\s*[-to]{1,3}\s*(\d+(?:\.\d+)?)\s*(?:\+)?\s*(?:years|yrs)", corpus, flags=re.IGNORECASE)
    if range_matches:
        mins = [float(m[0]) for m in range_matches]
        return min(mins) if mins else None

    direct_matches = re.findall(r"(\d+(?:\.\d+)?)\s*(?:\+)?\s*(?:years|yrs)", corpus, flags=re.IGNORECASE)
    if direct_matches:
        vals = [float(v) for v in direct_matches]
        return min(vals) if vals else None

    return None


def _skill_score(required: list[str], nice_to_have: list[str], resume_skills: list[str]) -> tuple[float, list[str], list[str], list[str]]:
    req_norm = [_normalize(s) for s in required if s]
    nice_norm = [_normalize(s) for s in nice_to_have if s]
    resume_norm = {_normalize(s) for s in resume_skills if s}

    matched_required = [orig for orig, norm in zip(required, req_norm) if norm in resume_norm]
    matched_nice = [orig for orig, norm in zip(nice_to_have, nice_norm) if norm in resume_norm]
    missing_required = [orig for orig, norm in zip(required, req_norm) if norm not in resume_norm]

    req_ratio = len(matched_required) / len(required) if required else 0.0
    nice_ratio = len(matched_nice) / len(nice_to_have) if nice_to_have else 0.0

    # Give most weight to required skills; nice-to-have contributes when present.
    if required and nice_to_have:
        score = (0.8 * req_ratio) + (0.2 * nice_ratio)
    elif required:
        score = req_ratio
    elif nice_to_have:
        score = nice_ratio
    else:
        score = 0.5

    return max(0.0, min(1.0, score)), matched_required, matched_nice, missing_required


def _experience_score(min_exp: float | None, resume_exp: Any) -> float:
    if min_exp is None:
        return 0.5

    try:
        resume_exp_val = float(resume_exp or 0.0)
    except Exception:
        resume_exp_val = 0.0

    if resume_exp_val >= min_exp:
        return 1.0

    if min_exp <= 0:
        return 1.0

    return max(0.0, min(1.0, resume_exp_val / min_exp))


def _role_alignment_score(jd_record: dict[str, Any], resume_record: dict[str, Any]) -> float:
    jd_text = " ".join(
        [
            str(jd_record.get("job_title") or ""),
            str(jd_record.get("role_summary") or ""),
        ]
    )
    resume_text = " ".join(
        [
            str(resume_record.get("current_role") or ""),
            str(resume_record.get("work_experience") or ""),
        ]
    )

    jd_tokens = _tokenize(jd_text)
    resume_tokens = _tokenize(resume_text)

    if not jd_tokens:
        return 0.5

    overlap = jd_tokens.intersection(resume_tokens)
    return len(overlap) / len(jd_tokens)


def _education_score(jd_record: dict[str, Any], resume_record: dict[str, Any]) -> float:
    jd_text = _normalize(str(jd_record.get("original_text") or ""))
    resume_education = _normalize(str(resume_record.get("education") or ""))

    required_degrees = [deg for deg in DEGREE_KEYWORDS if deg in jd_text]
    if not required_degrees:
        return 0.5

    matches = [deg for deg in required_degrees if deg in resume_education]
    return len(matches) / len(required_degrees)


def _fit_label(score: float) -> str:
    if score >= 0.8:
        return "Strong fit"
    if score >= 0.65:
        return "Good fit"
    if score >= 0.5:
        return "Moderate fit"
    return "Low fit"


def rank_resumes_for_jd(
    jd_record: dict[str, Any],
    resumes: list[dict[str, Any]],
    top_k: int = 10,
) -> list[dict[str, Any]]:
    """Rank resumes against a JD using deterministic weighted scoring."""
    required_skills = _safe_json_list(jd_record.get("required_skills"))
    nice_to_have = _safe_json_list(jd_record.get("nice_to_have_skills"))
    min_exp = _extract_min_experience_years(jd_record)

    ranked: list[dict[str, Any]] = []

    for resume in resumes:
        resume_skills = _safe_json_list(resume.get("skills"))

        skill_score, matched_required, matched_nice, missing_required = _skill_score(
            required=required_skills,
            nice_to_have=nice_to_have,
            resume_skills=resume_skills,
        )
        exp_score = _experience_score(min_exp=min_exp, resume_exp=resume.get("total_experience_years"))
        role_score = _role_alignment_score(jd_record=jd_record, resume_record=resume)
        edu_score = _education_score(jd_record=jd_record, resume_record=resume)

        final_score = (
            0.55 * skill_score
            + 0.20 * exp_score
            + 0.15 * role_score
            + 0.10 * edu_score
        )

        reasons: list[str] = []
        if matched_required:
            reasons.append(f"Matched required skills: {', '.join(matched_required[:5])}")
        if matched_nice:
            reasons.append(f"Matched nice-to-have skills: {', '.join(matched_nice[:5])}")

        if min_exp is not None:
            candidate_exp = float(resume.get("total_experience_years") or 0.0)
            if candidate_exp >= min_exp:
                reasons.append(f"Meets experience expectation ({candidate_exp:.1f} years)")
            else:
                reasons.append(f"Below experience expectation ({candidate_exp:.1f} vs {min_exp:.1f} years)")

        if missing_required:
            reasons.append(f"Missing required skills: {', '.join(missing_required[:5])}")

        if not reasons:
            reasons.append("Profile has partial alignment with the role requirements")

        result = dict(resume)
        result["match_score"] = round(final_score, 4)
        result["match_percentage"] = round(final_score * 100, 1)
        result["fit_label"] = _fit_label(final_score)
        result["match_reasons"] = reasons
        result["matched_required_skills"] = matched_required
        result["missing_required_skills"] = missing_required
        ranked.append(result)

    ranked.sort(
        key=lambda r: (
            r.get("match_score", 0.0),
            float(r.get("total_experience_years") or 0.0),
        ),
        reverse=True,
    )

    return ranked[:top_k]
