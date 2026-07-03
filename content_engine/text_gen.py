"""
text_gen.py — All three text-generation prompts for the AI Content Engine.

WHY this module exists as a separate file:
  Single-responsibility principle: text generation is isolated from UI (app.py)
  and visual generation (image_gen.py, video_gen.py). This makes prompts easy
  to tune, test, and swap without touching layout or API plumbing.

WHY DeepSeek R1 via OpenRouter:
  R1 is a reasoning model that follows complex instructions reliably (JSON output,
  word counts, tone calibration). OpenRouter gives a single billing endpoint for
  all LLM calls, avoiding multiple vendor accounts. Cost: ~$0.0005 per tagline,
  ~$0.002 per blog intro — negligible for a lab.
"""

import re
import json
import time
import logging
from config import openrouter_client, TEXT_MODEL

# ---------------------------------------------------------------------------
# Structured logger — every API call emits a JSON-compatible log record so
# production monitoring tools (Datadog, CloudWatch) can ingest them directly.
# WHY structured vs print(): grep-able, filterable, machine-readable.
# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(name)s  %(message)s",
)

# ---------------------------------------------------------------------------
# Input validation constants
# WHY these limits: prevent prompt injection via huge inputs, keep API costs
# bounded, and mirror real CMS field limits (product names ≤ 100 chars, etc.)
# ---------------------------------------------------------------------------
MAX_PRODUCT_LEN = 100
MAX_AUDIENCE_LEN = 150
MAX_TONE_LEN = 50

# Approximate cost per 1K tokens for DeepSeek R1 on OpenRouter (USD).
# Used for per-call cost estimation in log records.
# Source: openrouter.ai/models — update if pricing changes.
COST_PER_1K_INPUT_TOKENS = 0.00055
COST_PER_1K_OUTPUT_TOKENS = 0.00219


def _validate_inputs(**kwargs) -> None:
    """
    Reject inputs that are empty, whitespace-only, or exceed safe character limits.

    WHY validate here (not just in app.py):
      Defense-in-depth. The UI validates for UX, but module-level validation
      ensures correctness even if this library is called programmatically or
      from a test harness.
    """
    limits = {
        "product": MAX_PRODUCT_LEN,
        "audience": MAX_AUDIENCE_LEN,
        "tone": MAX_TONE_LEN,
    }
    for field, value in kwargs.items():
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"'{field}' must be a non-empty string.")
        limit = limits.get(field, 500)
        if len(value) > limit:
            raise ValueError(
                f"'{field}' exceeds {limit} characters (got {len(value)}). "
                "Shorten the input to prevent runaway API costs."
            )


def _log_call(func_name: str, model: str, start: float, response) -> None:
    """
    Emit a structured log record for every LLM API call.

    Fields logged:
      - model: which LLM was used (important when A/B testing models)
      - latency_s: wall-clock time for the call (SLA monitoring)
      - prompt_tokens / completion_tokens: for cost attribution
      - estimated_cost_usd: helps students understand per-query spend
      - status: success / error for alerting dashboards

    WHY log tokens and cost:
      Logging per-call cost lets the team calculate monthly spend:
      cost_per_call × daily_queries × 30. At ~$0.003 per full run,
      1000 runs/month ≈ $3.
    """
    elapsed = time.time() - start
    usage = getattr(response, "usage", None)
    prompt_tokens = getattr(usage, "prompt_tokens", 0) if usage else 0
    completion_tokens = getattr(usage, "completion_tokens", 0) if usage else 0
    cost = (
        prompt_tokens / 1000 * COST_PER_1K_INPUT_TOKENS
        + completion_tokens / 1000 * COST_PER_1K_OUTPUT_TOKENS
    )
    logger.info(
        "llm_call function=%s model=%s latency_s=%.2f "
        "prompt_tokens=%d completion_tokens=%d "
        "estimated_cost_usd=%.6f status=success",
        func_name,
        model,
        elapsed,
        prompt_tokens,
        completion_tokens,
        cost,
    )


def _clean(text: str) -> str:
    """
    Strip DeepSeek R1 <think>...</think> reasoning blocks from the response.

    WHY: R1 emits chain-of-thought reasoning wrapped in <think> tags before
    the actual answer. Leaving these in would pollute the tagline, blog text,
    and JSON output. This is a model-specific quirk, not a general LLM issue —
    isolating it here means we only change one line if we switch models.
    """
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


