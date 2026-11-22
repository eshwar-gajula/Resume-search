"""Build separate AI-authorship-signal and web-similarity reports for answers."""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.services.ai_detection import AIContentDetector
from app.services.plagiarism import PlagiarismChecker

logger = logging.getLogger(__name__)

MIN_AI_CHECK_CHARACTERS = 40
MIN_WEB_CHECK_CHARACTERS = 40
MAX_AI_CHECK_CHARACTERS = 12000
MAX_WEB_CHECK_CHARACTERS = 3000


def normalize_answers(answers: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """Normalize stored application or skill-test answers without exposing secrets."""
    normalized = []
    for answer in answers:
        question = str(answer.get("question") or answer.get("question_text") or "").strip()
        text = str(answer.get("answer") or answer.get("answer_text") or "").strip()
        question_type = str(answer.get("question_type") or "text").strip().lower()
        if text:
            normalized.append({
                "question": question[:1000],
                "answer": text,
                "question_type": question_type,
            })
    return normalized


def _free_text_answers(answers: List[Dict[str, str]]) -> List[Dict[str, str]]:
    return [
        answer for answer in answers
        if answer["question_type"] not in {"multiple_choice", "multiple-choice", "mcq"}
    ]


def _joined_answer_text(answers: List[Dict[str, str]]) -> str:
    """Only score answer text; question prompts can bias authorship classification."""
    return "\n\n".join(answer["answer"] for answer in answers).strip()


async def _check_ai_authorship(
    answers: List[Dict[str, str]], detector: AIContentDetector
) -> Dict[str, Any]:
    text = _joined_answer_text(answers)
    if len(text) < MIN_AI_CHECK_CHARACTERS:
        return {
            "status": "insufficient_text",
            "verdict": "unknown",
            "summary": "There is not enough free-text content for the AI detector to analyze.",
        }

    truncated = len(text) > MAX_AI_CHECK_CHARACTERS
    try:
        result = await detector.check_text(text[:MAX_AI_CHECK_CHARACTERS])
        if not isinstance(result, dict) or result.get("status") not in {
            "checked", "not_configured", "unavailable"
        }:
            raise ValueError("AI detector returned an invalid report")
        return {**result, "truncated": truncated}
    except Exception as exc:
        logger.warning("AI-authorship review unavailable: %s", type(exc).__name__)
        return {
            "status": "unavailable",
            "verdict": "unknown",
            "summary": "The AI detector could not complete the check. No authorship conclusion was recorded.",
            "truncated": truncated,
        }


async def _check_web_similarity(
    answers: List[Dict[str, str]], checker: PlagiarismChecker
) -> Dict[str, Any]:
    text = _joined_answer_text(answers)
    base = {"score": None, "passed": None, "threshold": checker.threshold}

    if len(text) < MIN_WEB_CHECK_CHARACTERS:
        return {
            **base,
            "status": "insufficient_text",
            "summary": "There is not enough free-text content for a web-similarity check.",
        }
    if not checker.api_key:
        return {
            **base,
            "status": "not_configured",
            "summary": "Web similarity was not checked because RAPIDAPI_KEY is not configured.",
        }

    truncated = len(text) > MAX_WEB_CHECK_CHARACTERS
    try:
        result = await checker.check_text(text[:MAX_WEB_CHECK_CHARACTERS])
        if result.get("score") is None or result.get("passed") is None:
            return {
                **base,
                "status": "unavailable",
                "summary": "The web-similarity provider returned no score.",
                "truncated": truncated,
            }
        score = float(result["score"])
        passed = bool(result["passed"])
        return {
            "score": score,
            "passed": passed,
            "threshold": checker.threshold,
            "status": "checked",
            "summary": "Provider-reported web-source similarity; this is separate from AI-authorship detection.",
            "truncated": truncated,
        }
    except Exception as exc:
        logger.warning("Web-similarity review unavailable: %s", type(exc).__name__)
        return {
            **base,
            "status": "unavailable",
            "summary": "The web-similarity provider could not complete the check.",
            "truncated": truncated,
        }


def _normalize_match_originality(assessment: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Keep the match-analysis score distinct from authorship and web-similarity signals."""
    if not isinstance(assessment, dict):
        return None
    score = assessment.get("originality_score")
    try:
        score = float(score) if score is not None else None
    except (TypeError, ValueError):
        score = None
    flags = assessment.get("suspicion_flags", [])
    if not isinstance(flags, list):
        flags = []
    return {
        "score": score,
        "suspicion_level": str(assessment.get("suspicion_level") or "inconclusive")[:40],
        "signals": [str(flag)[:180] for flag in flags[:5]],
        "summary": str(assessment.get("assessment") or "")[:800],
        "method": "match-analysis originality estimate; it is not the AI detector result",
    }


def attach_match_originality(report: Dict[str, Any], assessment: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Add the separate resume-match originality estimate to an existing detector report."""
    updated = dict(report or {})
    normalized = _normalize_match_originality(assessment)
    if normalized is not None:
        updated["match_originality"] = normalized
    return updated


async def analyze_answer_integrity(
    answers: List[Dict[str, Any]],
    checker: PlagiarismChecker,
    ai_detector: AIContentDetector,
    existing_ai_assessment: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Analyze answers and keep all provider signals separate from application routing."""
    normalized = normalize_answers(answers)
    free_text = _free_text_answers(normalized)

    ai_task = _check_ai_authorship(free_text, ai_detector)
    web_task = _check_web_similarity(free_text, checker)
    ai_detection, web_similarity = await asyncio.gather(ai_task, web_task)
    match_originality = _normalize_match_originality(existing_ai_assessment)

    report = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "answer_count": len(normalized),
        "free_text_answer_count": len(free_text),
        "ai_detection": ai_detection,
        "web_similarity": web_similarity,
        "match_originality": match_originality,
        "notice": (
            "AI-detection results are estimates and cannot prove authorship. "
            "An AI or web-similarity signal, or an inconclusive or unavailable check, sends the application "
            "to recruiter manual review. A separate match-analysis originality score below 40 also routes to review. "
            "No automated result proves authorship or rejects an applicant."
        ),
    }
    report["routing"] = integrity_routing_decision(report)
    return report


def integrity_routing_decision(report: Dict[str, Any]) -> Dict[str, Any]:
    """Route uncertain or adverse checks to human review without making an authorship claim."""
    ai = report.get("ai_detection") or {}
    web = report.get("web_similarity") or {}
    reasons = []

    if ai.get("status") != "checked":
        reasons.append(f"ai_check_{ai.get('status') or 'inconclusive'}")
    elif ai.get("verdict") != "human_written":
        reasons.append("ai_authorship_inconclusive_or_flagged")

    if web.get("status") != "checked":
        reasons.append(f"web_similarity_{web.get('status') or 'inconclusive'}")
    elif web.get("passed") is not True:
        reasons.append("web_similarity_above_review_threshold")

    return {
        "decision": "manual_review" if reasons else "cleared",
        "reasons": reasons,
        "summary": (
            "Automated checks need recruiter review; they are indicators, not proof."
            if reasons else
            "Configured checks returned no review trigger; recruiter review remains the final decision."
        ),
    }


def store_integrity_result(application: Any, report: Dict[str, Any]) -> None:
    """Persist provider results without changing workflow status."""
    match_details = dict(application.match_details or {})
    match_details["skill_test_integrity"] = report
    application.match_details = match_details

    web_similarity = report.get("web_similarity", {})
    if web_similarity.get("status") == "checked":
        application.plagiarism_score = web_similarity.get("score")
        application.passed_plagiarism = web_similarity.get("passed")
    else:
        application.plagiarism_score = None
        application.passed_plagiarism = None
