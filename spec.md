# AI Content Engine — Detailed Build Spec

**Course:** GenAI & Agentic AI Engineering · Day 3 · Afternoon Lab  
**Time budget:** 120 minutes (target completion: 3:00 PM)  
**Start point:** Provided scaffold (do not build layout/plumbing from scratch)  
**Modalities:** Text + Image + Video  
**Stack:** Streamlit · OpenRouter (all API calls) · DeepSeek R1 (text) · FLUX.2 Klein (image) · Wan 2.6 (video)

---

## 1. What You're Building

A Streamlit app that accepts **one product brief** (three fields) and produces **five campaign assets** in a single button press. No manual steps between inputs and outputs — one click, five AI calls, complete campaign suite rendered on screen.

This is not prompt practice. The hard part is **orchestrating five different API calls** while prompt-engineering each one for its specific job. The scaffold handles all layout and API plumbing. Your two hours go entirely into:

1. Writing the five prompts
2. Wiring the chaining logic (output of one call → input of next)
3. Adding retry logic for API failures

---

## 2. The Five Assets

| # | Asset | Technique | Model |
|---|---|---|---|
| 1 | Campaign tagline | Few-shot prompting | `deepseek/deepseek-r1` via OpenRouter |
| 2 | 200-word blog introduction | Role-based prompting | `deepseek/deepseek-r1` via OpenRouter |
| 3 | Social media post (3 platforms) | Structured output (JSON) | `deepseek/deepseek-r1` via OpenRouter |
| 4 | Campaign hero image | Image prompt formula | `black-forest-labs/flux.2-klein-4b` via OpenRouter |
| 5 | 5–8 second promotional video | Image-to-video + motion prompt | `alibaba/wan-2.6` via OpenRouter |

---

## 3. Project Structure

```
content_engine/
├── app.py            # Streamlit shell — PROVIDED (do not modify layout)
├── text_gen.py       # YOU BUILD: tagline, blog intro, social post prompts
├── image_gen.py      # YOU BUILD: image prompt constructor + FLUX call
├── video_gen.py      # YOU BUILD: motion prompt + Wan 2.6 call
├── config.py         # API keys + model settings — PROVIDED
├── requirements.txt  # Python dependencies
└── .env              # OPENROUTER_API_KEY=...  IMAGE_API_KEY=...
```

### What's provided in the scaffold

- Streamlit app shell (`app.py`)
- Sidebar input form with three fields and one Generate button
- Two-column main area layout (text left, visuals right)
- OpenRouter client for text generation (`openrouter_client`)
- OpenRouter client for image/video generation (`image_client`, same endpoint)
- Placeholder function signatures in `text_gen.py`, `image_gen.py`, `video_gen.py`
- Model constants: `TEXT_MODEL`, `IMAGE_MODEL`, `VIDEO_MODEL` in `config.py`

### What you build (everything behind the Generate button)

- All five prompts (system messages, user messages, few-shot examples)
- Chaining logic — passing outputs from one call into the next
- Retry logic for API failures

---

## 4. UI Specification

### Sidebar — Input Form

Three fields, one button:

| Field | Variable | Type |
|---|---|---|
| Product name | `product` | text input |
| Target audience | `audience` | text input |
| Brand tone | `tone` | text input |

One **Generate** button triggers all five calls in sequence.

### Main Area — Two-Column Output

| Left column | Right column |
|---|---|
| Tagline (text card) | Hero image |
| Blog introduction (text card) | Promotional video clip |
| Social posts — Twitter, Instagram, LinkedIn (text cards) | |

Each card must indicate **which technique powered it** (few-shot / role-based / structured output / image prompt formula / motion prompt).

---

## 5. Execution Flow

```
User fills brief (product, audience, tone)
         |
         v
[CALL 1] Tagline ──────────────────────────────────────────────┐
         |                                                       |
         v                                                       |
[CALL 2] Blog Intro  <- uses tagline as context                 |
         |                                                       v
[CALL 3] Social Post (can run after Call 1)          [CALL 4] Hero Image  (FLUX.2)
                                                                 |
                                                                 v
                                                      [CALL 5] Promo Video  (Wan 2.6)
                                                                 |
                                                                 v
                                              Render all five assets on screen
```

