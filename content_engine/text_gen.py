import re
import json
from config import openrouter_client, TEXT_MODEL


def _clean(text: str) -> str:
    """Strip DeepSeek <think>...</think> reasoning blocks if present."""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


# Prompt 1: Campaign Tagline (Few-shot)

TAGLINE_SYSTEM = """
You are a creative director. Generate ONE campaign tagline.
Match the brand tone exactly. Max 10 words. No hashtags.
"""

FEW_SHOT_EXAMPLES = {
    "playful": [
        {"product": "fizzy lemonade", "tagline": "Squeeze the day, one sip at a time."},
        {"product": "kids sneakers", "tagline": "Run wild. Jump higher. Repeat."},
    ],
    "premium": [
        {"product": "luxury watch", "tagline": "Time, perfected for those who demand more."},
        {"product": "silk skincare", "tagline": "Where science meets the art of beauty."},
    ],
    "eco": [
        {"product": "bamboo toothbrush", "tagline": "Small swap. Big difference for our planet."},
        {"product": "organic coffee", "tagline": "Good for you. Gentle on the earth."},
    ],
}

DEFAULT_EXAMPLES = [
    {"product": "smart speaker", "tagline": "Your home, smarter than ever before."},
    {"product": "fitness app", "tagline": "Every rep counts. Every goal matters."},
]


def generate_tagline(product: str, audience: str, tone: str) -> str:
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
            resp = openrouter_client.chat.completions.create(
                model=TEXT_MODEL,
                messages=[
                    {"role": "system", "content": TAGLINE_SYSTEM},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=200,
            )
            return _clean(resp.choices[0].message.content).strip('"')
        except Exception as e:
            if attempt == 1:
                raise RuntimeError(f"Tagline generation failed: {e}")


# Prompt 2: Blog Introduction (Role-based)

def generate_blog_intro(product: str, audience: str, tone: str, tagline: str) -> str:
    system = (
        f"You are a content strategist writing for {audience}. "
        f"Write a 200-word blog intro for {product}. "
        f'Weave in the campaign tagline: "{tagline}". '
        f"Tone: {tone}. "
        "Output exactly 200 words of prose. No headings, no lists."
    )
    for attempt in range(2):
        try:
            resp = openrouter_client.chat.completions.create(
                model=TEXT_MODEL,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": "Write the 200-word blog introduction now."},
                ],
                max_tokens=500,
            )
            return _clean(resp.choices[0].message.content)
        except Exception as e:
            if attempt == 1:
                raise RuntimeError(f"Blog intro generation failed: {e}")


# Prompt 3: Social Media Posts (Structured output / JSON)

SOCIAL_SYSTEM = """
Generate social posts for {product}.
Return ONLY JSON:
{{
  "twitter": string (max 280 chars),
  "instagram": string (max 2200 chars),
  "linkedin": string (max 700 chars)
}}
Tone: {tone}. No markdown fences. Each platform's copy must be distinct in style and length.
"""

CHAR_LIMITS = {"twitter": 280, "instagram": 2200, "linkedin": 700}


def generate_social_posts(product: str, tone: str) -> dict:
    system = SOCIAL_SYSTEM.format(product=product, tone=tone)
    for attempt in range(2):
        try:
            resp = openrouter_client.chat.completions.create(
                model=TEXT_MODEL,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": "Generate the social posts now."},
                ],
                max_tokens=800,
            )
            raw = _clean(resp.choices[0].message.content)
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
                raw = raw.strip()
            data = json.loads(raw)
            for platform, limit in CHAR_LIMITS.items():
                if platform in data:
                    data[platform] = data[platform][:limit]
            return data
        except json.JSONDecodeError as e:
            if attempt == 1:
                raise RuntimeError(f"Social post JSON parse failed: {e}")
        except Exception as e:
            if attempt == 1:
                raise RuntimeError(f"Social post generation failed: {e}")