# ---------------------------------------------------------------------------
# PROMPT 1 — Campaign Tagline   (Few-shot prompting)
# ---------------------------------------------------------------------------

TAGLINE_SYSTEM = """
You are a creative director. Generate ONE campaign tagline.
Match the brand tone exactly. Max 10 words. No hashtags.
This tool is for marketing content only. If the product or request involves
medical advice, legal counsel, financial guidance, or political messaging,
respond with exactly: REFUSED: outside scope.
"""

# WHY few-shot examples keyed by tone:
#   Zero-shot taglines drift toward generic copy ("Experience the difference").
#   Injecting 2 tone-matched examples calibrates the model's style register
#   without fine-tuning. Three tones cover the most common brand voices;
#   DEFAULT_EXAMPLES handle anything else gracefully.
FEW_SHOT_EXAMPLES = {
    "playful": [
        {"product": "fizzy lemonade", "tagline": "Squeeze the day, one sip at a time."},
        {"product": "kids sneakers",  "tagline": "Run wild. Jump higher. Repeat."},
    ],
    "premium": [
        {"product": "luxury watch",  "tagline": "Time, perfected for those who demand more."},
        {"product": "silk skincare", "tagline": "Where science meets the art of beauty."},
    ],
    "eco": [
        {"product": "bamboo toothbrush", "tagline": "Small swap. Big difference for our planet."},
        {"product": "organic coffee",    "tagline": "Good for you. Gentle on the earth."},
    ],
}

DEFAULT_EXAMPLES = [
    {"product": "smart speaker", "tagline": "Your home, smarter than ever before."},
    {"product": "fitness app",   "tagline": "Every rep counts. Every goal matters."},
]


def generate_tagline(product: str, audience: str, tone: str) -> str:
    """
    Prompt 1: Few-shot tagline generation.

    WHY few-shot here (not role-based or structured output):
      Tagline quality is about stylistic calibration. Few-shot examples
      show the model the exact register we want — short, punchy, on-brand —
      better than any system-prompt instruction alone.

    The output feeds into Prompt 2 (blog intro context) and Prompt 4
    (image semantic grounding), so it must be a clean plain string.
    """
    _validate_inputs(product=product, audience=audience, tone=tone)

    examples = FEW_SHOT_EXAMPLES.get(tone.lower(), DEFAULT_EXAMPLES)
    shots = "\n".join(
        f'Product: {e["product"]}\nTagline: {e["tagline"]}' for e in examples
    )
    user_prompt = (
        f"{shots}\n\n"
        f"Product: {product}\n"
        f"Audience: {audience}\n"
        f"Tone: {tone}\n"
        f"Tagline:"
    )

    for attempt in range(2):
        try:
            start = time.time()
            resp = openrouter_client.chat.completions.create(
                model=TEXT_MODEL,
                messages=[
                    {"role": "system", "content": TAGLINE_SYSTEM},
                    {"role": "user",   "content": user_prompt},
                ],
                max_tokens=200,
            )
            _log_call("generate_tagline", TEXT_MODEL, start, resp)
            result = _clean(resp.choices[0].message.content).strip('"')
            # Surface content safety refusals as a clear error rather than
            # silently returning "REFUSED: outside scope" as a tagline.
            if result.startswith("REFUSED:"):
                raise ValueError(f"Content safety refusal: {result}")
            return result
        except Exception as e:
            logger.warning("generate_tagline attempt %d failed: %s", attempt + 1, e)
            if attempt == 1:
                raise RuntimeError(f"Tagline generation failed: {e}")


# ---------------------------------------------------------------------------
# PROMPT 2 — Blog Introduction   (Role-based prompting)
# ---------------------------------------------------------------------------

