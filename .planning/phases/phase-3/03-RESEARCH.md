# Phase 3: Asset Management & Manifest - Research

**Researched:** 2026-08-24
**Domain:** Deterministic slot resolution over a fixed beat list + Google image-generation API usage (google-genai, MLDev/API-key backend)
**Confidence:** MEDIUM — slot-resolution math and manifest shape are HIGH (computed directly from `output/beats.json` and installed SDK source this session); the exact image-generation call that produced the smoke test is unverifiable (script no longer exists), so the recommended call pattern is HIGH-confidence-but-substitute, not a confirmed replay of what worked.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Slot Identity**
- **D-01:** Slot identity is resolved **automatically, with no human alias list**. The system makes its best guess and records how it guessed. A first pass does not get hand-curated input.
- **D-02:** A scene whose heading is not an `INT.`/`EXT.` slug **inherits the location of the preceding scene**. This is deterministic and fixes the known case: script scene 2 is a `SUPERIMPOSE` title card with no slug of its own, and the extractor invented `INT. BOXING CLUB - NIGHT` for it while script scene 1 calls the same room `INT. BLUE DOOR FIGHT CLUB - NIGHT`. Same room, two names, two would-be slots.
  — Reversibility: reversible — a resolver rule, local to slot assignment.
- **D-03:** Beyond the inheritance rule, resolve remaining headings by normalising the slug (drop `INT.`/`EXT.`, time-of-day suffix, punctuation, possessives) and then clustering what is left semantically. Every merge records both the source headings and why they were judged the same place, so a wrong guess is visible in the manifest rather than silent.
  — Reversibility: reversible — merges are data in the manifest, re-runnable.

**Character Slots and Voices**
- **D-04:** Art slots and voice identities are separate axes and do not collapse the same way. Minor characters share generic *visual* slots; they must not share *voices*.
- **D-05:** Minor characters (1-2 beats, unnamed function roles — `FIGHTER #1`, `FIGHTER #2`, `FAN`, `ANNOUNCER`) map to **generic art slots** rather than getting bespoke generated character art.
- **D-06:** Two characters who speak in the same scene must never be given the same voice. `FIGHTER #1` and `FIGHTER #2` talk to each other in scene 3 — sharing a generic art slot is fine, sharing a voice is not. Voice identity is per named character, not per art slot, and the registry must enforce distinctness within a scene.
  — Reversibility: costly — Phase 5 casts voices from this key; changing the axis later means recasting and regenerating all dialogue audio.
- **D-07:** All 9 characters in the beat list speak, so the slot registry doubles as the voice registry Phase 5 consumes. Build the key once here rather than twice.

**Style Consistency**
- **D-08:** A shared generic style prompt drives consistency across all generated slots — one style definition applied to every generation, rather than per-slot prompt wording.
  — Reversibility: reversible — regenerating temp art is cheap.
- **D-09:** The style prompt must actively suppress the failure modes observed in the Google AI smoke test (2026-08-24): the model returned greyscale with heavy shading instead of black line art on white, added storyboard chrome (spiral notebook binding, a panel caption), and rendered instruction words into the frame as artwork. Notably the phrase "storyboard panel" *caused* the chrome. The facial-feature rule was respected. Evidence: `output/smoke/panel_test_0.png`.

**Manifest Priority**
- **D-10:** Priority is defined as **how much of the finished cut depends on the slot** — its share of total screen time, not a generation order or a cost band. Rocky appears in 31 of 49 beats; the hallway appears in 1.
- **D-11:** This definition serves every downstream use at once: generation order, budget order, and the ranked answer to "which slots would most benefit from real reference art being supplied." Each entry records the underlying numbers (beats, seconds, share) as its reason.
  — Reversibility: reversible — a derived field, recomputable from the beat list.

### Claude's Discretion
- Slot naming scheme and manifest file format and location.
- Which specific generic art slots exist and how a character is judged "minor."
- Change-detection mechanism for slot-file replacement (content hash vs mtime) and what a replacement invalidates — default to content hashing, which is re-runnable and does not depend on filesystem timestamps.
- How the style prompt is expressed and where it lives.

### Deferred Ideas (OUT OF SCOPE)
- Hand-curated slot alias map / human-in-the-loop slot correction — explicitly excluded from the first pass (D-01).
- CloudFront CDN and TLS for the hosted URL — Phase 1 gap, in the roadmap backlog.
- `beat_assembler` robustness (swallowed `ClientError` returning `local://` under a 200; uncaught `ProfileNotFound`) — not this phase's goal, but this phase writes to the same bucket, so fold the fix in if it is cheap.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| FR-02 | Asset management: named slots, temp-art fallback, replace-and-regenerate, priority manifest | See Standard Stack, Architecture Patterns, Code Examples, Change Detection sections |
| NFR-04 | Every generated artifact carries a machine-readable reason field | See Manifest Shape (`## Architecture Patterns > Pattern: Manifest Entry Shape`) — every slot entry records `source`, `reason`, `priority_reason` |
| NFR-03 (carried constraint, not owned by this phase) | Google Cloud SDK only for AI | See Standard Stack — `google-genai` only, MLDev/API-key backend, no Vertex/aiplatform dependency added |
</phase_requirements>

## Summary

Phase 3 has two genuinely separate problems that the roadmap bundles together: (1) a **pure data-transformation problem** — collapsing 8 scene headings and 9 characters from `output/beats.json` into a deduplicated slot registry with priority — which is fully computable today with stdlib tools and no AI call; and (2) an **AI image-generation problem** — producing black-line-art temp art for every slot lacking reference art, using `google-genai` against the Gemini Developer API (the `GOOGLE_API_KEY` / MLDev backend already smoke-tested and proven working in STATE.md).

Running the D-02/D-03 rules mechanically against the actual current beat list produces a **different slot count than the CONTEXT.md scope anchor**: 9 character slots (unchanged) but **6 location slots, not 8** — because D-02 folds scene 2 into scene 1, and D-03's own normalization step (drop `INT.`/`EXT.`) causes `EXT. ROCKY'S APARTMENT - NIGHT` (scene 6) and `INT. ROCKY'S APARTMENT - NIGHT` (scene 8) to collapse to the same key mechanically, not just the SUPERIMPOSE case the decision was written to fix. This is flagged in detail below — it is a faithful consequence of the locked rules, not a bug, but the planner should decide consciously whether an apartment's interior and exterior sharing one identity-anchor slot is intended, since Phase 4 will need the beat's own `scene_heading` (not just the slot) to know which shot to actually draw.