**Sequencing rules (explicit in the brief):**
- Call 1 (tagline) must complete before Calls 2 and 4 (both consume the tagline)
- Call 4 (image) must complete before Call 5 (video consumes the image bytes)
- Call 3 (social) depends only on `product` and `tone` — can run after Call 1 at any point

---

## 6. Prompt Specifications

### 6.1 Prompt 1 — Campaign Tagline (`text_gen.py`)

**Technique:** Few-shot prompting  
**Purpose:** Generate a single on-brand tagline that captures the product and tone  
**Model:** `deepseek/deepseek-r1` via OpenRouter  

**System message:**
```python
TAGLINE_SYSTEM = """
You are a creative director. Generate ONE campaign tagline.
Match the brand tone exactly. Max 10 words. No hashtags.
"""
```

**Few-shot examples (tone-calibrated):**
```python
FEW_SHOT_EXAMPLES = {
    "playful": [
        {"product": "fizzy lemonade", "tagline": "Squeeze the day, one sip at a time."},
        {"product": "kids sneakers",  "tagline": "Run wild. Jump higher. Repeat."},
    ],
    "premium": [
        {"product": "luxury watch",   "tagline": "Time, perfected for those who demand more."},
        {"product": "silk skincare",  "tagline": "Where science meets the art of beauty."},
    ],
    "eco": [
        {"product": "bamboo toothbrush", "tagline": "Small swap. Big difference for our planet."},
        {"product": "organic coffee",    "tagline": "Good for you. Gentle on the earth."},
    ],
}
```

**Requirements:**
- Inject 2 tone-matched few-shot examples; fall back to `DEFAULT_EXAMPLES` for unrecognised tones
- Hard constraint: max 10 words, no hashtags
- Strip DeepSeek `<think>...</think>` reasoning blocks from the response (`_clean()` helper)
- Return type: plain string (tagline only — no labels, no quotes, no preamble)
- This output is consumed by Prompts 2 and 4; it must be clean and strippable

---

### 6.2 Prompt 2 — Blog Introduction (`text_gen.py`)

**Technique:** Role-based prompting (persona injection)  
**Purpose:** 200-word blog intro that echoes the tagline and speaks to the audience  
**Model:** `deepseek/deepseek-r1` via OpenRouter  
**Input dependency:** `{tagline}` from Prompt 1 — must be passed in as context  

**System message (constructed at call time):**
```python
system = (
    f"You are a content strategist writing for {audience}. "
    f"Write a 200-word blog intro for {product}. "
    f'Weave in the campaign tagline: "{tagline}". '
    f"Tone: {tone}. "
    "Output exactly 200 words of prose. No headings, no lists."
)
```

**Requirements:**
- Substitute `audience`, `product`, `tagline`, `tone` at call time
- Exactly 200 words — enforce in the prompt
- The tagline must appear woven into the copy, not bolted on
- Role is **content strategist** (not creative director, not copywriter)
- Strip `<think>` blocks before returning
- Return type: plain string (prose only)

---

### 6.3 Prompt 3 — Social Media Post (`text_gen.py`)

**Technique:** Structured output (JSON)  
**Purpose:** Platform-specific social copy respecting each platform's character limit  
**Model:** `deepseek/deepseek-r1` via OpenRouter  

**System message:**
```python
SOCIAL_SYSTEM = """
Generate social posts for {product}.
Return ONLY JSON:
{
  "twitter": string (max 280 chars),
  "instagram": string (max 2200 chars),
  "linkedin": string (max 700 chars)
}
Tone: {tone}. No markdown fences. Each platform's copy must be distinct in style and length.
"""
```

**Character limits (hard, from the brief):**

| Platform | Max characters |
|---|---|
| Twitter | 280 |
| Instagram | 2200 |
| LinkedIn | 700 |

