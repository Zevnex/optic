# Diversity, Representation & Ethics Standard

This reference provides technical guidance on rendering authentic human diversity across skin tones, hair textures, and cultural environments, alongside strict ethical boundaries and conflict resolution procedures.

---

## 1. Technical Guide to Authentic Representation

Generative models historically suffer from bias toward Caucasian features, uniform European facial geometry, straight hair, and inaccurate subsurface skin scattering. Follow these technical guidelines:

### 1.1 Skin Tones & Subsurface Light Scattering (Fitzpatrick Scale I–VI)
Skin is not an opaque matte paint; it is a translucent multilayered biological tissue that scatters light internally (subsurface scattering / SSS):

- **Fitzpatrick Types I & II (Fair / Pale):**
  - Light interaction: High blue/red blood vessel visibility under thin skin; translucent highlights around ear cartilage and nose tip; gentle peach/pink undertones under neutral light.
  - Prompt phrasing: `natural fair skin tone with subtle rose-pink undertones, visible skin micro-texture, neutral daylight illumination`.
- **Fitzpatrick Types III & IV (Medium / Olive / Tan):**
  - Light interaction: Balanced melanin absorption; golden, warm-olive, or neutral honey undertones; crisp specular highlights on forehead and cheekbones without looking greasy.
  - Prompt phrasing: `warm olive skin tone with natural golden undertones, realistic specular highlights, authentic texture with soft laugh lines`.
- **Fitzpatrick Types V & VI (Deep Brown / Rich Dark):**
  - **The Common Model Failure:** AI models often render deep skin tones as gray, washed out, ashen, or excessively oily/plastic.
  - Light interaction: Rich melanin creates deep, saturated warmth (espresso, bronze, rich mahogany) and highly defined specular light roll-off along anatomical contours.
  - Prompt phrasing: `rich deep mahogany skin tone with luminous bronze and warm undertones, crisp specular highlight definition along the cheekbones, natural skin hydration and micro-texture, clean directional daylight`.

### 1.2 Hair Texture Taxonomy (Types 1 to 4)
Specify authentic hair architecture rather than generic descriptors:
- **Type 1 (Straight):** Fine to coarse individual strands; clean directional fall with gravitational drape.
- **Type 2 (Wavy):** Distinct S-shaped waves; natural volume at crown; gentle texture variation.
- **Type 3 (Curly):** Defined spirals and corkscrews; light bounces off individual curl rings; visible volume and natural spring.
- **Type 4 (Coily / Kinky / Afro-textured):** Tight zigzag coils, high density, matte to soft sheen light absorption; structured architectural forms (e.g., well-defined locs, two-strand twists, clean fade, tapered natural afro, braided cornrows). Always specify the exact styling technique.

### 1.3 Regional & Cultural Plausibility
When depicting international settings, avoid generic Western stock-photo environments:
- **Architecture & Materials:** Specify local building materials (e.g., terracotta roof tiles in Mediterranean, timber framing in Alpine, exposed red laterite stone in Kerala, bamboo screening in Southeast Asia).
- **Vehicles & Infrastructure:** Power lines, street signage, vehicle types, and pavement textures must correspond to the geographic region.
- **Attire & Norms:** Avoid tourist caricatures; prompt authentic contemporary everyday attire worn by locals in that specific metropolitan or rural setting.

---

## 2. Ethical Standards & Absolute Prohibitions

Natural Image Craft is dedicated to craftsmanship, realism, and physical believability—**never deceptive evasion, exploitation, or fraud.**

### Absolute Prohibitions (Zero Tolerance — Mandatory Refusal)
1. **Minors (Under 18):**
   - **Absolute Rule:** NEVER generate sexually suggestive, exploitative, abusive, or compromising imagery depicting minors or individuals who appear to be minors.
   - Any prompt touching upon sexualization or exploitation of youth must be immediately and unconditionally declined.
2. **Non-Consensual Intimate Imagery (NCII) & Deepfakes:**
   - Never generate explicit, defamatory, or compromising depictions of real, living individuals.
3. **Deceptive Photojournalism & Fake News:**
   - Never generate photorealistic images designed to fabricate historical events, catastrophic news occurrences, elections, protests, or crisis scenes with intent to deceive the public.
4. **Commercial Product Fraud:**
   - When generating visuals for a real-world product that is commercially sold to consumers, do not invent specifications, dimensions, features, or safety certifications that the actual product lacks. The image must be labeled as illustrative or conceptual.

---

## 3. Conflict Resolution Protocol: What the Agent Does

When a user request conflicts with safety, copyright, or ethical standards, the agent must execute the following protocol:

### Step 1: Detect the Violation Type
- **Category 1 (Safety / Harm):** Minor safety, NCII, hate speech, violent defamation.
- **Category 2 (Copyright / Trademark):** Request to reproduce exact proprietary logos, trademarked cartoon characters, or living artists' personal signatures.
- **Category 3 (Deceptive Reality):** Request to generate a fake personal photo, fake court evidence, or fake medical certificate.

### Step 2: Gracefully Decline & Offer Lawful Alternatives
Do not lecture or preach. State what cannot be done clearly in 1–2 sentences, and offer a compliant alternative:

```markdown
### Request Notice
I cannot generate photorealistic imagery depicting [specific sensitive element, e.g., real public figures in compromising scenarios / exact trademarked Disney character]. 

**Compliant Alternative Options:**
1. We can create an original conceptual scene capturing the same visual theme with an original character.
2. We can generate a clean, stylized architectural or documentary scene using realistic fictional subjects.
Would you like to proceed with one of these alternatives?
```

### Step 3: Mandatory Provenance & Disclosure Note
Every realistic image generated for commercial, public, or publication use must include a standard transparency footer in its delivery report:

> **Provenance & Transparency:** This visual was created with AI generative synthesis (Model: [Model Name], Date: [YYYY-MM-DD]). Consistent with digital authenticity and C2PA-style provenance conventions, this asset should be disclosed as synthetic media in editorial or consumer contexts (`qc_tools.py provenance` embeds unsigned PNG `tEXt`/`iTXt` metadata and an unsigned SHA-256 audit sidecar rather than signed C2PA CBOR/X.509 manifests).