def generate_blog_intro(product: str, audience: str, tone: str, tagline: str) -> str:
    """
    Prompt 2: Role-based blog intro using a content strategist persona.

    WHY role-based here:
      A "content strategist" persona produces audience-aware, structured prose
      with natural brand voice. Without the role, the model writes generic
      copy. The persona also enforces the 200-word discipline more reliably
      than a bare instruction.

    WHY tagline is passed as context:
      The blog intro must echo the campaign tagline to create copy coherence
      across assets. Injecting it into the system message rather than the user
      message gives it higher instruction priority.
    """
    _validate_inputs(product=product, audience=audience, tone=tone)
    if not tagline or not tagline.strip():
        raise ValueError("'tagline' must be non-empty — it comes from Prompt 1.")

    # WHY build system dynamically (not a module-level constant):
    #   All four variables need to be injected at call time. An f-string here
    #   is cleaner and less error-prone than a .format() on a multi-line string.
    system = (
        f"You are a content strategist writing for {audience}. "
        f"Write a 200-word blog intro for {product}. "
        f'Weave in the campaign tagline: "{tagline}". '
        f"Tone: {tone}. "
        "Output exactly 200 words of prose. No headings, no lists."
    )

    for attempt in range(2):
        try:
            start = time.time()
            resp = openrouter_client.chat.completions.create(
                model=TEXT_MODEL,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user",   "content": "Write the 200-word blog introduction now."},
                ],
                max_tokens=500,
            )
            _log_call("generate_blog_intro", TEXT_MODEL, start, resp)
            result = _clean(resp.choices[0].message.content)
            if result.startswith("REFUSED:"):
                raise ValueError(f"Content safety refusal: {result}")
            return result
        except Exception as e:
            logger.warning("generate_blog_intro attempt %d failed: %s", attempt + 1, e)
            if attempt == 1:
                raise RuntimeError(f"Blog intro generation failed: {e}")


# ---------------------------------------------------------------------------
# PROMPT 3 — Social Media Posts   (Structured output / JSON)
# ---------------------------------------------------------------------------

# WHY structured output (JSON) here instead of prose:
#   Three platforms need distinct copy with hard character limits that must be
#   machine-verified. JSON forces the model to produce parseable, addressable
#   output. We then validate limits in Python — never trust the model alone.
SOCIAL_SYSTEM = """
Generate social posts for {product}.
Return ONLY valid JSON (no markdown fences, no preamble):
{{
  "twitter":   "<string, max 280 chars>",
  "instagram": "<string, max 2200 chars>",
  "linkedin":  "<string, max 700 chars>"
}}
Tone: {tone}.
Each platform's copy must differ in length, style, and call-to-action -- not just truncated versions of each other.
This tool is for marketing content only. If the product involves medical advice,
legal counsel, financial guidance, or political messaging, respond with exactly:
REFUSED: outside scope.
"""

# WHY hard character limits enforced in code (not only in the prompt):
#   LLMs occasionally exceed stated limits by a few characters. Truncating in
#   code is the safety net that makes character-limit compliance a guarantee,
#   not a best-effort.
CHAR_LIMITS = {"twitter": 280, "instagram": 2200, "linkedin": 700}


def generate_social_posts(product: str, tone: str) -> dict:
    """
    Prompt 3: Structured JSON social media posts.

    WHY only product + tone (no audience):
      Social posts are platform-addressed by definition. Audience segmentation
      comes from the platform itself (targeting settings), not from copy length.
      Keeping the prompt focused produces tighter, platform-idiomatic copy.

    Returns a dict with keys: twitter, instagram, linkedin.
    Each value is already truncated to its platform character limit.
    """
    _validate_inputs(product=product, tone=tone)

    system = SOCIAL_SYSTEM.format(product=product, tone=tone)

    for attempt in range(2):
        try:
            start = time.time()
            resp = openrouter_client.chat.completions.create(
                model=TEXT_MODEL,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user",   "content": "Generate the social posts now."},
                ],
                max_tokens=800,
            )
            _log_call("generate_social_posts", TEXT_MODEL, start, resp)

            raw = _clean(resp.choices[0].message.content)

            # Check for content safety refusal before attempting JSON parse.
            if raw.strip().startswith("REFUSED:"):
                raise ValueError(f"Content safety refusal: {raw.strip()}")

            # Strip markdown fences — some models add ```json ... ``` despite instructions.
            # WHY strip here rather than failing: recoverable formatting error; the
            # JSON content is still valid.
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
                raw = raw.strip()

            data = json.loads(raw)

            # Hard-enforce character limits as a safety net after parsing.
            for platform, limit in CHAR_LIMITS.items():
                if platform in data:
                    data[platform] = data[platform][:limit]

            return data

        except json.JSONDecodeError as e:
            logger.warning(
                "generate_social_posts attempt %d JSON parse failed: %s", attempt + 1, e
            )
            if attempt == 1:
                raise RuntimeError(f"Social post JSON parse failed: {e}")
        except Exception as e:
            logger.warning("generate_social_posts attempt %d failed: %s", attempt + 1, e)
            if attempt == 1:
                raise RuntimeError(f"Social post generation failed: {e}")