**Requirements:**
- Return ONLY valid JSON — no markdown fences, no preamble, no trailing text
- Strip markdown fences if the model adds them before `json.loads()`
- Hard-truncate each platform's copy to its character limit after parsing
- Substitute `{product}` and `{tone}` at call time
- Each platform's copy should be distinct in length and style, not just truncated versions of each other
- Validate character limits in code after parsing (`CHAR_LIMITS` dict + slicing)

---

### 6.4 Prompt 4 — Hero Image (`image_gen.py`)

**Technique:** Programmatic image prompt formula (subject + style + composition + constraints)  
**Purpose:** A campaign-grade hero image matched to product, tagline, and tone  
**Model:** `black-forest-labs/flux.2-klein-4b` via OpenRouter (`https://openrouter.ai/api/v1/images`)  
**Input dependencies:** `{product}` + `{tagline}` from Prompt 1  

**Tone → style lookup:**
```python
TONE_STYLES = {
    "playful":  "bright flat illustration, vibrant colours",
    "premium":  "photorealistic, studio lighting, luxury aesthetic",
    "eco":      "watercolour, natural earthy tones, soft light",
    "bold":     "high contrast graphic design, bold colours",
    "minimal":  "clean minimalist photography, white background",
    "retro":    "vintage film photography, warm grain",
}
# Default for unrecognised tones: "clean modern photography"
```

**Prompt builder:**
```python
def build_image_prompt(product: str, tagline: str, tone: str) -> str:
    style = TONE_STYLES.get(tone.lower(), "clean modern photography")
    return (
        f"A {style} hero image of {product}. "
        f"Campaign theme: {tagline}. "
        "Centred composition, shallow depth of field, 16:9 aspect ratio. "
        "No text, no logos, no watermarks."
    )
```

**Formula breakdown:**

| Element | Example value | Source |
|---|---|---|
| Subject | `{product}` | form input |
| Style | `"photorealistic, studio lighting, luxury aesthetic"` | derived from `{tone}` via lookup |
| Composition | `"Centred composition, shallow depth of field, 16:9 aspect ratio"` | hardcoded |
| Constraints | `"No text, no logos, no watermarks"` | hardcoded |
| Semantic context | `Campaign theme: {tagline}` | tagline from Prompt 1 |

**Requirements:**
- The tone→style lookup covers 6 tones; default `"clean modern photography"` for anything else
- Aspect ratio: 16:9 (hardcoded)
- No text, no logos, no watermarks (hardcoded constraint — appears in every prompt)
- Response may be `b64_json` or URL — handle both
- Output: raw image bytes → passed directly into Prompt 5

---

### 6.5 Prompt 5 — Promotional Video (`video_gen.py`)

**Technique:** Image-to-video with motion prompt  
**Purpose:** A 5-second cinematic clip derived from the hero image  
**Model:** `alibaba/wan-2.6` via OpenRouter (`https://openrouter.ai/api/v1/videos`)  
**Input dependency:** Hero image bytes from Prompt 4  

**Motion prompt:**
```python
MOTION_PROMPT = (
    "Slow cinematic push-in. "
    "Soft light shifts gently. "
    "Background mostly still."
)
```

**API payload:**
```python
{
    "model": VIDEO_MODEL,           # "alibaba/wan-2.6"
    "prompt": MOTION_PROMPT,
    "frame_images": [{
        "type": "image_url",
        "image_url": {"url": f"data:image/png;base64,{b64}"},
        "frame_type": "first_frame"
    }],
    "resolution": "720p",
    "aspect_ratio": "16:9",
    "duration": 5
}
```

**Polling pattern:**
- Submit job → receive `polling_url`
- Poll every 15 seconds until `status == "completed"`
- On `completed`: fetch `unsigned_urls[0]` and return as raw bytes
- On `failed`: raise `RuntimeError` immediately

**Requirements:**
- Encode hero image as base64 and send as `first_frame`
- Duration: 5 seconds (`duration: 5`)
- Keep motion subtle: slow push-in, gentle light shift, mostly still background
- Do not add text overlays or hard cuts
- Output: video bytes → rendered in the right column of the UI

