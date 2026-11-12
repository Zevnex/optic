# Image Generation Tool Profiles & Model Adapters

This reference documents the capabilities, prompting behaviors, parameters, and constraints for image generation models used across modern AI coding agents (Freebuff AI, Cursor, OpenAI Codex, Antigravity, Windsurf, Claude via MCP, etc.).

---

## 1. Quick Model Comparison Matrix

| Model / Engine Family | Host Environments | Negative Prompt Field? | Ideal Prompt Length | Text in Image? | Inpainting / Edits? | Aspect Ratio Control | Best Prompt Style |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **GPT-Image Family (`gpt-image-1` / OpenAI Native)** | OpenAI Codex, ChatGPT, API | ❌ No (use positive rephrasing) | 60–140 words | ⭐⭐⭐⭐ (Tier 1: Very Good ≤ 5 words) | Native multi-turn conversational edits & mask API | Presets (`1024x1024`, `1536x1024`, `1024x1536`) | Conversational, descriptive natural English |
| **Gemini Image / Nano Banana Pro** | Google Antigravity, Cursor Native, Gemini API | ❌ No (use positive rephrasing) | 70–160 words | ⭐⭐⭐⭐⭐ (Tier 1: Excellent) | Native multimodal blend & conversational edit | Presets (`1:1`, `16:9`, `4:3`, `9:16`, `21:9`) | Cohesive scene storytelling, physical lighting cues |
| **Flux.1 Pro / Dev / Fill** | Cursor / Windsurf / Claude (via MCP / Replicate / fal.ai) | ❌ No on Pro API (Dev local only via CFG) | 80–180 words | ⭐⭐⭐ (Tier 2: Short words only; prefer post-overlay) | Masked inpainting via Flux.1 Fill (`qc_tools.py mask`) | Custom width/height (multiples of 32) | Dense physical descriptions, concrete nouns, camera cues |
| **DALL-E 3 (Legacy)** | Legacy OpenAI API / MCP | ❌ No (LLM auto-expands prompt) | 50–100 words | ⭐⭐ (Tier 2: Weak; overlay text instead) | Basic API inpainting | `1024x1024`, `1024x1792`, `1792x1024` | Focused subject + environment |
| **Midjourney v6.1 / v7** | Discord, Web, Community MCP | ✅ Yes (`--no` parameter) | 40–100 words | ⭐⭐⭐ (Good with quotes `"..."`) | Vary (Region), Pan, Zoom | `--ar` parameter (e.g. `--ar 16:9`) | Evocative phrases, lighting tags, parameter flags |
| **Stable Diffusion 3.5 / SDXL** | ComfyUI, Local WebUI, fal.ai | ✅ Yes (Native negative prompt tensor) | 50–150 words | ⭐⭐⭐ (Tier 2: Medium) | Full binary mask inpaint (`qc_tools.py mask`) / ControlNet | Arbitrary aspect ratios (bucketed) | Structured weighting, positive + negative prompt pairs |
| **Ideogram 2 / 3** | Web, Ideogram API, MCP | ✅ Yes (API negative prompt supported) | 50–120 words | ⭐⭐⭐⭐⭐ (Tier 1: Industry best typography) | Masked Fill / Inpaint | Presets and custom ratios | Clear layout instructions + quoted strings for typography |

> **Runtime Model Discovery Rule:** Never hardcode speculative model IDs in API scripts. Always inspect the active MCP tool schema, environment variables, or SDK model list at runtime before invoking an API endpoint.

---

## 2. Agent-Specific Integrations & Workflows

### 2.1 Freebuff AI
- **Platform Architecture:** Open-source, ad-supported multi-surface agent (Desktop, CLI, Web app builder). Uses a dynamic model selector routing across frontier LLM/VLM providers.
- **Image Generation Pipeline:**
  - In Freebuff Web (app builder / formerly Vly), generated web layouts default to structured placeholder assets (Unsplash CDN URLs with relevant keywords) or call connected external image generation APIs via environment variables (`OPENAI_API_KEY`, `FAL_KEY`, `REPLICATE_API_TOKEN`).
  - When acting as a full-stack coding agent, Freebuff handles images by generating scripts (Python scripts with Pillow, SVG code, or calling external endpoints).
- **Recommended Strategy:**
  - Check whether an API key for Flux or OpenAI is mounted. If not, generate high-fidelity SVG or programmatic Canvas/Pillow assets, or use precision Unsplash query URLs.
  - When calling connected generative endpoints, use the positive descriptive prose style matching the active backend model.

### 2.2 Cursor AI
- **Platform Architecture:** VS Code-forked AI-native IDE with native agent capabilities and deep MCP support.
- **Image Generation Pipeline:**
  - **Native Agent Imagegen:** Powered by underlying integrated multimodal models (Google Nano Banana Pro / Gemini tier). Images automatically display inline in chat and save directly into `./assets/` or `public/images/`.
  - **MCP Extensions:** Frequently configured with `flux-replicate-mcp`, `imagegen` (OpenAI), or custom local Stable Diffusion ComfyUI bridges.
- **Recommended Strategy:**
  - Inspect workspace MCP configuration (`.cursor/mcp.json`) to detect whether Flux, OpenAI, or custom engines are bound.
  - When targeting `./assets/`, always specify an explicit, web-safe filename (`hero-banner-dark.png`) and aspect ratio.
  - If using Flux via MCP, eliminate any comma-separated negative tokens (e.g. `blurry, bad hands`) as Flux will parse them as positive objects and inject deformities.

