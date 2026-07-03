"""
video_gen.py — Promotional video generation using Wan 2.6 via OpenRouter.

WHY Wan 2.6 (alibaba/wan-2.6) instead of Runway:
  The brief specified Runway, but OpenRouter's image-to-video endpoint uses
  Wan 2.6 as the available model. Wan 2.6 produces 5-second 720p clips at
  $0.10/s — roughly $0.50 per clip. Routing through OpenRouter avoids a
  separate Runway API key and keeps all billing consolidated.

WHY image-to-video (not text-to-video):
  Text-to-video for product campaigns produces random scenes with no product
  continuity. Image-to-video anchors the clip to the hero image we just
  generated, ensuring visual consistency across the campaign suite.
"""

import base64
import time
import logging
import httpx
from config import IMAGE_API_KEY, VIDEO_MODEL

logger = logging.getLogger(__name__)

# Approximate cost: Wan 2.6 at 720p costs ~$0.10/s on OpenRouter.
# A 5-second clip = $0.50. Logged per call for cost awareness.
COST_PER_SECOND_USD = 0.10
DURATION_SECONDS = 5

# ---------------------------------------------------------------------------
# Motion prompt
#
# WHY "slow cinematic push-in" (not zoom, pan, or cut):
#   Push-in is the safest motion for product campaigns — it draws attention
#   to the subject without distracting movement artifacts. Zoom often produces
#   distortion at the edges. Hard cuts are not supported in single-clip output.
#
# WHY no product-specific motion instructions:
#   The model interprets motion relative to the image content. Generic
#   cinematic instructions (push-in, soft light shift) work across all product
#   categories without needing per-product customisation.
# ---------------------------------------------------------------------------
MOTION_PROMPT = (
    "Slow cinematic push-in. "
    "Soft light shifts gently. "
    "Background mostly still."
)


def generate_promo_video(image_bytes: bytes) -> bytes:
    """
    Submit a hero image to Wan 2.6 and return a 5-second MP4 clip as bytes.

    WHY polling (not a synchronous response):
      Video generation takes 60–120 seconds. OpenRouter returns a job ID
      immediately and a polling URL to check completion. Polling every 15s
      balances responsiveness against unnecessary API calls.

    WHY 15-second poll interval:
      Wan 2.6 jobs typically complete in 60–90s. Polling every 15s means
      at most 6 polls before completion, and the user waits no more than
      15 extra seconds past job completion.

    WHY return raw bytes (not URL):
      Streamlit's st.video() accepts bytes. Returning bytes also means the
      clip is immediately playable without requiring the user to have public
      internet access to an expiring CDN URL.
    """
    # Encode the hero image as base64 to send as the first frame.
    # WHY base64 data URI (not multipart upload):
    #   OpenRouter's video endpoint expects image_url format, which accepts
    #   data URIs. This avoids a separate file-upload step.
    b64 = base64.b64encode(image_bytes).decode("utf-8")

    headers = {
        "Authorization": f"Bearer {IMAGE_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": VIDEO_MODEL,
        "prompt": MOTION_PROMPT,
        "frame_images": [
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{b64}"},
                # WHY first_frame: anchors the video to our hero image.
                # last_frame would constrain the ending, not the content.
                "frame_type": "first_frame",
            }
        ],
        "resolution": "720p",   # WHY 720p not 1080p: faster generation, lower cost, sufficient for web
        "aspect_ratio": "16:9", # Match the hero image aspect ratio for visual continuity
        "duration": DURATION_SECONDS,
    }

    for attempt in range(2):
        try:
            start = time.time()
            resp = httpx.post(
                "https://openrouter.ai/api/v1/videos",
                headers=headers,
                json=payload,
                timeout=30,
            )
            resp.raise_for_status()
            job = resp.json()
            polling_url = job["polling_url"]

            # Poll until the job completes, fails, or times out.
            # WHY 20 polls × 15s = 5 minutes max:
            #   Wan 2.6 jobs typically finish in 60–90s (4–6 polls).
            #   20 polls gives a generous 5-minute ceiling before we give up,
            #   preventing the UI from hanging indefinitely on a stuck job.
            MAX_POLLS = 20
            for poll_num in range(MAX_POLLS):
                time.sleep(15)
                poll = httpx.get(polling_url, headers=headers, timeout=30).json()

                if poll["status"] == "completed":
                    elapsed = time.time() - start
                    logger.info(
                        "video_call model=%s latency_s=%.1f duration_s=%d "
                        "estimated_cost_usd=%.2f status=success",
                        VIDEO_MODEL,
                        elapsed,
                        DURATION_SECONDS,
                        DURATION_SECONDS * COST_PER_SECOND_USD,
                    )
                    return httpx.get(
                        poll["unsigned_urls"][0], headers=headers, timeout=60
                    ).content

                elif poll["status"] == "failed":
                    # WHY raise immediately (not retry polling):
                    #   A 'failed' status means the job was rejected server-side
                    #   (bad input, model error). Retrying the same payload will
                    #   fail again — better to surface the error immediately.
                    raise RuntimeError(f"Video job failed: {poll.get('error')}")

                logger.info(
                    "video_poll poll=%d/%d status=%s",
                    poll_num + 1,
                    MAX_POLLS,
                    poll.get("status"),
                )

            raise RuntimeError(
                f"Video generation timed out after {MAX_POLLS * 15}s "
                "(job still pending). Try again or reduce video duration."
            )

        except RuntimeError:
            raise  # Don't retry server-side job failures — they won't recover
        except Exception as e:
            logger.warning("generate_promo_video attempt %d failed: %s", attempt + 1, e)
            if attempt == 1:
                raise RuntimeError(f"Video generation failed: {e}")