---

## 7. Chaining Logic — Data Flow Table

| Output of | Variable name | Consumed by |
|---|---|---|
| Prompt 1 (tagline) | `tagline` | Prompt 2 system message, Prompt 4 `build_image_prompt()` |
| Prompt 2 (blog) | `blog_text` | Display only |
| Prompt 3 (social) | `social_json` (parsed dict) | Display only (3 platform cards) |
| Prompt 4 (image) | `hero_image_bytes` | Prompt 5 as base64-encoded first frame |
| Prompt 5 (video) | `video_bytes` | Display only |

**Critical:** Each handoff must pass the actual output, not a reference. The tagline string goes directly into the f-string substitution for `generate_blog_intro()` and into `build_image_prompt()`. The image bytes go directly into the Wan 2.6 API call as a base64 data URI.

---

## 8. Error Handling & Retry Logic

The brief explicitly calls out retry logic as **your responsibility** (not provided in scaffold).

Minimum requirements:
- Wrap each of the five API calls in `try/except` with `for attempt in range(2)` retry loop
- On failure of attempt 0, retry once; on failure of attempt 1, `raise RuntimeError`
- If a call in the chain fails (e.g. Prompt 4), do not attempt downstream calls that depend on it (e.g. Prompt 5) — `app.py` guards this with `if hero_image_bytes:`
- Display a clear error message in the relevant output card (`st.error()`) rather than crashing the app
- Social post JSON parsing: strip markdown fences before `json.loads()`; catch `json.JSONDecodeError` separately from general `Exception`
- DeepSeek R1 emits `<think>...</think>` reasoning blocks — strip these with the `_clean()` helper before processing any text response

---

## 9. Design Principles (from the brief)

> "A single mega-prompt would try to do everything and do nothing well. Each call is tuned for one job with one technique."

Each prompt must be:
- **Single-responsibility** — one asset, one technique, one job
- **Technique-appropriate** — don't use structured output where few-shot is specified, and vice versa
- **Explicitly constrained** — word counts, character limits, format rules must appear inside the prompt, not just in the code

The chain architecture mirrors the homework prompt pipeline from Day 2 (meeting notes → action items), now extended across modalities (text → image → video).

---

## 10. Done Criteria (from the brief)

All of the following must be true by 3:00 PM:

- [ ] App generates all five assets in one run from a single product brief
- [ ] Tagline brand voice matches the `tone` input
- [ ] Blog intro is ~200 words and visibly echoes the tagline
- [ ] Social posts respect Twitter 280 / Instagram 2200 / LinkedIn 700 character limits
- [ ] Hero image matches the product and tone; contains no text or logos
- [ ] Video is a clean 5-second clip derived from the hero image
- [ ] Peer review passes: a partner runs a **different product** through your engine and all five assets generate correctly

---

## 11. Stretch Goals (time permitting)

| Goal | Description |
|---|---|
| Voiceover | Use ElevenLabs or OpenAI TTS to generate audio from the blog intro |
| A/B taglines | Generate two tagline variants; let the user pick one before generating the rest |
| Tone switcher | Change the tone field and regenerate the full cascade; observe how all assets shift |
| Export suite | Package all five assets (text as `.txt`/`.md`, image, video) into a downloadable ZIP |

---

## 12. Context — How This Fits the Course

| | Day 2 — Prompt Doctor | Day 3 — AI Content Engine |
|---|---|---|
| What you build | One prompt, graded by AI examiner | Multi-modal Streamlit app, five assets |
| The hard part | The prompt — nothing else | Orchestrating five API calls + prompt engineering for each |
| Modalities | Text only | Text + Image + Video |
| Output | One polished prompt per level | A working app that produces a campaign suite |

The Day 2 homework (prompt pipeline: meeting notes → action items, JSON handoffs between stages) is the direct conceptual predecessor. Today extends the same handoff pattern across modalities instead of just between text stages.
