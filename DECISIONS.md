# Architectural Decisions — AI Content Engine

This document records every significant technical decision made during the build, the alternatives considered, and the trade-off that determined the choice.

---

## D1 — All API calls routed through OpenRouter

**Decision:** Use OpenRouter as the single gateway for text, image, and video generation.

**Alternatives considered:**
- Direct OpenAI API for text + GPT Image API for images + Runway for video (three separate accounts and keys)
- Hugging Face Inference API for open-source models

**Why OpenRouter:**
One API key, one billing dashboard, one base URL. The OpenAI SDK works with OpenRouter via `base_url` override, so no extra dependencies. Model swaps are a one-line change in `config.py`.

**Trade-off:**
OpenRouter adds a routing layer (~50ms latency overhead per call). Some models available directly on their native API are not yet available on OpenRouter (e.g. GPT Image API, Runway). We accepted this: the latency is imperceptible in a campaign generation context, and the operational simplicity outweighs the model selection limitation.

---

## D2 — DeepSeek R1 for text generation

**Decision:** Use `deepseek/deepseek-r1` for tagline, blog, and social post generation.

**Alternatives considered:**
- `openai/gpt-4o-mini` — faster (~1s vs ~3s), slightly less instruction-following on structured output
- `anthropic/claude-3-haiku` — good instruction following, higher cost
- `meta-llama/llama-3.1-70b-instruct` — open weights, less reliable on JSON output

**Why R1:**
R1 follows complex, multi-constraint instructions reliably — word count limits, JSON-only output, no hashtags. Cost is ~$0.00055/1K input tokens, making a full text run cost under $0.003.

**Trade-off:**
R1 emits `<think>...</think>` reasoning blocks before answers. These must be stripped with `_clean()`. This is a known quirk handled in one function — acceptable maintenance cost for the quality gain.

---

## D3 — FLUX.2 Klein for image generation

**Decision:** Use `black-forest-labs/flux.2-klein-4b` for hero image generation.

**Alternatives considered:**
- `openai/dall-e-3` — not available on OpenRouter
- `stability/stable-diffusion-xl` — available on OpenRouter, lower quality on photorealistic product shots
- `ideogram/ideogram-v2` — good text rendering, not needed here (we explicitly exclude text from images)

**Why FLUX.2 Klein:**
Best available quality-to-cost ratio on OpenRouter for product photography prompts. Handles the tone→style formula reliably. Cost: ~$0.003/image.

**Trade-off:**
No native inpainting or style-reference input (vs Midjourney or DALL-E 3). For campaign hero images generated from a text prompt, neither capability is needed.

---

## D4 — Wan 2.6 for video generation

**Decision:** Use `alibaba/wan-2.6` via OpenRouter's `/v1/videos` endpoint.

**Alternatives considered:**
- Runway Gen-3 — best quality, not available on OpenRouter, separate API key required
- Stable Video Diffusion — lower quality motion coherence

**Why Wan 2.6:**
Only image-to-video model currently available through OpenRouter. Cost: $0.10/s at 720p ($0.50 for a 5-second clip). The polling-based job model (submit → poll every 15s → retrieve) is straightforward to implement.

**Trade-off:**
Generation takes 60–120 seconds. The UI shows a spinner with an honest time estimate ("~90 seconds"). Runway would be ~30s but requires a separate account. For a lab context, the wait is acceptable.

---

## D5 — Sequential execution (not parallel)

**Decision:** Run all five API calls sequentially, one at a time.

**Alternatives considered:**
- Run calls 2, 3, and 4 in parallel after call 1 completes (using `concurrent.futures` or `asyncio`)
- Run calls 2 and 3 in parallel (they're independent after call 1), then call 4, then call 5

**Why sequential:**
Streamlit's execution model is single-threaded per session. Parallelising calls requires `asyncio` or thread pools, both of which add complexity. The total wait time is dominated by the video call (~90s) regardless of whether text calls run in parallel (~3s each). Parallelising would save at most ~6 seconds out of ~100.

**Trade-off:**
Slightly longer total time in edge cases where the video is fast. The code is significantly simpler — a straight linear chain that's easy to follow and debug.

---

## D6 — Few-shot prompting for tagline (not zero-shot or fine-tuning)

**Decision:** Inject 2 tone-calibrated few-shot examples into the tagline prompt.

**Alternatives considered:**
- Zero-shot with detailed style instructions
- Fine-tuned model on brand tagline datasets

**Why few-shot:**
Zero-shot taglines drift toward generic copy ("Experience the difference") regardless of tone instructions. Two well-chosen examples reliably shift the model's style register without fine-tuning. Fine-tuning requires a dataset and is impractical for a one-day lab.

**Trade-off:**
The example bank only covers three tones explicitly (playful, premium, eco). Unknown tones fall back to `DEFAULT_EXAMPLES`, which are tone-neutral. A more complete example bank would cover more tones but would require curation.

---

## D7 — Structured JSON output for social posts (not prose + post-processing)

**Decision:** Instruct the model to return raw JSON for social posts and parse with `json.loads()`.

**Alternatives considered:**
- Generate three separate API calls (one per platform)
- Generate prose and split by platform headers in post-processing

**Why JSON:**
One call for all three platforms. Platform-specific constraints (character limits) are enforced in code after parsing — reliable and testable. Three separate calls would triple cost and latency for this step.

**Trade-off:**
JSON can fail to parse if the model adds markdown fences or trailing comments. Mitigated by stripping fences before `json.loads()` and retrying once on `JSONDecodeError`. A more robust approach would use a lenient JSON parser (json5) — identified as a known weakness.

---

## D8 — Input validation at module level (not only in the UI)

**Decision:** `text_gen.py` validates all inputs via `_validate_inputs()` before making any API call.

**Alternatives considered:**
- Validate only in `app.py` (UI layer)
- No validation beyond Streamlit's `max_chars` widget constraint

**Why module-level validation:**
The UI can be bypassed — `text_gen.py` can be imported and called from scripts, tests, or other UIs. Module-level validation ensures correctness regardless of how the library is invoked. `max_chars` in Streamlit silently truncates rather than raising an error, which could produce confusing outputs.

**Trade-off:**
Validation logic lives in two places (UI for UX feedback, module for correctness). They must stay in sync when limits change. Mitigated by importing the constants (`MAX_PRODUCT_LEN` etc.) from `text_gen.py` into `app.py` so there is a single source of truth.

---

## D9 — Base64 data URI for video first frame (not file upload)

**Decision:** Encode the hero image as a base64 data URI and pass it in the JSON payload.

**Alternatives considered:**
- Upload the image to a temporary URL (S3 or similar) and pass the URL
- Use a multipart form upload

**Why base64:**
OpenRouter's video endpoint accepts `image_url` format, which supports data URIs. No separate upload step, no S3 bucket, no URL expiry to manage. Self-contained in a single API call.

**Trade-off:**
Large images (>1MB) produce very large JSON payloads. At FLUX.2's default output size this is not a problem, but would be a concern with higher-resolution images.
