# AI Content Engine — Detailed Build Spec

**Course:** GenAI & Agentic AI Engineering · Day 3 · Afternoon Lab  
**Time budget:** 120 minutes (target completion: 3:00 PM)  
**Start point:** Provided scaffold (do not build layout/plumbing from scratch)  
**Modalities:** Text + Image + Video  
**Stack:** Streamlit · OpenRouter · GPT Image API (`gpt-image-1`) · Runway  

---

## 1. What You're Building

A Streamlit app that accepts **one product brief** (three fields) and produces **five campaign assets** in a single button press. No manual steps between inputs and outputs — one click, five AI calls, complete campaign suite rendered on screen.

This is not prompt practice. The hard part is **orchestrating five different API calls** while prompt-engineering each one for its specific job. The scaffold handles all layout and API plumbing. Your two hours go entirely into:

1. Writing the five prompts
2. Wiring the chaining logic (output of one call → input of next)
3. Adding retry logic for API failures

---

## 2. The Five Assets

| # | Asset | Technique | API |
|---|---|---|---|
| 1 | Campaign tagline | Few-shot prompting | OpenRouter |
| 2 | 200-word blog introduction | Role-based prompting | OpenRouter |
| 3 | Social media post (3 platforms) | Structured output (JSON) | OpenRouter |
| 4 | Campaign hero image | Image prompt formula | GPT Image API (`gpt-image-1`) |
| 5 | 5–8 second promotional video | Image-to-video + motion prompt | Runway API |

---

## 3. Project Structure

```
content_engine/
├── app.py          # Streamlit shell — PROVIDED (do not modify layout)
├── text_gen.py     # YOU BUILD: tagline, blog intro, social post prompts
├── image_gen.py    # YOU BUILD: image prompt constructor + GPT Image call
├── video_gen.py    # YOU BUILD: motion prompt + Runway call
├── config.py       # API keys + model settings — PROVIDED
└── .env            # OPENROUTER_API_KEY=...  RUNWAY_API_KEY=...  OPENAI_API_KEY=...
```

### What's provided in the scaffold

- Streamlit app shell (`app.py`)
- Sidebar input form with three fields and one Generate button
- Two-column main area layout (text left, visuals right)
- OpenRouter client (text generation)
- OpenAI client (image generation — separate from OpenRouter)
- Runway API wrapper
- Placeholder function signatures in `text_gen.py`, `image_gen.py`, `video_gen.py`

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
| Brand tone | `tone` | text input (or select) |

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
[CALL 3] Social Post (can run after Call 1)          [CALL 4] Hero Image
                                                                 |
                                                                 v
                                                      [CALL 5] Promo Video
                                                                 |
                                                                 v
                                              Render all five assets on screen