### 2.3 OpenAI Codex
- **Platform Architecture:** OpenAI's autonomous developer command center and CLI.
- **Image Generation Pipeline:**
  - Powered natively by OpenAI's **GPT-Image** generation family (`gpt-image-1` and current multimodal endpoints).
  - Integrates reasoning before rendering — the model parses composition, light bounces, and text layouts before pixel synthesis.
  - Native multi-turn conversational image editing: You do not need to rewrite the entire prompt to fix an image; pass the previous image reference and instruct: *"Adjust the key light to 45 degrees camera-left and remove the reflections on the table."*
- **Recommended Strategy:**
  - Leverage conversational targeted editing instead of re-rolling from scratch.
  - Keep prompts natural and narrative. Do not use Midjourney-style weighting syntax (`::2`) or SD-style brackets (`(masterpiece:1.2)`).

### 2.4 Google Antigravity
- **Platform Architecture:** Agentic development platform powered by Gemini multimodal architecture.
- **Image Generation Pipeline:**
  - Uses Google's **Nano Banana Pro** and **Gemini 3.x Image** generative layers.
  - Exceptional text rendering and complex scene understanding.
  - Supports native multi-image reference composition (e.g. combining a product render with an environmental background).
- **Recommended Strategy:**
  - Specify clear physical environments, light sources, and spatial relationships.
  - Use exact quoted text strings when text rendering is required (e.g., `a wooden storefront sign reading "CRAFT COFFEE" in clean serif lettering`).

### 2.5 Windsurf (Codeium Cascade)
- **Platform Architecture:** Cascade multimodal coding agent.
- **Image Generation Pipeline:**
  - Natively excels at multimodal design-to-code (parsing UI screenshots into Tailwind/React).
  - Generative images are produced via MCP tool integration (e.g., Cloudinary MCP, Fal.ai MCP) or programmatic generation scripts.
- **Recommended Strategy:**
  - Verify MCP tool schemas before prompting.
  - Route asset generation to project assets folders and immediately wire them into components.

---

## 3. Negative Prompt Handling by Engine

Many prompt engineers trained on Stable Diffusion 1.5 assume every model takes a negative prompt. **Modern diffusion transformer (DiT) models do NOT work this way.**

| Engine | Behavior When Given Negative Prompts | Correct Prompting Method |
| :--- | :--- | :--- |
| **Flux.1 Pro** | **Harmful:** Passing "no deformed fingers, no blurry background" causes the T5 text encoder to attend to "fingers" and "blurry", often *increasing* defects. | Use positive affirmation: `crisp focus throughout, anatomically correct fingers resting on the mahogany surface`. |
| **GPT-Image / DALL-E 3** | **Unreliable:** Words like "without people" frequently spawn people because token presence registers more strongly than semantic negation. | Rephrase contextually: `a completely deserted, silent city avenue at dawn` instead of `a city with no people and no cars`. |
| **Midjourney v7** | **Effective via `--no` parameter:** Midjourney strips tokens passed to `--no` from the positive CLIP embedding space. | Place unwanted elements strictly after `--no`: `--no text, watermark, frames, blur`. |
| **Stable Diffusion 3.5 / SDXL** | **Native positive/negative dual conditioning:** Uses separate negative prompt tensor. | Put style degradations and unwanted anatomy in negative prompt: `deformed, extra limbs, oversaturated, plastic skin, CGI`. |

---

## 4. Prompt Length & Keyword Effectiveness Guide

### Quality Words: What Works vs. What Hurts

| Term / Adjective | Status | Actual Impact | Better Alternative |
| :--- | :--- | :--- | :--- |
| `8k`, `photorealistic`, `hyperrealistic` | 🚫 Harmful | Triggers training data scraped from stock sites and amateur 3D art boards; produces glossy plastic sheen. | Specify the camera format and lens: `shot on 35mm full-frame camera, Kodak Portra 400 tone`. |
| `cinematic`, `epic`, `dramatic lighting` | ⚠️ Risky | Triggers aggressive teal/orange split-toning and heavy artificial volumetric haze. | Describe the specific light setup: `warm low-angled sunlight casting long soft shadows from camera right`. |
| `masterpiece`, `trending on ArtStation` | 🚫 Obsolete | Ignored by modern DiT models (Flux, GPT-Image); causes style drift in SDXL. | Describe physical textures: `unpolished brushed aluminum surface with micro-scratches`. |
| `natural skin texture`, `subtle pores` | ✅ Effective | Counteracts smoothing/denoising filters in modern models. | `candid photograph, natural unretouched skin texture with visible pores and subtle skin tone variation`. |
| `shallow depth of field`, `f/2.8` | ✅ Effective | Successfully guides background blur and subject separation. | `moderate depth of field, f/4, background softly out of focus while keeping the entire subject sharp`. |

---

## 5. Text-in-Image Capabilities & Guidelines

1. **Ideogram 3 & Nano Banana Pro / Gemini 3 Image:**
   - Both handle multiline typographic composition, font styling (serif, sans-serif, slab, handwritten), and precise spelling.
   - Syntax: Put text inside quotation marks: `a retro diner menu board with the text "DAILY SPECIAL: HOMEMADE PIE" in bold red capital letters`.
2. **Flux.1 Pro / GPT-Image 2.6:**
   - Reliable for 1–4 words (e.g. logos, street signs, brand names, product packaging).
   - Prone to spelling errors on paragraphs or small cursive scripts.
   - Rule: Keep generated text under 5 words. Typeset longer copy post-generation using HTML/Canvas or graphics editors.
3. **DALL-E 3 & SDXL:**
   - Weak text rendering.
   - Rule: Avoid in-image text. Prompt a clean blank area (copy space) and composite typography post-generation.