For image generation, the installed `google-genai==2.19.0` SDK confirms two workable call surfaces: the established `client.models.generate_content(..., config=types.GenerateContentConfig(response_modalities=["IMAGE"], ...))` pattern (already used elsewhere in this codebase for text, and confirmed in the SDK's own test suite for image output), and a newer `client.interactions.create(model=..., input=[...])` surface that natively supports `system_instruction` and up to multiple reference images. **A real, SDK-source-confirmed risk**: the legacy `generate_content` path raises a `ClientError` ("Developer instruction is not enabled for models/gemini-2.5-flash-image") when `system_instruction` is combined with an image-output model on the API-key backend, in the SDK's own replay tests. The safe, zero-cost mitigation — verified to sidestep the restriction entirely — is to fold the shared style block (D-08) directly into the **prompt text**, not `system_instruction`, regardless of which call surface is used.

The observed smoke-test failure (greyscale shading, spiral-notebook chrome, "NO FACIALS" burned into the frame as text) matches a well-documented Gemini image-model failure mode: the model treats short imperative/negated phrases and genre words ("storyboard panel") as literal content to render, not as instructions about the image. The fix is procedural, not magical — state the style positively ("flat black ink linework on pure white, no shading, no gradients") instead of negatively ("no shading"), and never phrase an instruction as a short all-caps or quoted label, since that is exactly what a caption looks like to the model.

**Primary recommendation:** Do the slot-resolution and manifest-assembly work as pure Python (stdlib `difflib`/`hashlib`/`re`, no AI call) following the `beat_assembler.py` dual-write precedent; call `client.models.generate_content` (not the newer, less-proven `interactions.create`) for temp-art generation, with the style block embedded in the prompt text; verify the exact `gemini-3.1-flash-image` call against a real key before committing the plan's implementation details, since the original smoke-test script that produced the 697 KB image no longer exists in the repo or git history.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Slot identity resolution (character/location dedup) | API / Backend (pure Python, `animatic.core`) | — | Deterministic transform over `output/beats.json`; no AI call needed, matches `beat_extractor`/`scene_timing` precedent of doing work in code, not prompts |
| Priority computation (screen-time share) | API / Backend | — | Pure aggregation over beat durations, same tier as slot resolution |
| Temp-art generation (image model call) | API / Backend | External Service (Google Gemini Developer API) | `google-genai` client call happens server-side; no browser/CDN tier involved in this phase |
| Reference-art ingestion (file → slot match) | API / Backend | Storage (S3 `media_bucket`) | Files live under `assets/reference-art/` locally, mirrored to S3 alongside beats — same dual-write tier as `beat_assembler` |
| Asset manifest (slot registry + voice keys) | API / Backend | Storage (S3 `media_bucket`) | Follows `_build_beat_list`/`assemble_and_write` precedent exactly |
| Change detection (content hash) | API / Backend | — | Computed at write time from file bytes; consumed by Phase 4's panel cache, not by this phase's own runtime |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `google-genai` | 2.19.0 (installed; `requirements.txt` pins `>=0.8`) | Image generation calls (`client.models.generate_content` / `client.interactions.create`) | Only AI SDK permitted under NFR-03; already the project's sole AI dependency (used in `beat_extractor.py`) [VERIFIED: `.venv/lib/python3.14/site-packages/google_genai-2.19.0.dist-info`, `requirements.txt:5`] |
| `boto3` | `>=1.34` (already a dependency) | S3 dual-write of manifest + generated art, following `beat_assembler.py`'s pattern | Already established in Phase 2; no new dependency [VERIFIED: `requirements.txt:6`, `src/animatic/core/beat_assembler.py:12-13`] |
| `hashlib` (stdlib) | Python 3.14 stdlib | Content-hash change detection per slot (Claude's Discretion → content hashing) | No dependency, deterministic, filesystem-timestamp-independent as CONTEXT.md's discretion note requires |
| `difflib` (stdlib) | Python 3.14 stdlib | Fallback near-duplicate heading matching after normalization, if exact-match clustering leaves ambiguous pairs | Zero-dependency string-similarity primitive; sufficient for an 8-scene fixed corpus — see Don't Hand-Roll |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `Pillow` | 12.3.0 (already installed transitively via `google-genai`, **not pinned explicitly** in `requirements.txt`) | Validate uploaded reference-art files are real images (format/dimension sanity check) before hashing/using them | Only if the plan wants to reject a corrupt/non-image file placed in `assets/reference-art/`; otherwise raw byte hashing needs nothing but `hashlib` [VERIFIED: `.venv/lib/python3.14/site-packages/pillow-12.3.0.dist-info` present in this project's own venv] |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| stdlib `difflib` for heading clustering | `rapidfuzz` (fuzzy-match library) | Faster and more configurable, but it's a new dependency for an 8-heading corpus that `difflib` already solves; not installed today — do not add it for this phase |
| `client.models.generate_content` for image calls | `client.interactions.create` (newer NextGen API) | Natively supports `system_instruction` and documents up to 14 reference images per call, but it is a "GAOS"/preview surface layered under Speakeasy-generated code in the same SDK, not what the project's one proven smoke test used — higher unknown-unknown risk this close to deadline |
| Google Developer API (`GOOGLE_API_KEY`, MLDev backend) | Vertex AI (`google-cloud-aiplatform`, also NFR-03-legal) | Vertex unlocks `edit_image`/`recontext_image` (Imagen reference-image compositing with masks/style refs), but those specific calls raise on the MLDev backend in the SDK's own tests — switching backends now means new GCP project/credential plumbing with no time budget to de-risk it |

**Installation:** No new dependency required beyond what's already in `requirements.txt`. If reference-art validation is added, explicitly pin `pillow>=12.0` (see Package Legitimacy Audit).

**Version verification:** `google-genai` 2.19.0 confirmed installed via `pip show google-genai` in this project's own `.venv` this session [VERIFIED: local `pip show` output, this session]. `requirements.txt` pins only `>=0.8`, a wide floor — no action needed, current install already satisfies it.

## Package Legitimacy Audit

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|--------------|---------|-------------|
| `pillow` | PyPI | long-established (PyPI listing shows a 2026-07-01 latest-release timestamp; project is the maintained fork of the original PIL, active since 2010) | unknown (lookup returned null) | `github.com/python-pillow/Pillow` | SUS (`unknown-downloads`) | Approved — the SUS verdict is a data-gap artifact (the legitimacy checker could not retrieve a download count), not a legitimacy signal. Pillow is already installed and in use transitively in this project's own `.venv` (confirmed via `ls .venv/.../site-packages` this session), verified official repo present. Add `pillow>=12.0` to `requirements.txt` explicitly if reference-art validation is implemented; no `checkpoint:human-verify` needed given it's already running in the environment. |

**Packages removed due to [SLOP] verdict:** none.
**Packages flagged as suspicious [SUS]:** `pillow` — see disposition above; not gated behind a human-verify checkpoint because it is already present and running in the project's own dependency tree, not newly introduced from an unverified source.

## Architecture Patterns

### System Architecture Diagram

```
output/beats.json (or S3 beats/latest.json)
        │
        ▼
┌───────────────────────────┐
│ slot_resolver.py           │  1. collect raw {character, scene_heading} per beat
│ (pure Python, no AI call)  │  2. apply D-02 inheritance (heading with no real
│                            │     INT./EXT. slug in the raw PDF → inherit prior
│                            │     scene's resolved location)
│                            │  3. apply D-03 normalize+cluster (strip INT./EXT.,
│                            │     time-of-day suffix, punctuation, possessive;
│                            │     exact-match then difflib near-match)
│                            │  4. classify characters major/minor (D-05)
│                            │  5. compute priority = beats/secs/share (D-10/D-11)
└──────────────┬─────────────┘
               │  list[Slot]  (character + location, unified)
               ▼
┌───────────────────────────┐        ┌──────────────────────────┐
│ reference art ingestion    │───────▶│ asset_manifest.py         │
│ assets/reference-art/*.jpg │ match  │ (mirrors beat_assembler   │
│ (filename → slot_id)       │ found  │  dual-write pattern)      │
└─────────────────────────────┘       │                            │
                                       │ for each slot:             │
               no match found ───────▶│  - source = reference | gen │
                                       │  - if gen: call             │
                                       │    genai image model with   │
                                       │    shared style block in    │
                                       │    prompt text (D-08/D-09)  │
                                       │  - content_hash = sha256    │
                                       │  - reason (NFR-04)          │
                                       └──────────────┬─────────────┘
                                                       ▼
                                    local: output/assets/manifest.json
                                    S3:    s3://<media_bucket>/assets/manifest.json
                                    (consumed by Phase 4 panel generation
                                     and Phase 5 voice casting)
```

### Recommended Project Structure
```
src/animatic/core/
├── slot_resolver.py     # beats.json -> list[Slot] (character + location, deduped, prioritized)
├── asset_generator.py   # Slot -> temp art via genai image call, style block applied
├── asset_manifest.py    # assemble manifest dict, local+S3 dual write (mirrors beat_assembler.py)
assets/
├── reference-art/       # existing — user-supplied reference images (flat, unslotted today)
output/
├── assets/
│   ├── manifest.json    # local mirror, same convention as output/beats.json
│   └── generated/       # generated temp art files, named <slot_id>.png
```

### Pattern: Slot Resolution — D-02 Inheritance Requires Re-Reading the PDF, Not Just `beats.json`

**What:** `output/beats.json`'s per-beat `scene_heading` field is **already Gemini's invented text**, not the raw script slug — `beat_extractor.py`'s prompt asks the model to fill `scene_heading` per beat with no ground truth for scenes lacking a real slug, which is exactly why scene 2 got the invented `INT. BOXING CLUB - NIGHT` [VERIFIED: `output/beats.json` beat `s2b1.scene_heading`, read this session]. There is no field in `beats.json` recording whether a scene's heading is "real" (matched `INT.`/`EXT.` in the source PDF) or invented. To implement D-02 correctly, Phase 3 must independently call `pdf_extractor.extract_scenes()` again (cheap — no LLM call, `pdfplumber` only) and test each scene's own raw heading line against an `INT.`/`EXT.` prefix pattern; only then can it decide "this scene has no real slug, inherit the previous scene's resolved location."

**When to use:** Any time a scene's canonical location is derived — always, since this is now the deterministic backbone of location-slot resolution, not an edge case.

**Example:**
```python
# Source: src/animatic/core/pdf_extractor.py (read this session, lines 1-84)
from animatic.core.pdf_extractor import extract_scenes

_SLUG_RE = re.compile(r"^\d+\s+(INT\.|EXT\.)", re.IGNORECASE)

raw_scenes = extract_scenes(pdf_path, first_n=8)  # dict[int, str] — heading + body, in appearance order
has_own_slug: dict[int, bool] = {
    scene_num: bool(_SLUG_RE.match(text))
    for scene_num, text in raw_scenes.items()
}
# has_own_slug[2] is False for Rocky — its raw block starts
# "2 SUPERIMPOSE OVER ACTION... "NOVEMBER 12, 1975 - 2" per
# .planning/phases/phase-2/2-VERIFICATION.md, which quotes the
# actual extracted text [VERIFIED: 2-VERIFICATION.md, read this session]:
#   "2 SUPERIMPOSE OVER ACTION... "NOVEMBER 12, 1975 - 2
#   PHILADELPHIA"
#   ... The club itself resembles a large unemptied trash-can."
```

### Pattern: D-02/D-03 Applied to the Actual Beat List — Computed Result

**What:** Running the locked rules against `output/beats.json` as it exists today [VERIFIED: computed from `output/beats.json` via direct read+aggregation this session] produces:

Raw `scene_heading` per scene (currently in `beats.json`, one per scene, model-invented for scene 2):

| Scene | Raw `scene_heading` (as currently in beats.json) | Has real INT./EXT. slug in PDF? |
|-------|---|---|
| 1 | `INT. BLUE DOOR FIGHT CLUB - NIGHT` | yes |
| 2 | `INT. BOXING CLUB - NIGHT` | **no — SUPERIMPOSE card, D-02 inherits scene 1** |
| 3 | `INT. DRESSING ROOM - NIGHT` | yes |
| 4 | `INT. TROLLEY - NIGHT` | yes |
| 5 | `EXT. STREET - NIGHT` | yes |
| 6 | `EXT. ROCKY'S APARTMENT - NIGHT` | yes |
| 7 | `INT. ROCKY'S HALLWAY - NIGHT` | yes |
| 8 | `INT. ROCKY'S APARTMENT - NIGHT` | yes |

After D-02 (scene 2 → scene 1's location) and D-03 normalization (drop `INT.`/`EXT.` + `- NIGHT` + punctuation/possessive) applied literally, scene 6 and scene 8 both normalize to the same key (`ROCKYS APARTMENT`) and **cluster together as one slot mechanically** — this is not the SUPERIMPOSE case D-02 was written for, it is a side effect of D-03's own normalization step being applied uniformly. Final canonical locations:

| Canonical location slot | Source scenes | Beats | Secs | Share of 255.7s | Priority rank |
|---|---|---|---:|---:|---:|
| BLUE DOOR FIGHT CLUB | 1, 2 (D-02 inherited) | 20 | 117.8 | 46.1% | 1 |
| DRESSING ROOM | 3 | 10 | 54.4 | 21.3% | 2 |
| ROCKY'S APARTMENT | 6, 8 (D-03 normalize-merged) | 9 | 40.1 | 15.7% | 3 |
| TROLLEY | 4 | 4 | 22.2 | 8.7% | 4 |
| STREET | 5 | 5 | 15.6 | 6.1% | 5 |
| ROCKY'S HALLWAY | 7 | 1 | 5.6 | 2.2% | 6 |

**This yields 6 location slots, not the 8 in CONTEXT.md's scope anchor**, and combined with the unchanged 9 character slots gives **15 total slots, not 17**. Reference art (`assets/reference-art/`) covers only the ROCKY character slot, so **14 slots need generated temp art, not 16**. This is flagged, not silently corrected — CONTEXT.md calls its own count a "scope anchor," and the discrepancy is a faithful, deterministic consequence of applying D-02+D-03 exactly as written, not a research error. The planner should decide consciously whether merging `EXT. ROCKY'S APARTMENT` and `INT. ROCKY'S APARTMENT` into one identity-anchor slot is intended (plausible — a location slot can function as a style/identity anchor rather than a literal single photo, with Phase 4 varying the actual per-beat framing from the beat's own `scene_heading`) or whether D-03 should special-case INT./EXT. pairs of the same name as siblings rather than duplicates. Either way, the manifest's merge `reason` field (already required by D-03) makes the decision visible and auditable regardless of which way it's decided.

### Pattern: Character Priority and Minor-Character Classification — Computed Result

[VERIFIED: computed from `output/beats.json` via direct read+aggregation this session]

| Character | Beats | Secs | Share | D-05 minor? (≤2 beats, function-role name) |
|---|---:|---:|---:|---|
| ROCKY | 31 | 152.3 | 59.6% | no (bespoke) |
| BLACK FIGHTER | 5 | 34.7 | 13.6% | no (bespoke) |
| PROMOTER | 5 | 28.3 | 11.1% | no (bespoke) |
| CORNERMAN | 4 | 21.3 | 8.3% | no (bespoke) |
| WOMAN | 3 | 17.1 | 6.7% | no (bespoke) — 3 beats exceeds the "1-2 beats" threshold in D-05's own wording even though the name is function-style |
| FIGHTER #1 | 2 | 12.5 | 4.9% | **yes** — D-05's own named example |
| FAN | 1 | 8.4 | 3.3% | **yes** — D-05's own named example |
| ANNOUNCER | 1 | 7.2 | 2.8% | **yes** — D-05's own named example |
| FIGHTER #2 | 1 | 3.0 | 1.2% | **yes** — D-05's own named example |

Recommended threshold, made explicit since CONTEXT.md leaves "how a character is judged minor" to discretion: **minor = character appears in ≤2 beats**, matching all four of D-05's own named examples exactly (`FIGHTER #1` at exactly 2 beats is the boundary case). This gives 5 bespoke character slots + 4 minor characters sharing generic slot(s). Recommend **one shared generic-minor-character art slot** for the first pass (simplest; all 4 minor characters render as an unnamed generic figure in the house line-art style) — a per-archetype split (e.g. "generic boxer" vs "generic civilian") is a cheap upgrade if time allows, not required for FR-02.

### Pattern: Voice Registry Doubles as the Slot Registry (D-07)

**What:** All 9 characters speak at least once [VERIFIED: every one of ROCKY, BLACK FIGHTER, CORNERMAN, FAN, PROMOTER, WOMAN, FIGHTER #1, FIGHTER #2, ANNOUNCER has a non-empty `dialogue` array in at least one beat in `output/beats.json`, confirmed by direct read this session]. The simplest implementation that trivially satisfies D-06 ("must never share a voice with someone they speak to in the same scene") is a **globally unique `voice_id` per character** (9 distinct ids) — if every character's voice_id is unique project-wide, no two characters can ever collide within any single scene, by construction. D-06's requirement that "the registry must enforce distinctness within a scene" is then a cheap assertion (defensive, not load-bearing under this design), useful mainly as a regression guard if a later phase ever pools voices across characters:

```python
# Concrete scenes that co-locate multiple speaking characters
# (verified by direct read of output/beats.json's characters[] per beat, this session):
#   scene 2: ROCKY, BLACK FIGHTER, CORNERMAN, FAN, ANNOUNCER all speak
#   scene 3: ROCKY, FIGHTER #1, FIGHTER #2, PROMOTER all speak
#   scene 4: ROCKY, WOMAN both speak
def assert_no_voice_collisions(beats: list[dict], voice_id_by_character: dict[str, str]) -> None:
    by_scene: dict[int, set[str]] = {}
    for beat in beats:
        for line in beat["dialogue"]:
            by_scene.setdefault(beat["scene"], set()).add(line["character"])
    for scene, speakers in by_scene.items():
        voice_ids = [voice_id_by_character[s] for s in speakers]
        assert len(voice_ids) == len(set(voice_ids)), f"voice collision in scene {scene}: {speakers}"
```

Phase 3's job stops at producing a stable `voice_id` per character (e.g. the normalized character name itself, `"rocky"`, `"black_fighter"`, ...) — mapping `voice_id` to an actual Gemini TTS voice name (Phase 5 smoke-tested `Charon` for one voice; the full available voice palette is a Phase 5 concern) is out of scope here per D-07's "build the key once."

### Pattern: Manifest Entry Shape

**What:** Follow the `Beat.to_dict()` / `beat_assembler._build_beat_list()` precedent exactly: a value plus the machine-readable rule that produced it (NFR-04), applied per slot.

```python
# Following the precedent in src/animatic/core/beat_extractor.py (Beat.to_dict, read this
# session) and src/animatic/core/beat_assembler.py (_build_beat_list, read this session)
@dataclass
class Slot:
    slot_id: str                 # normalized, e.g. "rocky", "blue_door_fight_club"
    slot_type: str                # "character" | "location"
    display_name: str             # e.g. "ROCKY", "BLUE DOOR FIGHT CLUB"
    source_headings: list[str]    # raw scene_headings/character names merged into this slot
    merge_reason: str             # NFR-04: why these were judged the same slot (D-03)
    is_minor: bool | None         # characters only; None for locations
    voice_id: str | None          # characters only (D-07); None for locations
    priority_rank: int            # 1 = highest share of screen time (D-10/D-11)
    beats: int                    # underlying count, so the rank is checkable (D-11)
    duration_secs: float
    share_pct: float
    source: str                   # "reference" | "generated"
    source_file: str | None       # matched reference filename, if any
    art_uri: str                  # local or s3:// path to the resolved active art
    content_hash: str             # sha256 of art_uri's bytes, for Phase 4 cache invalidation
    reason: str                   # NFR-04: why source=reference vs generated, what prompt was used
```

Manifest top level mirrors `_build_beat_list`'s shape (`generated_at`, `script`, then the list), written local-then-S3 exactly like `beat_assembler.assemble_and_write` [VERIFIED: `src/animatic/core/beat_assembler.py:24-36`, read this session].

### Anti-Patterns to Avoid
- **Trusting `beats.json`'s `scene_heading` as ground truth for "has a real slug":** it is already model-invented per-beat text with no provenance flag; re-derive from the PDF via `pdf_extractor.extract_scenes` instead (see pattern above).
- **Negative-only style prompting** ("no shading", "no color", "NO FACIALS"): the smoke test's own artifact shows the model rendering a negation as literal caption text. State style positively.
- **Reusing `beat_assembler`'s swallowed-`ClientError` pattern uncritically:** Phase 2's own verification report flags this as an open warning (`POST /beats/parse` answers 200 even when the S3 write silently failed) [VERIFIED: `.planning/phases/phase-2/2-VERIFICATION.md`, "Anti-Patterns Found" table, `beat_assembler.py:86-88`, read this session]. CONTEXT.md explicitly asks to fold the fix in here if cheap, since this phase writes to the same bucket.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Fuzzy heading matching (near-duplicate slugs after normalization) | A custom string-distance/clustering algorithm | stdlib `difflib.SequenceMatcher` (or exact-match on the normalized key, which is all this 8-scene corpus actually needs) | Zero new dependency; the current corpus needs zero fuzzy matching once D-02+D-03's normalization is applied — every remaining pair either matches exactly after normalization or is a genuinely different place |
| Content-based cache invalidation | A custom mtime/size heuristic | `hashlib.sha256(file_bytes).hexdigest()` | CONTEXT.md's own discretion note picks content hashing explicitly because it is re-runnable and filesystem-timestamp-independent; `hashlib` is stdlib, nothing to hand-roll |
| Image format/corruption validation on uploaded reference art | Manual byte-sniffing of image headers | `PIL.Image.open(...).verify()` | Already installed transitively; don't write a custom magic-byte sniffer for a solved problem |

**Key insight:** Everything Phase 3 actually needs beyond the single AI call (temp-art generation) is a deterministic transform over data already in the repo. Resist the temptation to route slot-identity clustering through an LLM call "for robustness" — it adds cost, latency, and a new failure mode to a problem the stdlib already solves exactly for this fixed corpus.

## Common Pitfalls

### Pitfall 1: `system_instruction` + image-output model raises on the API-key (MLDev) backend
**What goes wrong:** Passing `system_instruction` in `types.GenerateContentConfig` alongside `response_modalities=["IMAGE"]` on a Gemini image-generation model can raise `errors.ClientError` with message `"Developer instruction is not enabled for models/gemini-2.5-flash-image"` when the client is *not* using Vertex AI.
**Why it happens:** Confirmed directly in the installed SDK's own replay-test suite — `test_error_handling_unary` in `google/genai/tests/models/test_generate_content.py` (this exact scenario: image model + `system_instruction` + non-Vertex client) [VERIFIED: local inspection of `google-genai` 2.19.0 package source, `tests/models/test_generate_content.py:2466-2496`, read this session — the test targets `GEMINI_FLASH_IMAGE_LATEST = 'gemini-2.5-flash-image'`, a sibling model in the same "flash-image" family as the project's `gemini-3.1-flash-image`, so the restriction is plausible but not confirmed for the exact model this project uses].
**How to avoid:** Fold the shared style block (D-08) into the prompt **text** content instead of `system_instruction`. This is free — it costs nothing and works on both the legacy `generate_content` and newer `interactions.create` surfaces — so do it regardless of whether the restriction actually applies to `gemini-3.1-flash-image` specifically.
**Warning signs:** A `ClientError` on the very first image call referencing "Developer instruction."

### Pitfall 2: Negative/instructional phrasing gets rendered as literal image text
**What goes wrong:** The smoke test's prompt evidently included short, imperative, caption-like phrasing (something that produced the literal words "NO FACIALS" and a full caption block reading "Panel 3 - Wide Shot. Roxy's Gym, Night. [NAME] waitin'." burned into the frame) [VERIFIED: `output/smoke/panel_test_0.png`, viewed this session — the failure is directly visible: greyscale/heavy shading (not flat black-on-white), spiral-notebook binding chrome, an "EXIT" sign, a captioned label block, and "NO FACIALS" rendered as text in the lower right].
**Why it happens:** Cross-checked across multiple sources: Google's own prompting guidance for this model family recommends **semantic** (positive) framing over blacklist-style exclusions [CITED: Google Cloud Blog, "Ultimate prompting guide for Nano Banana" — "describe what you want, not what you don't want (e.g. 'empty street' instead of 'no cars')"], and the model has no structural way to distinguish "text describing what to draw" from "text meant to appear drawn" except by how the prompt is phrased — a short all-caps imperative phrase or a labeled block reads exactly like a caption to render.
**How to avoid:** State every constraint positively and as prose describing the final image, never as a standalone imperative/caption-shaped fragment. E.g. replace `"NO FACIALS"` with continuous prose: `"...rendered with a smooth, featureless face — no eyes, brows, nose, or mouth are drawn."` Avoid the word "storyboard" specifically — it is the documented trigger for the spiral-notebook/caption chrome in this project's own smoke test (D-09) — describe the desired output format directly instead ("a single flat illustration, no panel border, no binding, no surrounding page").
**Warning signs:** Any generated image containing readable text that wasn't explicitly requested as in-scene signage.

### Pitfall 3: `interactions.create`'s `ImageResponseFormat.mime_type` only accepts `image/jpeg`
**What goes wrong:** If the newer `client.interactions.create(..., response_format={"type": "image", ...})` surface is used and an explicit `mime_type` is set, the SDK's own type definition restricts it to a single literal value.
**Why it happens:** [VERIFIED: local inspection of `google-genai` 2.19.0 package source, `_gaos/types/interactions/imageresponseformat.py:73`, read this session — `ImageResponseFormatMimeType = Literal["image/jpeg",]`, quoted verbatim].
**How to avoid:** Either omit `mime_type` from `response_format` (uses the API default) or explicitly request `"image/jpeg"`; do not assume PNG output is selectable through this parameter on this surface. (The legacy `generate_content` path's `ImageConfig.output_mime_type` is not similarly restricted in the same file, but was only verified for the config *shape*, not the accepted literal set — treat as unconfirmed either way and check the actual response's `mime_type` at runtime rather than assuming.)
**Warning signs:** A `pydantic.ValidationError` on `response_format` construction, or a returned image whose bytes don't match the assumed extension.

### Pitfall 4: `beats.json`'s `scene_heading` is not provenance-tagged
See "Pattern: Slot Resolution — D-02 Inheritance Requires Re-Reading the PDF" above — this is the single most important pitfall in this phase, since silently trusting the field defeats D-02 entirely for exactly the case it exists to fix.

## Code Examples

### Text-to-image with a style block folded into the prompt (recommended primary path)
```python
# Source: pattern confirmed via google-genai 2.19.0 installed SDK test suite,
# tests/models/test_generate_content_image_generation.py and
# tests/models/test_generate_content.py:2440-2489 (multi-part Content with
# image+text parts), read this session. Model id "gemini-3.1-flash-image"
# confirmed present in the SDK's own Model literal enum
# (_gaos/types/interactions/model.py), read this session.
from google import genai
from google.genai import types

client = genai.Client(api_key=settings.google_api_key)

STYLE_BLOCK = (
    "Style: flat black ink linework on a pure white background, like a hand-drawn "
    "storyboard illustration for animation pre-visualization. Uniform, confident line "
    "weight throughout. No shading, no gradients, no cross-hatching, no color, no gray "
    "fills — line only. A single self-contained illustration filling the frame: no "
    "border, no binding, no page texture, no caption text, no labels, no watermark, "
    "nothing outside the drawn subject itself."
)

response = client.models.generate_content(
    model=f"models/{settings.gemini_image_model}",  # e.g. "gemini-3.1-flash-image"
    contents=f"{STYLE_BLOCK}\n\nSubject: {slot_prompt}",
    config=types.GenerateContentConfig(
        response_modalities=["IMAGE"],
        image_config=types.ImageConfig(aspect_ratio="4:3"),
        # Deliberately NOT setting system_instruction here — see Pitfall 1.
    ),
)
for part in response.candidates[0].content.parts:
    if part.inline_data is not None:
        image_bytes = part.inline_data.data
```

### Multi-image reference conditioning (for the one slot — ROCKY — that has supplied reference art)
```python
# Source: google-genai 2.19.0 installed SDK, tests/models/test_generate_content.py:2440-2463
# (types.Content with multiple types.Part entries: image bytes + text), read this session.
reference_parts = [
    types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg")
    for img_bytes in rocky_reference_image_bytes  # up to the 4 files in assets/reference-art/
]
response = client.models.generate_content(
    model=f"models/{settings.gemini_image_model}",
    contents=[
        types.Content(
            role="user",
            parts=[
                *reference_parts,
                types.Part.from_text(
                    text=f"{STYLE_BLOCK}\n\nUsing the attached reference photos for likeness, "
                         f"draw Rocky Balboa in the fight-club scene: {slot_prompt}"
                ),
            ],
        ),
    ],
    config=types.GenerateContentConfig(response_modalities=["IMAGE"]),
)
```

### Reference-file → slot matching (no human alias map, per D-01)
```python
# assets/reference-art/ currently holds 4 flat files, all Rocky-named:
#   rocky_porkpie.jpg, rocky_porkpie2.jpg, rocky_trunks_front.jpg, boxing_poses.jpeg
# [VERIFIED: `ls assets/reference-art/`, this session]
# No slot-keyed directory structure exists yet. A deterministic, alias-map-free match:
def find_reference_files(slot_id: str, reference_dir: Path) -> list[Path]:
    """Match reference-art files to a slot by substring on the normalized slot id.

    No hand-curated alias table (D-01) — matches purely on whether the slot's own
    normalized name appears in the filename. Works today because all 4 supplied
    files are Rocky-named and slot_id for the ROCKY character is "rocky".
    """
    return sorted(
        p for p in reference_dir.glob("*")
        if slot_id.lower() in p.stem.lower()
    )
```

### Content-hash change detection (Claude's Discretion → content hashing)
```python
import hashlib

def content_hash(art_bytes: bytes) -> str:
    return hashlib.sha256(art_bytes).hexdigest()

# Manifest stores this per slot. Phase 4's panel cache keys on (slot_id, content_hash);
# a changed hash on re-run is exactly the signal FR-02 / success criterion 4
# ("replacing a slot file and re-running regenerates the panels that use it") needs —
# but the actual regeneration/invalidation logic is Phase 4's responsibility, not this
# phase's. Phase 3's job ends at recording the hash faithfully in the manifest.
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| Single-shot text-to-image prompting for character consistency | Multi-reference-image conditioning (up to 14 images per call) in Gemini's "Nano Banana 2" (`gemini-3.1-flash-image`) generation | Model released ~Feb 2026 per DeepMind's own model page [CITED: deepmind.google/models/gemini-image/flash/, cross-checked against multiple secondary sources] | Reference-image-based identity anchoring is now a first-class capability, not a workaround — directly usable for the ROCKY slot's 4 supplied images |
| `client.models.generate_content` as the only content-generation surface | A newer `client.interactions.create` surface exists in the same installed SDK version, layered under Speakeasy-generated "GAOS" code, supporting `system_instruction` directly on image models and `previous_interaction_id` for iterative multi-turn edits | Present in `google-genai` 2.19.0 as installed; unclear how long this has existed or how stable it is | Not recommended as the primary path for this deadline — flagged as an option, not a default, given it's unverified against this project's own working smoke test |

**Deprecated/outdated:** Nothing in this stack is deprecated; `google-genai`'s legacy `generate_content` surface remains fully supported and is what `beat_extractor.py` already uses successfully for text.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The `system_instruction` + image-model `ClientError` restriction found for `gemini-2.5-flash-image` in the SDK's own tests also applies to `gemini-3.1-flash-image` | Common Pitfalls > Pitfall 1 | Low — the recommended mitigation (style block in prompt text) is free and works either way, so this assumption doesn't gate a decision, only explains a defensive choice |
| A2 | `gemini-3.1-flash-image` supports the same `contents=[Content(parts=[image, image, ..., text])]` multi-image-input pattern confirmed for `gemini-2.5-flash-image` in the SDK's tests | Code Examples > Multi-image reference conditioning | Medium — if the exact model doesn't accept multiple reference images the same way, Rocky's reference-conditioned generation would need to fall back to single-image conditioning or the newer `interactions.create` surface; recommend a quick real-key smoke test before committing to this pattern in the plan |
| A3 | The original smoke-test script that produced `output/smoke/panel_test_0.png` used `client.models.generate_content` (not `interactions.create`) | Summary, Code Examples | Low-medium — the script no longer exists in the repo or git history [VERIFIED: `git log --all` search for "smoke"/"panel_test" turned up no matching file, this session], so the exact original call is genuinely unknown; the recommended pattern is the best-supported reconstruction from the installed SDK's own test suite, not a replay of what actually produced the 697 KB image STATE.md references |
| A4 | One shared generic art slot (not per-archetype) is sufficient for the 4 minor characters under D-05 | Pattern: Character Priority and Minor-Character Classification | Low — explicitly framed as a "first pass, cheap to upgrade" recommendation, consistent with the project's own "ship a best first pass" standing preference |
| A5 | Merging `EXT. ROCKY'S APARTMENT` and `INT. ROCKY'S APARTMENT` into one location slot (a mechanical consequence of D-03 as written) is acceptable, rather than something D-03 should special-case | Pattern: D-02/D-03 Applied to the Actual Beat List | Medium — if the planner decides INT./EXT. pairs should stay separate slots, the normalization step needs an explicit carve-out preserving the INT./EXT. token for clustering purposes while still discarding it for the SUPERIMPOSE-inheritance case; flagged explicitly above for a decision, not silently resolved |

**If this table is empty:** N/A — see entries above.

## Open Questions

1. **Does the planner want 15 total slots (9 characters + 6 locations) or should D-03's normalization special-case INT./EXT. pairs to preserve 7 locations?**
   - What we know: the locked rules as written produce 6 location slots when run against the actual current beat list (see A5).
   - What's unclear: whether the CONTEXT.md discussion anticipated this collapse or assumed each of the 8 raw headings besides the SUPERIMPOSE case would stay distinct.
   - Recommendation: surface this in `/gsd-plan-phase` before locking the plan's task list — it changes both the total slot count in every success-criterion check and the manifest fixture the tests will pin.

2. **What exact call produced the working `output/smoke/panel_test_0.png` (697 KB, `gemini-3.1-flash-image`, no allowlist gating per STATE.md)?**
   - What we know: it worked, used `GOOGLE_API_KEY`, and produced a real (if stylistically wrong) image.
   - What's unclear: the exact SDK call surface and parameters — the script isn't in the repo or git history.
   - Recommendation: the first task in Phase 3's plan should be a small, disposable spike script re-proving the call against a real key, before the slot-resolution/manifest code is wired to depend on its exact shape. This also naturally produces the corrected-prompt smoke evidence needed to confirm D-09 is actually satisfied.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `google-genai` | Temp-art generation calls | ✓ | 2.19.0 (installed; `requirements.txt` floor `>=0.8`) | — |
| `GOOGLE_API_KEY` | Authenticating the above | ✓ (per STATE.md's 2026-08-24 smoke test — image, TTS, and Veo calls all succeeded, no allowlist gating) | — | — |
| `boto3` + AWS credentials (`newaccount` profile / ECS task role) | S3 dual-write of manifest | ✓ (already used by `beat_assembler.py`) | `>=1.34` | Local-only write if S3 fails — but see Anti-Pattern above: `beat_assembler`'s current fallback silently returns 200, a known open bug worth fixing here |
| `Pillow` | Optional reference-art validation | ✓ (installed transitively) | 12.3.0 | Skip validation, hash raw bytes directly — `hashlib` needs no image library |

**Missing dependencies with no fallback:** none.
**Missing dependencies with fallback:** none — everything this phase needs is already present in the project's own `.venv`.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x + pytest-asyncio [VERIFIED: `requirements-dev.txt`, read this session] |
| Config file | none dedicated — `tests/` discovered by pytest's default rootdir convention (existing `tests/test_beat_parser.py` follows this) |
| Quick run command | `pytest tests/test_asset_manifest.py -x` |
| Full suite command | `pytest tests/ -x` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| FR-02 | Slot resolution deduplicates scene 2 into scene 1 (D-02) | unit | `pytest tests/test_asset_manifest.py::test_scene_2_inherits_scene_1_location -x` | ❌ Wave 0 |
| FR-02 | Every character/location in beats.json resolves to exactly one slot | unit | `pytest tests/test_asset_manifest.py::test_every_beat_entity_resolves_to_one_slot -x` | ❌ Wave 0 |
| FR-02 | Zero reference art still produces a complete manifest (temp-art fallback) | integration (mock genai client, follow `test_extract_beats_returns_beats`'s `@patch` pattern) | `pytest tests/test_asset_manifest.py::test_manifest_complete_with_no_reference_art -x` | ❌ Wave 0 |
| FR-02 | Reference art takes priority over generated art when present | unit | `pytest tests/test_asset_manifest.py::test_reference_art_takes_priority -x` | ❌ Wave 0 |
| FR-02 | Manifest entries carry slot name, priority, source, reason | unit | `pytest tests/test_asset_manifest.py::test_manifest_entry_shape -x` | ❌ Wave 0 |
| FR-02 | Content hash changes when a slot file is replaced | unit | `pytest tests/test_asset_manifest.py::test_content_hash_changes_on_file_replace -x` | ❌ Wave 0 |
| NFR-04 | Every slot's `reason` field is non-empty and machine-readable | unit | `pytest tests/test_asset_manifest.py::test_all_slots_have_nonempty_reason -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_asset_manifest.py -x`
- **Per wave merge:** `pytest tests/ -x`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_asset_manifest.py` — new file, covers all FR-02/NFR-04 rows above
- [ ] Mock fixture for `client.models.generate_content` image responses, following the existing `@patch("animatic.core.beat_extractor.genai.Client")` pattern in `tests/test_beat_parser.py` [VERIFIED: `tests/test_beat_parser.py` function names `test_extract_beats_returns_beats(mock_client_cls)` etc., read this session]
- [ ] No new pytest config needed — existing rootdir discovery covers a new file under `tests/`

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | No new auth surface in this phase |
| V3 Session Management | no | No new session surface in this phase |
| V4 Access Control | no | No new access-control surface; S3 bucket policy already established in Phase 1 |
| V5 Input Validation | yes | Reference-art filenames under `assets/reference-art/` should be treated as local, trusted (developer-supplied) input for the demo's fixed-content scope — but if this code path is ever reachable from an uploaded file (not true today per PROJECT.md's "No user-supplied script upload"), validate with `PIL.Image.open(...).verify()` before hashing/using, and never build a filesystem path by concatenating an unsanitized filename (use `Path.name` / basename only, reject path separators) |
| V6 Cryptography | no (hashing here is content-addressing, not a security control) | `hashlib.sha256` is used for change detection, not for any secret or integrity guarantee — no crypto requirement beyond "produces a stable digest" |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Path traversal via a crafted reference-art filename (e.g. `../../etc/passwd`) | Tampering | Use `Path(filename).name` only when constructing any write path; never join a raw user-controlled filename directly (not currently reachable from untrusted input given the fixed-content demo, but cheap to do correctly from the start) |
| Decompression-bomb / oversized image file exhausting memory during hashing or `PIL` validation | Denial of Service | Stream-hash in chunks (`hashlib.sha256()` + `.update()` in a read loop) rather than loading the whole file into memory at once if reference art size is ever attacker-influenced; not a practical risk for the fixed demo's small local files, but cheap to do correctly |
| Prompt injection via scene/character text flowing into the image-generation prompt (script content is fixed/trusted today, but the pattern generalizes) | Tampering | Not a live risk in this phase — script content is a fixed, developer-supplied PDF (PROJECT.md: "No user-supplied script upload"), not third-party or user-supplied text |

