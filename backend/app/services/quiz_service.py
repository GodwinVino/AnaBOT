import json
import random
import logging
from app.services.rag_service import RAGService
from app.services.aicafe_service import AICafeService

logger = logging.getLogger(__name__)

rag_service = RAGService()

DIFFICULTY_INSTRUCTIONS = {
    "Beginner": (
        "Generate SIMPLE factual questions. "
        "Questions should test basic recall of facts, definitions, and key terms directly stated in the context."
    ),
    "Novice": (
        "Generate MODERATE questions that test understanding and comprehension. "
        "Questions should require the reader to interpret information, not just recall it."
    ),
    "Expert": (
        "Generate CHALLENGING scenario-based or analytical questions. "
        "Questions should require deep understanding, inference, or application of concepts from the context."
    ),
}

QUIZ_SYSTEM_PROMPT = """You are an expert trainer and assessment designer.
Your task is to generate multiple choice questions strictly based on the provided context.
You must return ONLY a valid JSON array — no explanation, no markdown, no extra text.
"""


class QuizService:
    def __init__(self):
        self.aicafe = AICafeService()

    async def generate_quiz(self, application: str, level: str) -> list:
        if not rag_service.vectorstore_exists(application):
            raise FileNotFoundError(
                f"Knowledge base not found for '{application}'. Please load KB first."
            )

        # Retrieve broad context — use a general query to get diverse chunks
        queries = [
            "main concepts and key information",
            "important processes and procedures",
            "definitions and terminology",
        ]
        all_chunks = []
        seen = set()
        for q in queries:
            chunks = rag_service._retrieve(application, q, top_k=4)
            for c in chunks:
                key = c["text"][:60]
                if key not in seen:
                    seen.add(key)
                    all_chunks.append(c)

        if not all_chunks:
            raise ValueError("No content retrieved from knowledge base to generate quiz.")

        # Use up to 12 chunks for rich context
        context = "\n\n---\n\n".join(c["text"] for c in all_chunks[:12])
        difficulty_note = DIFFICULTY_INSTRUCTIONS.get(level, DIFFICULTY_INSTRUCTIONS["Beginner"])

        user_prompt = f"""Context:
{context}

Task: Generate exactly 5 multiple choice questions based ONLY on the context above.

Difficulty: {level}
{difficulty_note}

Rules:
- Each question must have exactly 4 options labeled A, B, C, D
- Only ONE option is correct
- Include a brief explanation for the correct answer
- Questions must be answerable from the context only
- Do NOT invent information not present in the context

Return ONLY this JSON array (no other text):
[
  {{
    "question": "Question text here?",
    "options": ["A. option one", "B. option two", "C. option three", "D. option four"],
    "answer": "A",
    "explanation": "Brief explanation why A is correct based on the context."
  }}
]"""

        logger.info(f"[QUIZ] Generating {level} quiz for '{application}' with {len(all_chunks)} chunks")

        raw = await self.aicafe.complete_raw(
            system_prompt=QUIZ_SYSTEM_PROMPT,
            user_content=user_prompt,
            temperature=0.7,
            max_tokens=2000,
        )

        questions = self._parse_questions(raw)
        questions = self._shuffle(questions)
        logger.info(f"[QUIZ] Generated {len(questions)} questions for level={level}")
        return questions

    def _parse_questions(self, raw: str) -> list:
        """Extract JSON array from LLM response, tolerating markdown fences."""
        text = raw.strip()

        # Strip markdown code fences if present
        if "```" in text:
            lines = text.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            text = "\n".join(lines).strip()

        # Find the JSON array boundaries
        start = text.find("[")
        end = text.rfind("]")
        if start == -1 or end == -1:
            logger.error(f"[QUIZ] No JSON array found in response: {text[:300]}")
            raise ValueError("AI did not return valid quiz JSON. Please try again.")

        json_str = text[start:end + 1]
        try:
            questions = json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error(f"[QUIZ] JSON parse error: {e} | raw: {json_str[:300]}")
            raise ValueError(f"Failed to parse quiz questions: {e}")

        # Validate structure
        valid = []
        for i, q in enumerate(questions):
            if not all(k in q for k in ("question", "options", "answer", "explanation")):
                logger.warning(f"[QUIZ] Question {i} missing fields, skipping")
                continue
            if len(q["options"]) != 4:
                logger.warning(f"[QUIZ] Question {i} has {len(q['options'])} options, skipping")
                continue
            valid.append(q)

        if not valid:
            raise ValueError("No valid questions were generated. Please try again.")

        return valid

    def _shuffle(self, questions: list) -> list:
        """Shuffle question order and option order within each question."""
        random.shuffle(questions)
        for q in questions:
            correct_text = next(
                (opt for opt in q["options"] if opt.startswith(q["answer"] + ".")),
                None
            )
            random.shuffle(q["options"])
            # Re-map answer label after shuffle
            for opt in q["options"]:
                if opt == correct_text:
                    q["answer"] = opt[0]  # first char is the label A/B/C/D
                    break
        return questions
