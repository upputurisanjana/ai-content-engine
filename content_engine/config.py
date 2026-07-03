"""
config.py — Centralised API keys, model constants, and client instances.

WHY a dedicated config module:
  Centralising configuration means model names, endpoints, and API keys are
  changed in exactly one place. If we switch from DeepSeek to GPT-4o, only
  TEXT_MODEL changes here — no hunt across multiple files.

WHY python-dotenv (.env file) and not os.environ directly:
  .env files are ignored by git (see .gitignore), so secrets never appear in
  version control. dotenv.load_dotenv() also works without any shell setup,
  making the app runnable immediately after cloning with just pip install.

WHY two separate API keys (OPENROUTER_API_KEY vs IMAGE_API_KEY):
  Some teams use different OpenRouter accounts for text vs. image/video calls
  to separate billing. The code supports this pattern without requiring it —
  both keys can be the same value in .env if you only have one account.
"""

import os
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

# Load from the .env file in the same directory as this script.
# WHY Path(__file__).parent: makes the path relative to this file, not to
# wherever the user runs `streamlit run` from — avoids working-directory bugs.
load_dotenv(Path(__file__).parent / ".env")

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
IMAGE_API_KEY = os.getenv("IMAGE_API_KEY")

# ---------------------------------------------------------------------------
# Model selection
#
# WHY DeepSeek R1 for text:
#   R1 follows complex structured-output and word-count instructions reliably.
#   Cost: ~$0.00055/1K input tokens, ~$0.00219/1K output tokens on OpenRouter.
#   Trade-off: slower than GPT-4o-mini (~3s vs ~1s per call) but much cheaper.
#
# WHY FLUX.2 Klein for images:
#   Available on OpenRouter, produces campaign-quality images, ~$0.003/image.
#   Trade-off: no native inpainting or style-reference support (vs Midjourney).
#
# WHY Wan 2.6 for video:
#   Cheapest image-to-video option on OpenRouter ($0.10/s at 720p = $0.50/clip).
#   Trade-off: 60–120s generation time vs Runway's ~30s (Runway not on OpenRouter).
# ---------------------------------------------------------------------------
TEXT_MODEL  = "deepseek/deepseek-r1"
IMAGE_MODEL = "black-forest-labs/flux.2-klein-4b"
VIDEO_MODEL = "alibaba/wan-2.6"

# ---------------------------------------------------------------------------
# Client instances
#
# WHY OpenAI SDK (not httpx directly) for text generation:
#   The openai library handles retries, streaming, and response parsing.
#   OpenRouter is OpenAI-API-compatible, so the same SDK works with a
#   base_url override — no extra dependencies needed.
#
# WHY httpx directly for image/video (not OpenAI SDK):
#   The image and video endpoints use request/response shapes that differ
#   from the OpenAI images API (e.g. polling_url for video). httpx gives
#   full control over the request payload without SDK abstraction getting
#   in the way.
# ---------------------------------------------------------------------------

# Text generation client
openrouter_client = OpenAI(
    api_key=OPENROUTER_API_KEY,
    base_url="https://openrouter.ai/api/v1",
)

# Image generation client (kept separate to allow independent key rotation)
image_client = OpenAI(
    api_key=IMAGE_API_KEY,
    base_url="https://openrouter.ai/api/v1",
)