## Sources

### Primary (HIGH confidence — direct source inspection this session)
- `google-genai` 2.19.0 installed package source (`.venv/lib/python3.14/site-packages/google/genai/`) — `types.py`, `interactions.py`, `_gaos/types/interactions/*.py`, `_gaos/google_genai.py`, `tests/models/test_generate_content.py`, `tests/models/test_generate_content_image_generation.py`, `tests/models/test_edit_image.py`, `tests/models/test_recontext_image.py`
- `output/beats.json` — full beat list, read and aggregated this session
- `output/smoke/panel_test_0.png` — viewed directly this session
- `src/animatic/core/beat_extractor.py`, `beat_assembler.py`, `pdf_extractor.py`, `scene_timing.py`, `config.py`, `api/beats.py` — all read this session
- `.planning/phases/phase-2/2-VERIFICATION.md` — read this session, quoted verbatim for the scene-2 raw heading text and the `beat_assembler.py` open-bug finding
- `.planning/phases/phase-3/03-CONTEXT.md`, `.planning/ROADMAP.md`, `.planning/REQUIREMENTS.md`, `.planning/PROJECT.md`, `.planning/STATE.md`, `.planning/config.json` — all read this session

### Secondary (MEDIUM confidence — WebSearch/WebFetch cross-checked)
- Google Cloud Blog, "Ultimate prompting guide for Nano Banana" (cloud.google.com/blog/products/ai-machine-learning/ultimate-prompting-guide-for-nano-banana) — positive-framing prompting guidance, reference-image consistency formula
- Google DeepMind model pages for Gemini 3.1 Flash Image ("Nano Banana 2") — deepmind.google/models/gemini-image/flash/
- ai.google.dev/gemini-api/docs/image-generation — model IDs, up-to-14-reference-images capability, `client.interactions.create` code shape (cross-checked against installed SDK source, confirmed accurate)

