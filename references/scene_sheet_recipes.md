# Scene Sheet Recipes & Combinatorial Diversity Matrix

This reference provides production-ready parameter recipes across the 6 most common image generation requests, alongside a physical entropy system to eliminate repetitive "AI slop" tropes.

---

## 1. Physical Entropy Engine: Escaping the Slop Trope Trap

### The Trap: Formulaic Imperfections
When prompt templates reuse the same "flyaway hair, coffee ring stain, subtle fingerprint, specks of dust" in every generation, they establish a new, easily identified AI cliché. 

### The Law of Motivated Entropy
**Every imperfection in an image must have a traceable physical cause.** Ask: *How old is this object? What is the climate? Who touched it last? What physical force acted upon it?*

| Physical Cause | Surface / Environment | Physical Result to Prompt (Choose 2–3 Per Scene) |
| :--- | :--- | :--- |
| **Mechanical Handling** | Tool, laptop, door handle, phone | Micro-buffing along high-contact edges; faint key scratches; slight patina on brass/leather. |
| **Thermal / Atmospheric** | Cold drink, hot kitchen, window | Condensation droplets pooling at base; faint steam wisps; heat haze; frost crystals on glass edge. |
| **Gravitational Settling** | Fabric, cushions, paper, clothing | Compression creases behind knees/elbows; slight fabric sag; asymmetrical drape over a chair arm. |
| **Age / Oxidation** | Wood, paper, painted metal, brick | Sun-bleaching on window-facing surfaces; hairline crazing in ceramic glaze; slight paper corner curl. |
| **Industrial / Fabrication** | Molded plastic, sewn goods, metals | Hairline parting seams on injection-molded plastic; single stray thread at a double-stitched hem. |
| **Environmental Residue** | Outdoor surfaces, workshop, street | Dried rain splash marks on lower window pane; chalk dust on slate; tire scuffs on warehouse floor. |

---

## 2. Combinatorial Diversity Matrix

Never default to `85mm, f/2, window light` for every image. Sample dynamically across this matrix:

```
[Camera Focal Length]   ×   [Lighting Geometry]       ×   [Camera Perspective]
----------------------------------------------------------------------------------
24mm (Wide Context)         Overhead Skylight Diffuse     Eye-Level Straight-On
35mm (Documentary/Street)   Low-Angle Raking Sun (Dawn)   Low-Angle Heroic (+15°)
50mm (Natural Eye Perspective) Side Rim/Kicker + Bounce   High-Angle Looking Down (-30°)
85mm (Compressed Portrait)  Single Hard Tungsten Point    Over-The-Shoulder (OTS)
105mm (Macro Detail/Product) Softbox 45° Key + Reflector  Three-Quarter Off-Center
```

---

## 3. The Hand Placement Framework: Stop "Hiding Hands"

Telling the model to "hide hands in pockets" or "crop out hands" creates awkward, unnatural amputated poses. Instead, give hands **active physical tasks with clear weight-bearing contact**:

1. **Resting Weight:** Both hands flat on a table, palms down, knuckles slightly relaxed.
2. **Firm Tool Grip:** Hand holding a pen, camera grip, or chef knife, fingers wrapped naturally around the handle with knuckles visible.
3. **Resting Support:** One hand resting against the jaw or temple, fingers softly curled, elbow resting on desk.
4. **Bimanual Task:** Two hands working in tandem (e.g., tying apron strings, typing with index fingers raised, opening a ledger).
5. **One-Handed Active:** Holding a ceramic mug by the body (not delicate handle loop), fingers wrapping the cylinder.

---

## 4. Six Production Parameter Recipes

### Recipe 1: Modern E-Commerce / Studio Product Shot
- **Primary Use:** Online store, Amazon hero asset, marketing catalog.
- **Aspect Ratio:** 1:1 or 4:5 vertical.
- **Camera & Lens:** 100mm macro or 85mm medium-telephoto; f/8 to f/11 (deep focus, crisp front-to-back sharpness).
- **Camera Angle:** Slight 15° top-down elevation, 30° off-axis rotation.
- **Lighting Architecture:** Commercial studio setup. Large overhead diffused softbox (key) providing clean gradient highlights across the product top; white foam-core bounce card on camera-left filling deep shadows; faint neutral rim light on back edge for separation.
- **Materials & Surfaces:** Matte neutral-grey or warm-limestone plinth; crisp product materials (e.g. frosted amber glass, brushed 6061 anodized aluminum).
- **Physical Entropy (2 items):** Microscopic manufacturing seam along injection-molded edge; faint soft shadow contact band anchoring the base to the plinth.
- **Color & Balance:** 5500K daylight neutral white balance; pure accurate product tones; zero split-toning.
- **Copy Space:** Product situated lower-right or centered; clean background for packaging text overlay.

