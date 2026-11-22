"""AI-generated text signal provider backed by RapidAPI."""
import logging
from typing import Any, Dict

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class AIContentDetector:
    """Call a RapidAPI AI text detector and normalize its three possible verdicts."""

    def __init__(self):
        self.api_key = settings.rapidapi_ai_detector_key or settings.rapidapi_key
        self.host = settings.rapidapi_ai_detector_host
        self.url = settings.rapidapi_ai_detector_url

    async def check_text(self, text: str) -> Dict[str, Any]:
        if not self.api_key:
            return {
                "status": "not_configured",
                "verdict": "unknown",
                "summary": "AI detection was not run because RAPIDAPI_KEY is not configured.",
            }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.url,
                    headers={
                        "X-RapidAPI-Host": self.host,
                        "X-RapidAPI-Key": self.api_key,
                        "Content-Type": "application/json",
                    },
                    json={"text": text},
                )
                response.raise_for_status()
                data = response.json()

            if not isinstance(data, dict) or data.get("success") is False:
                raise ValueError("AI detector returned an invalid response")

            raw_verdict = str(data.get("result") or "").strip().casefold()
            verdicts = {
                "ai-generated": "ai_generated",
                "ai generated": "ai_generated",
                "human-written": "human_written",
                "human written": "human_written",
                "undetectable": "undetectable",
            }
            verdict = verdicts.get(raw_verdict)
            if verdict is None:
                raise ValueError("AI detector returned an unsupported verdict")

            summaries = {
                "ai_generated": "The provider classified this text as likely AI-generated. This is an estimate, not proof of authorship.",
                "human_written": "The provider classified this text as likely human-written. This is an estimate, not proof of authorship.",
                "undetectable": "The provider could not confidently classify this text as AI-generated or human-written.",
            }
            return {
                "status": "checked",
                "verdict": verdict,
                "provider_result": str(data.get("result"))[:80],
                "summary": summaries[verdict],
            }
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            logger.warning("RapidAPI AI detection rejected the request with HTTP %s", status_code)
            if status_code in {401, 403}:
                summary = (
                    "RapidAPI denied access to the AI detector. Check the RapidAPI app key and "
                    "subscribe that app to the AI Generated Content Detector plan."
                )
            elif status_code == 429:
                summary = "The AI detector reached its RapidAPI request limit. No authorship conclusion was recorded."
            else:
                summary = "The AI detector provider could not complete the request. No authorship conclusion was recorded."
            return {
                "status": "unavailable",
                "verdict": "unknown",
                "summary": summary,
            }
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            logger.warning("RapidAPI AI detection failed: %s", type(exc).__name__)
            return {
                "status": "unavailable",
                "verdict": "unknown",
                "summary": "The AI detector could not return a usable result. No authorship conclusion was recorded.",
            }


ai_content_detector = AIContentDetector()


def get_ai_content_detector() -> AIContentDetector:
    """FastAPI dependency for the AI-authorship signal provider."""
    return ai_content_detector