### Tertiary (LOW confidence — WebSearch only, not independently confirmed against an official source)
- Secondary blog/aggregator commentary on Nano Banana 2 capabilities (replicate.com, mindstudio.ai, getimg.ai, mcplato.com, atlabs.ai) — used only to corroborate the reference-image-count claim already found in a Google-first-party source, not relied on alone for anything load-bearing

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — `google-genai` version, model ID literal, and call shapes all confirmed via direct installed-package source inspection, not training memory
- Architecture (slot resolution, manifest shape): HIGH — computed directly from the actual `output/beats.json` this session, not estimated
- Architecture (image generation call): MEDIUM — call shapes are SDK-source-verified, but the exact call that produced the working smoke test is unrecoverable, so the recommendation is a well-supported reconstruction, not a confirmed replay
- Pitfalls: MEDIUM-HIGH — the `system_instruction` restriction and `ImageResponseFormat.mime_type` restriction are directly quoted from SDK source; the "storyboard"/negative-phrasing diagnosis is a reasonable inference from the visible smoke-test artifact cross-checked against Google's own published prompting guidance, not a confirmed root-cause from Google

**Research date:** 2026-08-24
**Valid until:** ~7 days (fast-moving: `gemini-3.1-flash-image` and the `interactions` API surface are recent/preview-adjacent per the SDK's own file headers dated 2026; re-verify against a real key before the plan locks in exact call parameters)
</content>