### Recipe 2: Executive / Editorial Headshot & Portrait
- **Primary Use:** About page, LinkedIn, magazine feature, press kit.
- **Aspect Ratio:** 3:4 portrait or 16:9 contextual banner.
- **Camera & Lens:** 70mm to 85mm prime lens; f/3.2 to f/4.0 (sharp focus on both eyes, subtle softening of ears and background).
- **Camera Angle:** Exactly eye-level; subject turned 20° away from lens, gaze returning toward camera.
- **Lighting Architecture:** Large diffused North-facing window on camera-right (45° angle) creating gentle wrap; subtle ambient room fill preventing crushed shadows; clean single catchlight visible at 1 o'clock in both irises.
- **Hands Recipe:** One hand resting naturally on table edge, fingers relaxed; second hand out of frame or resting in lap.
- **Physical Entropy (3 items):** Natural unretouched skin texture with fine pores and gentle laugh lines around eyes; slight asymmetrical collar roll on cotton shirt; two stray natural hair strands over the temple.
- **Color & Balance:** Natural skin tone calibrated to subject's heritage; neutral gray/warm background tones; 4800K light.

### Recipe 3: SaaS / Web Hero Banner with Negative Space
- **Primary Use:** Website homepage hero section, desktop app landing page.
- **Aspect Ratio:** 16:9 or 21:9 ultra-wide landscape.
- **Camera & Lens:** 35mm wide-normal lens; f/5.6 (sharp midground, gentle falloff).
- **Camera Angle:** Slightly low eye-level (+10°), positioned off-center.
- **Composition & Copy Space:** **Rule of Two-Thirds.** Left 60% of the canvas consists of clean, uncluttered architectural wall, window, or minimal gradient suitable for dark or light typography overlay; primary visual interest concentrated in the right 40%.
- **Lighting Architecture:** Soft morning diffused daylight entering from tall floor-to-ceiling glass on far right; subtle overhead recessed 3000K LED glow in ceiling.
- **Subject / Props:** Modern ergonomic standing desk with matte oak surface, minimal ceramic mug, closed anodized notebook.
- **Physical Entropy (2 items):** Braided nylon power cable looping cleanly behind table leg; subtle daylight reflection gradient across the matte desk finish.

### Recipe 4: Culinary & Food Photography
- **Primary Use:** Restaurant menu, culinary editorial, cookbook cover.
- **Aspect Ratio:** 4:5 vertical or 1:1.
- **Camera & Lens:** 90mm macro tilt-shift lens; f/4.5 (slice of selective focus on the hero ingredient, e.g., the caramelized crust).
- **Camera Angle:** 45° diner's perspective or 90° straight-down flat lay.
- **Lighting Architecture:** Strong directional side-backlight (10 o'clock position) skimming the dish to accentuate glistening moisture and crisp textures; small silver card bounce at 4 o'clock filling foreground shadows.
- **Materials:** Hand-thrown stoneware ceramic plate with matte speckled glaze; rough linen napkin with natural weave.
- **Physical Entropy (3 items):** Uneven golden caramelization blistering on baked pastry edge; single flake of coarse sea salt resting on the rim; micro-droplets of olive oil glistening on microgreen garnish.
- **Color & Balance:** Warm 4200K culinary balance; rich earthy tones; vibrant organic greens.

### Recipe 5: Architecture & Interior Design Space
- **Primary Use:** Architectural digest, hospitality portfolio, real estate showcase.
- **Aspect Ratio:** 3:2 landscape or 16:9.
- **Camera & Lens:** 24mm architectural tilt-shift lens (zero keystone distortion; vertical walls strictly parallel to frame edges); f/8.
- **Camera Angle:** Standing chest height (approx. 1.3m / 4.2ft above finished floor); single-point or two-point perspective.
- **Lighting Architecture:** Balanced ambient exposure. Daylight streaming through external openings balanced with warm interior accent lamps (2700K practicals in corners). Shadows under furniture are grounded and directional.
- **Materials:** Polished terrazzo floor with subtle aggregates; fluted white oak cabinetry; raw linen curtains.
- **Physical Entropy (3 items):** Natural wood grain variation across cabinet panels; faint foot traffic matte sheen variation near entry; soft organic folds in linen drape pooling gently onto floor.

### Recipe 6: Documentary & Editorial Lifestyle Scene
- **Primary Use:** Editorial essay, brand story, authentic lifestyle marketing.
- **Aspect Ratio:** 3:2 standard 35mm film ratio.
- **Camera & Lens:** 35mm or 50mm f/1.4 prime; shot at f/2.8.
- **Camera Angle:** Unobtrusive observer perspective, shooting at eye-height from mid-distance (2.5 meters).
- **Lighting Architecture:** 100% available ambient light (overcast cloudy sky through industrial glass window, or late afternoon street light). No artificial studio strobes.
- **Subject & Action:** Subject engaged in an authentic craft or task (e.g. measuring timber with a brass ruler; reviewing paper schematics on a drafting table).
- **Hands Recipe:** Bimanual purposeful task: left hand holding edge of blueprint flat; right hand holding graphite pencil with realistic thumb-forefinger grip.
- **Physical Entropy (3 items):** Faint graphite dust smudge near paper border; worn denim work shirt with faded elbow creases; micro-abrasions on wooden workbench surface.
