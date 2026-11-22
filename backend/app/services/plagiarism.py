"""
Plagiarism check service backed by the Smodin RapidAPI endpoint.
"""
import logging
import math

import httpx
from typing import Dict, Any
from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

RAPIDAPI_HOST = "plagiarism-checker-and-auto-citation-generator-multi-lingual.p.rapidapi.com"
PLAGIARISM_URL = f"https://{RAPIDAPI_HOST}/plagiarism"


class PlagiarismChecker:
    """
    Simple plagiarism detection service.
    Uses Smodin's plagiarism checker through RapidAPI.
    """
    
    def __init__(self):
        self.api_key = settings.rapidapi_key
        self.threshold = settings.plagiarism_threshold  # Default: 30%
    
    async def check_text(self, text: str) -> Dict[str, Any]:
        """
        Check text for plagiarism.
        
        Returns:
            {
                "score": float (0-100),
                "passed": bool,
                "details": str
            }
        """
        if not self.api_key:
            return {
                "score": None,
                "passed": None,
                "details": "Plagiarism check skipped (no API key configured)"
            }
        
        try:
            headers = {
                "X-RapidAPI-Host": RAPIDAPI_HOST,
                "X-RapidAPI-Key": self.api_key,
                "Content-Type": "application/json"
            }
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    PLAGIARISM_URL,
                    headers=headers,
                    json={"text": text, "language": "en"}
                )

                response.raise_for_status()
                data = response.json()

            if not isinstance(data, dict) or "percentPlagiarism" not in data:
                raise ValueError("Plagiarism provider returned an invalid response")
            score = float(data["percentPlagiarism"])
            if not math.isfinite(score) or not 0 <= score <= 100:
                raise ValueError("Plagiarism provider returned an invalid score")
            
            passed = score < self.threshold
            
            return {
                "score": score,
                "passed": passed,
                "details": f"Plagiarism score: {score}%. {'Passed' if passed else 'Flagged for review'}"
            }
            
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            logger.warning("RapidAPI plagiarism check failed: %s", type(exc).__name__)
            return {
                "score": None,
                "passed": None,
                "details": "Plagiarism provider unavailable; no result was recorded"
            }
    
    def evaluate(self, score: float) -> bool:
        """
        Simple evaluation: score >= threshold means flagged.
        
        Args:
            score: Plagiarism percentage (0-100)
        
        Returns:
            True if passed (below threshold), False if flagged
        """
        return score < self.threshold


# Singleton instance
plagiarism_checker = PlagiarismChecker()


def get_plagiarism_checker() -> PlagiarismChecker:
    """Dependency for getting plagiarism checker"""
    return plagiarism_checker
