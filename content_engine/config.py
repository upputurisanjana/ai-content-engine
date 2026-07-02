import os
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(Path(__file__).parent / ".env")

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
IMAGE_API_KEY = os.getenv("IMAGE_API_KEY")

TEXT_MODEL = "deepseek/deepseek-r1"
IMAGE_MODEL = "black-forest-labs/flux.2-klein-4b"
VIDEO_MODEL = "alibaba/wan-2.6"  # cheapest image-to-video on OpenRouter ($0.10/s at 720p)

# Text generation
openrouter_client = OpenAI(
    api_key=OPENROUTER_API_KEY,
    base_url="https://openrouter.ai/api/v1",
)

# Image generation
image_client = OpenAI(
    api_key=IMAGE_API_KEY,
    base_url="https://openrouter.ai/api/v1",
)
