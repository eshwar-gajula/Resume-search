"""
LLM Provider - Groq API with Llama 3.3 70B
Uses Groq free tier – extremely fast inference.
OpenAI-compatible chat completions endpoint.
"""
import asyncio
import httpx
import json
import logging
from typing import Optional, List, Dict, Any

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class LLMProvider:
    """
    LLM adapter using Groq's OpenAI-compatible API.
    """

    def __init__(self):
        self.api_key = settings.groq_api_key
        self.model = settings.llm_model or "openai/gpt-oss-120b"
        self.base_url = "https://api.groq.com/openai/v1"

    # ------------------------------------------------------------------
    async def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        response_format: Optional[Dict] = None,
    ) -> str:
        """
        Send a chat-completion request to Groq.
        Retries automatically on 429 rate-limit errors.
        """
        if not self.api_key:
            raise RuntimeError("GROQ_API_KEY is not configured")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": 1,
        }

        if response_format:
            payload["response_format"] = response_format

        url = f"{self.base_url}/chat/completions"
        max_retries = 3

        for attempt in range(max_retries + 1):
            try:
                logger.info(
                    "Groq request attempt %d/%d  model=%s",
                    attempt + 1, max_retries + 1, self.model,
                )
                async with httpx.AsyncClient(timeout=120.0) as client:
                    resp = await client.post(url, headers=headers, json=payload)

                # Rate limited
                if resp.status_code == 429:
                    wait = 5 * (2 ** attempt)
                    logger.warning("Rate limited (429). Waiting %ds…", wait)
                    if attempt < max_retries:
                        await asyncio.sleep(wait)
                        continue
                    resp.raise_for_status()

                resp.raise_for_status()
                data = resp.json()

                content = data["choices"][0]["message"].get("content", "")
                logger.info("Groq response – %d chars in choice", len(content))
                return content

            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code
                if status == 429 and attempt < max_retries:
                    continue
                # JSON mode unsupported → retry without it
                if response_format and status in (400, 422) and attempt < max_retries:
                    logger.warning("JSON mode unsupported, retrying without response_format")
                    payload.pop("response_format", None)
                    continue
                logger.error("Groq HTTP %s: %s", status, exc.response.text[:400])
                raise

        raise RuntimeError("Groq request failed after all retries")

    # ------------------------------------------------------------------
    async def parse_resume(self, resume_text: str) -> Dict[str, Any]:
        """
        Use LLM to extract structured data from resume text.
        """
        system_prompt = """You are a resume parser. Extract structured information from the resume text.
Return a JSON object with these fields:
- skills: Array of skills
- education: Array of {degree, year, field}
- experience: Array of {title, company, duration, description}
- projects: Array of {name, description, technologies}
- certifications: Array of certifications
- summary: Brief professional summary

Ignore names, contact information, profile links, and employer prestige. Focus on relevant skills, work, projects, and education. Return valid JSON only."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Parse this resume:\n\n{resume_text}"},
        ]

        response = await self.chat(
            messages,
            temperature=0.3,
            max_tokens=8192,
            response_format={"type": "json_object"},
        )

        try:
            return json.loads(response)
        except json.JSONDecodeError:
            start = response.find("{")
            end = response.rfind("}") + 1
            if start != -1 and end > start:
                try:
                    return json.loads(response[start:end])
                except json.JSONDecodeError:
                    pass
            return {"error": "Failed to parse response", "raw": response[:500]}

    # ------------------------------------------------------------------
    async def match_candidate(
        self,
        job_description: str,
        job_skills: List[str],
        candidate_resume: Dict[str, Any],
        screening_questions: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """
        Use LLM to calculate match score between job and candidate.
        Evaluates across 6 weighted benchmarks (5 if no screening questions).
        """
        has_screening = screening_questions and len(screening_questions) > 0

        if has_screening:
            system_prompt = """You are an expert job-candidate matching system. Evaluate how well a candidate matches a job posting across 6 benchmarks.

### Scoring Benchmarks (Total: 100 points)

1. **Work Experience (20 points)**
   - Relevance of past roles to the job
   - Years of experience in similar positions
   - Industry alignment
   - Progression and responsibilities

2. **Projects (20 points)**
   - Relevant projects matching job requirements
   - Technical complexity and scale
   - Technologies used that align with job skills
   - Demonstrated problem-solving abilities

3. **Screening Questions (20 points)**
   - Quality and depth of answers
   - Technical accuracy
   - Problem-solving approach shown
   - Communication clarity
   
   **IMPORTANT: Also assess answer originality/authenticity:**
   - Does the answer seem personally written or copy-pasted?
   - Are there signs of AI-generated content (overly formal, generic, lacks personal touch)?
   - Does the answer show genuine understanding or just surface-level knowledge?
   - Are there inconsistencies with the candidate's resume experience level?

4. **Skills (15 points)**
   - Match between candidate skills and required skills
   - Proficiency level indicators
   - Related/transferable skills

5. **Educational Background (15 points)**
   - Degree relevance to the role
   - Field of study and relevant coursework or specializations
   - Academic achievements relevant to the role

6. **Certifications (10 points)**
   - Industry-relevant certifications
   - Recency and validity
   - Alignment with job requirements