```

**Sequencing rules (explicit in the brief):**
- Call 1 (tagline) must complete before Calls 2 and 4 (both consume the tagline)
- Call 4 (image) must complete before Call 5 (video consumes the image)
- Call 3 (social) depends only on `product` and `tone` — can run after Call 1 at any point

---

## 6. Prompt Specifications

### 6.1 Prompt 1 — Campaign Tagline (`text_gen.py`)

**Technique:** Few-shot prompting  
**Purpose:** Generate a single on-brand tagline that captures the product and tone  
**API:** OpenRouter  

**System message (provided stub):**
```python
TAGLINE_SYSTEM = """
You are a creative director. Generate ONE campaign tagline.
Match the brand tone exactly. Max 10 words. No hashtags.
"""
```

**Your TODOs:**
```python
# TODO: build the few-shot examples based on {tone}
# TODO: user prompt = product + audience + tone
# TODO: call OpenRouter, return the tagline string
```

**Requirements:**
- Inject 2–3 few-shot examples into the prompt
- The examples must be **tone-calibrated** — different examples for different `tone` values (e.g. playful vs. premium vs. eco)
- Hard constraint: max 10 words, no hashtags
- Return type: plain string (tagline only — no labels, no quotes, no preamble)
- This output is consumed by Prompts 2 and 4; it must be clean and strippable

---

### 6.2 Prompt 2 — Blog Introduction (`text_gen.py`)

**Technique:** Role-based prompting (persona injection)  
**Purpose:** 200-word blog intro that echoes the tagline and speaks to the audience  
**API:** OpenRouter  
**Input dependency:** `{tagline}` from Prompt 1 — must be passed in as context  

**System message (provided stub):**
```python
BLOG_SYSTEM = """
You are a content strategist writing for {audience}.
Write a 200-word blog intro for {product}.
Weave in the campaign tagline: "{tagline}".
Tone: {tone}.
"""
```

**Requirements:**
- Substitute `{audience}`, `{product}`, `{tagline}`, `{tone}` at call time
- Exactly 200 words — enforce this in the prompt
- The tagline must appear woven into the copy, not bolted on
- Role is **content strategist** (not creative director, not copywriter)
- Return type: plain string (prose only)

---

### 6.3 Prompt 3 — Social Media Post (`text_gen.py`)

**Technique:** Structured output (JSON)  
**Purpose:** Platform-specific social copy respecting each platform's character limit  
**API:** OpenRouter  

**System message (provided stub):**
```python
SOCIAL_SYSTEM = """
Generate social posts for {product}.
Return ONLY JSON:
{
  "twitter": string (max 280 chars),
  "instagram": string (max 2200 chars),
  "linkedin": string (max 700 chars)
}
Tone: {tone}. No markdown fences.
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
- Parse the JSON response before passing to the display layer
- Substitute `{product}` and `{tone}` at call time
- Each platform's copy should be distinct in length and style, not just truncated versions of each other
- Done criteria explicitly checks that character limits are respected — validate them in code after parsing

---

### 6.4 Prompt 4 — Hero Image (`image_gen.py`)

**Technique:** Programmatic image prompt formula (subject + style + composition + constraints)  
**Purpose:** A campaign-grade hero image matched to product, tagline, and tone  
**API:** GPT Image API (`gpt-image-1`)  
**Input dependencies:** `{product}` + `{tagline}` from Prompt 1  

**Prompt builder (provided stub):**
```python
def build_image_prompt(product, tagline, tone):
    style = {
        "playful": "bright flat illustration",
        "premium": "photorealistic, studio lighting",
        "eco":     "watercolour, natural tones"
    }.get(tone, "clean modern")
    return (
        f"A {style} of {product}. "
        f"Centred, shallow DOF, 16:9. No text, no logos."
    )
```

**Formula breakdown:**

| Element | Example value | Source |
|---|---|---|
| Subject | `{product}` | form input |
| Style | `"photorealistic, studio lighting"` | derived from `{tone}` via lookup |
| Composition | `"Centred, shallow DOF, 16:9"` | hardcoded |
| Constraints | `"No text, no logos"` | hardcoded |

**Requirements:**
- Extend the tone→style lookup with additional tones as needed (the three given are the minimum)
- Default style (`"clean modern"`) applies for any unrecognised tone value
- Aspect ratio: 16:9 (hardcoded)
- No text, no logos in the image (hardcoded constraint — must appear in every prompt)
- Tagline is available as an input; decide whether to include it in the prompt for semantic grounding
- Output: image bytes → passed directly into Prompt 5

---

### 6.5 Prompt 5 — Promotional Video (`video_gen.py`)

**Technique:** Image-to-video with motion prompt  
**Purpose:** A 5–8 second cinematic clip derived from the hero image  
**API:** Runway  
**Input dependency:** Hero image output from Prompt 4  

**Motion prompt (provided stub):**
```python
MOTION_PROMPT = (
    "Slow cinematic push-in. "
    "Soft light shifts gently. "
    "Background mostly still. 5 seconds."
)
```

**Requirements:**
- Feed the hero image from Prompt 4 as the base frame into Runway
- Duration: 5–8 seconds (motion prompt targets 5 s; Runway `duration` parameter set to 5)
- Keep motion subtle: slow push-in, gentle light shift, mostly still background
- Do not add text overlays or hard cuts
- Output: video URL → rendered in the right column of the UI

---

## 7. Chaining Logic — Data Flow Table

| Output of | Variable name | Consumed by |
|---|---|---|
| Prompt 1 (tagline) | `tagline` | Prompt 2 system message, Prompt 4 image prompt builder |
| Prompt 2 (blog) | `blog_text` | Display only |
| Prompt 3 (social) | `social_json` (parsed dict) | Display only (3 platform cards) |
| Prompt 4 (image) | `hero_image` | Prompt 5 as base frame |
| Prompt 5 (video) | `video_clip` | Display only |

**Critical:** Each handoff must pass the actual output, not a reference. The tagline string goes directly into the f-string substitution of BLOG_SYSTEM and into `build_image_prompt()`. The image bytes go directly into the Runway API call.

---

## 8. Error Handling & Retry Logic

The brief explicitly calls out retry logic as **your responsibility** (not provided in scaffold).

Minimum requirements:
- Wrap each of the five API calls in try/except
- On failure, retry at least once before surfacing an error to the UI
- If a call in the chain fails (e.g. Prompt 4), do not attempt downstream calls that depend on it (e.g. Prompt 5)
- Display a clear error message in the relevant output card rather than crashing the app
- Social post JSON parsing: if the model returns malformed JSON (e.g. with markdown fences), strip fences before parsing; catch `json.JSONDecodeError` and show a recoverable error

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
- [ ] Video is a clean 5–8 second clip derived from the hero image
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
