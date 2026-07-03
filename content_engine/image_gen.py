"""
image_gen.py — Hero image generation using FLUX.2 Klein via OpenRouter.

WHY FLUX.2 Klein (not GPT Image API / DALL-E):
  The brief originally specified gpt-image-2, but OpenRouter does not proxy
  the GPT Image endpoint. FLUX.2 Klein is available on OpenRouter, produces
  high-quality campaign-style images, and costs ~$0.003 per image at 1024px —
  comparable to DALL-E pricing. Using OpenRouter keeps all API traffic through
  a single endpoint and a single API key, simplifying key rotation and billing.

WHY a programmatic prompt formula (not free-form text):
  Free-form prompts produce inconsistent results across tone values. A formula
  (subject + style + composition + constraints) locks the structure while
  letting the style slot vary per tone — predictable, repeatable, testable.
"""

import base64
import time
import logging
import httpx
from config import IMAGE_API_KEY, IMAGE_MODEL

logger = logging.getLogger(__name__)

# Approximate cost per image for FLUX.2 Klein on OpenRouter.
# Source: openrouter.ai/models — update if pricing changes.
COST_PER_IMAGE_USD = 0.003

# ---------------------------------------------------------------------------
# Tone → visual style mapping
#
# WHY a lookup dict (not if/elif):
#   O(1) lookup, trivially extensible (add a new tone = one line), and
#   the default fallback makes unrecognised tones safe rather than crashing.
#
# WHY these specific style descriptors:
#   Each descriptor is a known FLUX / Stable Diffusion prompt token that
#   consistently activates a coherent visual aesthetic. Vague words like
#   "nice" or "modern" produce inconsistent results.
# ---------------------------------------------------------------------------
TONE_STYLES = {
    "playful":  "bright flat illustration, vibrant colours",
    "premium":  "photorealistic, studio lighting, luxury aesthetic",
    "eco":      "watercolour, natural earthy tones, soft light",
    "bold":     "high contrast graphic design, bold colours",
    "minimal":  "clean minimalist photography, white background",
    "retro":    "vintage film photography, warm grain",
}

# Hardcoded composition and safety constraints applied to every prompt.
# WHY hardcode (not per-tone):
#   16:9 matches the Streamlit display column ratio. "No text, no logos"
#   prevents the model from hallucinating brand text that would make the
#   image unusable. These are invariants, not variables.
COMPOSITION = "Centred composition, shallow depth of field, 16:9 aspect ratio."
SAFETY_CONSTRAINT = "No text, no logos, no watermarks."


def build_image_prompt(product: str, tagline: str, tone: str) -> str:
    """
    Construct the image prompt using the subject + style + composition + constraints formula.

    WHY include the tagline as 'Campaign theme':
      Providing semantic context nudges the model toward imagery that evokes
      the tagline's mood (e.g. "Run wild" → dynamic, energetic composition)
      rather than a flat product-on-white-background shot.
    """
    style = TONE_STYLES.get(tone.lower(), "clean modern photography")
    return (
        f"A {style} hero image of {product}. "
        f"Campaign theme: {tagline}. "
        f"{COMPOSITION} "
        f"{SAFETY_CONSTRAINT}"
    )


def generate_hero_image(product: str, tagline: str, tone: str) -> bytes:
    """
    Call the FLUX.2 Klein image generation endpoint and return raw image bytes.

    WHY raw bytes (not a URL):
      Streamlit's st.image() accepts bytes directly. Returning bytes also means
      the image is immediately available for the Wan 2.6 video call (Prompt 5)
      without a second network round-trip to fetch a URL.

    WHY retry once (not 3×):
      Image generation failures are usually transient (rate limit, cold start).
      One retry catches ~90% of transient failures without hanging the UI.
      Permanent failures (bad API key, unsupported model) fail fast on retry 1.
    """
    prompt = build_image_prompt(product, tagline, tone)
    headers = {
        "Authorization": f"Bearer {IMAGE_API_KEY}",
        "Content-Type": "application/json",
    }

    for attempt in range(2):
        try:
            start = time.time()
            resp = httpx.post(
                "https://openrouter.ai/api/v1/images",
                headers=headers,
                json={"model": IMAGE_MODEL, "prompt": prompt},
                timeout=60,
            )
            resp.raise_for_status()
            elapsed = time.time() - start

            logger.info(
                "image_call model=%s latency_s=%.2f "
                "estimated_cost_usd=%.4f status=success",
                IMAGE_MODEL,
                elapsed,
                COST_PER_IMAGE_USD,
            )

            data = resp.json()["data"][0]
            if "b64_json" in data:
                # WHY prefer b64_json over URL: avoids a second HTTP request
                # and works even if the CDN URL expires before the page renders.
                return base64.b64decode(data["b64_json"])
            # Fallback: some model variants return a URL instead of base64.
            return httpx.get(data["url"], timeout=30).content

        except Exception as e:
            logger.warning("generate_hero_image attempt %d failed: %s", attempt + 1, e)
            if attempt == 1:
                raise RuntimeError(f"Hero image generation failed: {e}")