### Response Format
Return a JSON object with:
{
    "match_score": <total score 0-100>,
    "benchmarks": {
        "work_experience": {"score": <0-20>, "reasoning": "<brief explanation>"},
        "projects": {"score": <0-20>, "reasoning": "<brief explanation>"},
        "screening_questions": {
            "score": <0-20>, 
            "reasoning": "<brief explanation>",
            "originality_assessment": {
                "originality_score": <0-100, where 100 is fully original>,
                "suspicion_level": "<none/low/medium/high>",
                "suspicion_flags": ["<flag1>", "<flag2>", ...],
                "assessment": "<detailed explanation of originality evaluation>"
            }
        },
        "skills": {"score": <0-15>, "reasoning": "<brief explanation>"},
        "education": {"score": <0-15>, "reasoning": "<brief explanation>"},
        "certifications": {"score": <0-10>, "reasoning": "<brief explanation>"}
    },
    "matched_skills": ["skill1", "skill2", ...],
    "missing_skills": ["skill1", "skill2", ...],
    "overall_assessment": "<2-3 sentence summary of the candidate's fit>"
}

### Suspicion Flags to Check For:
- "generic_response": Answer is too generic, could apply to any candidate
- "ai_generated": Signs of AI/ChatGPT writing style (overly structured, formal)
- "copy_paste_detected": Answer appears copied (unusual formatting, inconsistent style)
- "expertise_mismatch": Answer shows knowledge inconsistent with resume experience level
- "no_personal_examples": Lacks specific personal experiences or examples
- "templated_answer": Answer follows a common template or format

Be fair, objective, and thorough. If information is missing for a benchmark, score it conservatively but don't penalize excessively."""
        else:
            system_prompt = """You are an expert job-candidate matching system. Evaluate how well a candidate matches a job posting across 5 benchmarks.

### Scoring Benchmarks (Total: 100 points)
Note: No screening questions were provided, so points are distributed across other benchmarks.

1. **Work Experience (24 points)**
   - Relevance of past roles to the job
   - Years of experience in similar positions
   - Industry alignment
   - Progression and responsibilities

2. **Projects (24 points)**
   - Relevant projects matching job requirements
   - Technical complexity and scale
   - Technologies used that align with job skills
   - Demonstrated problem-solving abilities

3. **Skills (19 points)**
   - Match between candidate skills and required skills
   - Proficiency level indicators
   - Related/transferable skills

4. **Educational Background (19 points)**
   - Degree relevance to the role
   - Institution quality (if applicable)
   - Relevant coursework or specializations
   - Academic achievements

5. **Certifications (14 points)**
   - Industry-relevant certifications
   - Recency and validity
   - Alignment with job requirements

### Response Format
Return a JSON object with:
{
    "match_score": <total score 0-100>,
    "benchmarks": {
        "work_experience": {"score": <0-24>, "reasoning": "<brief explanation>"},
        "projects": {"score": <0-24>, "reasoning": "<brief explanation>"},
        "skills": {"score": <0-19>, "reasoning": "<brief explanation>"},
        "education": {"score": <0-19>, "reasoning": "<brief explanation>"},
        "certifications": {"score": <0-14>, "reasoning": "<brief explanation>"}
    },
    "matched_skills": ["skill1", "skill2", ...],
    "missing_skills": ["skill1", "skill2", ...],
    "overall_assessment": "<2-3 sentence summary of the candidate's fit>"
}

Be fair, objective, and thorough. If information is missing for a benchmark, score it conservatively but don't penalize excessively."""

        candidate_info = json.dumps(candidate_resume, indent=2)

        user_content = f"""
Job Description:
{job_description}

Required Skills:
{', '.join(job_skills)}

Candidate Resume Data:
{candidate_info}
"""

        if has_screening:
            questions_text = "\n\nScreening Questions and Candidate's Answers:\n"
            for i, qa in enumerate(screening_questions, 1):
                questions_text += f"\nQ{i}: {qa.get('question', 'N/A')}\n"
                questions_text += f"A{i}: {qa.get('answer', 'No answer provided')}\n"
            user_content += questions_text
            user_content += "\nEvaluate this candidate against all 6 benchmarks and calculate the total match score."
        else:
            user_content += "\nEvaluate this candidate against all 5 benchmarks and calculate the total match score."

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]

        response = await self.chat(
            messages,
            temperature=0.3,
            max_tokens=8192,
            response_format={"type": "json_object"},
        )

        try:
            result = json.loads(response)
            if "benchmarks" in result and "match_score" not in result:
                benchmarks = result["benchmarks"]
                result["match_score"] = sum(
                    b.get("score", 0)
                    for b in benchmarks.values()
                    if isinstance(b, dict)
                )
            result["has_screening_questions"] = has_screening
            return result
        except json.JSONDecodeError:
            return {
                "match_score": 0,
                "benchmarks": {},
                "matched_skills": [],
                "missing_skills": [],
                "overall_assessment": "Failed to analyze candidate",
                "has_screening_questions": has_screening,
            }


# Singleton instance
llm = LLMProvider()


async def get_llm() -> LLMProvider:
    """Dependency for getting LLM provider"""
    return llm
