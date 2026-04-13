import os
import httpx
import logging
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

AI_CAFE_API_KEY = os.getenv("AI_CAFE_API_KEY", "")
DEPLOYMENT_NAME = os.getenv("DEPLOYMENT_NAME", "gpt-4.1")
API_VERSION = os.getenv("API_VERSION", "2024-12-01-preview")
AI_CAFE_BASE_URL = os.getenv(
    "AI_CAFE_BASE_URL",
    "https://aicafe.hcl.com/AICafeService/api/v1/subscription/openai/deployments",
)

SYSTEM_PROMPT = """You are a professional AI assistant for enterprise knowledge management.

Always format your answers using Markdown. Follow these rules strictly:

- Use ### for main section headings
- Use #### for sub-headings
- Use bullet points (-) for lists and features
- Use numbered lists (1. 2. 3.) for steps or sequences
- Use **bold** to highlight key terms, values, and important points
- Break content into clear sections — avoid long unbroken paragraphs
- Keep responses concise and structured like professional documentation
- If the answer is not found in the provided context, respond with exactly:
  **Not available in knowledge base**

Answer ONLY from the provided context. Do not use external knowledge."""

DEBUG = True


class AICafeService:
    def __init__(self):
        self.endpoint = (
            f"{AI_CAFE_BASE_URL}/{DEPLOYMENT_NAME}/chat/completions"
            f"?api-version={API_VERSION}"
        )
        self.headers = {
            "api-key": AI_CAFE_API_KEY,
            "Content-Type": "application/json",
        }

    async def complete(self, question: str, context: str) -> str:
        user_content = (
            f"Context:\n{context}\n\n"
            f"Question: {question}\n\n"
            f"Answer strictly from the context above:"
        )

        payload = {
            "model": DEPLOYMENT_NAME,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            "temperature": 0.2,
            "max_tokens": 500,
        }

        if DEBUG:
            logger.info(f"[AICAFE] Sending request to: {self.endpoint}")
            logger.info(f"[AICAFE] Deployment: {DEPLOYMENT_NAME}")
            logger.info(f"[AICAFE] Prompt length: {len(user_content)} chars")

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    self.endpoint, json=payload, headers=self.headers
                )
                response.raise_for_status()
                data = response.json()
                answer = data["choices"][0]["message"]["content"].strip()

                if DEBUG:
                    logger.info(f"[AICAFE] ✓ Response received ({len(answer)} chars)")
                    logger.info(f"[AICAFE] Answer preview: {answer[:200]!r}")

                return answer

        except httpx.HTTPStatusError as e:
            logger.error(
                f"[AICAFE] HTTP {e.response.status_code}: {e.response.text[:300]}"
            )
            raise Exception(f"AI CAFE API error {e.response.status_code}: {e.response.text[:200]}")
        except httpx.TimeoutException:
            logger.error("[AICAFE] Request timed out after 60s")
            raise Exception("AI CAFE request timed out. Please try again.")
        except Exception as e:
            logger.error(f"[AICAFE] Unexpected error: {e}", exc_info=True)
            raise Exception(f"Failed to get response from AI CAFE: {str(e)}")

    async def complete_raw(
        self,
        system_prompt: str,
        user_content: str,
        temperature: float = 0.2,
        max_tokens: int = 2000,
    ) -> str:
        """Generic completion with custom system prompt — used by quiz service."""
        payload = {
            "model": DEPLOYMENT_NAME,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_content},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if DEBUG:
            logger.info(f"[AICAFE] complete_raw | tokens={max_tokens} | temp={temperature}")

        try:
            async with httpx.AsyncClient(timeout=90.0) as client:
                response = await client.post(
                    self.endpoint, json=payload, headers=self.headers
                )
                response.raise_for_status()
                data = response.json()
                result = data["choices"][0]["message"]["content"].strip()
                if DEBUG:
                    logger.info(f"[AICAFE] complete_raw ✓ ({len(result)} chars)")
                return result
        except httpx.HTTPStatusError as e:
            logger.error(f"[AICAFE] HTTP {e.response.status_code}: {e.response.text[:300]}")
            raise Exception(f"AI CAFE API error {e.response.status_code}: {e.response.text[:200]}")
        except httpx.TimeoutException:
            raise Exception("AI CAFE request timed out. Please try again.")
        except Exception as e:
            logger.error(f"[AICAFE] Unexpected error: {e}", exc_info=True)
            raise Exception(f"Failed to get response from AI CAFE: {str(e)}")
