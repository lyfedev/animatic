# Phase 4: Panel Generation - Research

**Researched:** 2026-08-25
**Domain:** Text-to-image generation (Gemini image model) driving a cached, per-beat panel pipeline
**Confidence:** HIGH for caching/mapping/manifest design (derived directly from Phase 3's own shipped code); MEDIUM for prompt phrasing (extends a proven in-repo pattern to a new case, not yet run against the live API); LOW/ASSUMED for exact API rate limits (could not be checked without an authenticated AI Studio session)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### Shot size
- **D-01:** Shot size is **derived deterministically from beat type**, no model call:
  `establishing → wide`, `action → medium`, `dialogue → close-up`. Free, testable,
  predictable across 49 beats, and it produces defensible grammar — the fight plays in
  wides and mediums, exchanges play close.
- **D-02:** Shot size is a **derived field computed alongside beats, never written back
  into the beat list.** Beats stand as initially rendered (roadmap S-02 decision); adding
  a field to them would contradict that and invalidate the Phase 3 manifest's hashes.
- **D-03:** **Rejected: generate at one framing and crop in.** The user offered it as a
  cheaper path and it is a reasonable instinct, but it fails on the one rule it has to
  serve. A close-up is the shot size that needs MORE face detail (brow, mouth, nose), so
  cropping into a featureless panel yields a blank face at high magnification, plus
  upscaling artifacts on line art. We already make one call per beat; the shot size costs
  nothing extra inside that call.
  — **Reversibility:** reversible — a prompt clause and a mapping table.
- **D-04:** Every panel records its shot size AND the rule that assigned it, following the
  `duration_source` precedent from Phase 2 (NFR-04).

#### Facial features (PROJECT.md, non-negotiable)
- **D-05:** The facial rule is keyed off shot size: wide and medium carry **no** facial
  features; close-ups carry **brow line, mouth line and nose only** — never eyes, never
  full rendering.
- **D-06:** State it positively, never as a negation, and place it LAST in the prompt.
  This is the hardest-won lesson of Phase 3 and it cost several regenerations to learn:
  negations get rendered as literal text ("NO FACIALS" was painted into a frame), and a
  rule stated mid-prompt loses to whatever follows it. Both the character-isolation fix
  and the empty-room fix came down to moving the rule to the end.
- **D-07:** Name no object that is not wanted in the picture. The blank-face wording
  bounded the face by "the hairline, hat brim and jaw contour" and put a hat on every
  character in the film, including a boxer in trunks. `tests/test_style.py` guards the
  character prompt against headwear and garment nouns; the panel prompt needs the same
  guard.

#### Reference conditioning
- **D-08:** **HELD — not used in Phase 4.** Multi-image conditioning was spiked and works
  (`output/experiments/refcond_panel.jpg`: the black_fighter plate plus the fight-club
  plate returned one composed panel keeping both). The capability is proven and S-03's
  risk is closed, but the user has explicitly held it out of this phase. Panels generate
  from text — the beat, the shot size, and the slot descriptions from the Phase 3 manifest.
  — **Reversibility:** reversible — an additional `contents` part on the call.

#### Iteration strategy
- **D-09:** **Tracer scene, then the rest.** Generate scene 2's panels first — the fight,
  19 beats, the highest-value and highest-density scene — and put them in front of the user
  before generating the other 30. Phase 3 needed several rounds of looking at pictures to
  find output that was subtly wrong; catching a systemic prompt defect on 19 panels rather
  than 49 is the point.
- **D-10:** Budget context: generation runs ~10s per image, so a full 49-panel run is
  roughly 8-9 minutes. Caching (criterion 5) means a re-run after a fix only regenerates
  what changed.

#### Known carry-forwards from Phase 3
- **D-11:** `promoter` reads as a modern staffer with a clipboard and lanyard, because
  scene 3's beats describe a dressing room and never mention the sport. Thin scene context
  is a live failure mode for any character whose scenes do not describe their world. It
  affects panels the same way it affected slots.
- **D-12:** Text still leaks onto LOCATION art occasionally (a "BOX'S GYM" sign appeared
  once). The Phase 3 guard covers character prompts only. Panels render rooms, so they
  inherit this risk.

### Claude's Discretion
- Panel storage layout, naming, and manifest/index format.
- Cache key composition — must at minimum cover beat content, shot size, and the slot
  art each panel depends on, so Phase 3's `stale_beat_ids` signal actually drives redraws
  (this is what closes ROADMAP criterion 4 from Phase 3).
- Whether panels are written to S3 per-panel or batched.

### Deferred Ideas (OUT OF SCOPE)
- Reference-image conditioning for panels (proven working, held by the user — D-08).
- S-01 slot description override, S-02 beat stretch — Phase 9 backlog.
- Fixing `promoter`'s thin context at the slot level — carried as D-11, not this phase's goal.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| FR-03 | Generate black line-art panels on white for each beat; no facial features in wide/medium; close-ups: brow line, mouth line, nose only; consistent line weight and style; every panel carries a machine-readable reason | Architecture Patterns §1-4, Common Pitfalls §1-2, Code Examples — reuse of `STYLE_BLOCK` for consistency, new close-up facial clause draft, NFR-04 reason fields designed into the panel index |
| NFR-03 | Google Cloud SDK only for AI (`google-genai`, etc.), no other AI APIs | Standard Stack, Package Legitimacy Audit — confirms `google-genai` 2.19.0 already installed and live-tested; no new packages needed; D-08 (reference conditioning) explicitly not built, keeping the call shape identical to Phase 3's proven one |
| NFR-04 | Every generated artifact carries a machine-readable reason field | Architecture Patterns §1 (cache_key + reason), Validation Architecture (test map row for NFR-04), Security Domain (S3 write honesty reused from `s3_writer.py`) |
</phase_requirements>

## Summary

Phase 4 has almost no new architecture to invent — Phase 3 already built every mechanism this
phase needs one level down (slot resolution, change detection, honest S3 writes, the shared
style block, the "positive prose, rule last" prompting discipline). The job is to run that same
machinery once per **beat** instead of once per **slot**, with three new pieces: (1) a
deterministic shot-size function (D-01, pure code, no research needed), (2) a panel prompt
builder that reuses `style.describe_slot`/`style.character_context` for grounding but adds a
new close-up facial clause that names brow/mouth/nose as present while eyes stay part of the
blank plane — the inverse of what `asset_generator._subject_note` already does for full
suppression, and it needs the same "positive prose, named last" discipline that took two
regeneration passes to get right in Phase 3, and (3) a panel index (`output/panels/index.json`)
shaped like `assets/manifest.json`, keyed for cache reuse on a self-computed beat hash plus the
current `content_hash` of every slot the beat depends on.

The one piece of genuine investigation was Gemini's Batch API: it **does** support image output
models including `gemini-3.1-flash-image`, at 50% of interactive pricing, but its documented
target is a 24-hour turnaround SLA — wrong tool for a phase whose own budget (D-10) is ~9 minutes
end to end. Recommendation: synchronous `generate_content` calls, one per beat (or per distinct
prompt, since a shared minor-character prompt could in principle be reused across beats the way
`asset_generator` shares one image across four minor-character slots — but panels are per-beat,
not per-slot, so no such sharing exists here), with the exact same failure-isolation pattern
`asset_generator.generate_missing_art` already uses: catch, record a machine-readable reason,
continue the run.

**Primary recommendation:** Build `src/animatic/core/panel_generator.py` and
`src/animatic/core/panel_manifest.py` as direct siblings of `asset_generator.py` /
`asset_manifest.py`, reusing `style.py` and `s3_writer.put_bytes` unchanged, with a new
`panel_prompt.py` (or a `panel_style.py` addition) that adds the close-up facial clause. Do not
reintroduce reference-image conditioning (D-08 HELD) — panels are text-only this phase.

**Before any of this can be planned as "read the manifest and go":** the manifest currently on
disk (`output/assets/manifest.json`, and the copy in S3) is **not** the 16-slot registry Phase 3
shipped — see Pitfall 0 below. A full, non-`--only` run of `scripts/build_assets.py` must
precede Phase 4 execution.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Shot-size derivation (D-01) | Backend/core (pure Python) | — | Deterministic lookup from `beat.type`; no model call, no I/O |
| Beat→slot resolution (location + characters) | Backend/core | — | Pure function over `beats.json` + `manifest.json`, already the pattern `slot_resolver.py` establishes |
| Panel image generation | Backend/core → Google GenAI API | — | One `generate_content` call per beat, same shape as `asset_generator.generate_slot_art` |
| Cache/staleness detection | Backend/core | — | Content-hash comparison against the Phase 3 manifest, computed at panel-build time, not trusted from Phase 3's own `stale_beat_ids` (see Research Q1) |
| Panel + index persistence | Backend/core | S3 (Storage) | Local-then-S3 dual write, following `asset_manifest.write_manifest`/`write_slot_art` exactly |
| Panel index consumption | Phase 7 (Video Assembly) | — | Reads `output/panels/index.json` in beat order for duration + path; out of scope this phase but the index contract is set here |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `google-genai` | 2.19.0 (installed, `pip show google-genai` — [VERIFIED: local venv]) | Image generation via `client.models.generate_content` | Already the only AI SDK in the project (NFR-03); `requirements.txt` pins `>=0.8`, actual installed is 2.19.0 |
| `boto3` | already installed, used via `s3_writer.put_bytes` | S3 writes for panels + index | Reuse — `s3_writer` is already "the one place in the codebase that talks to boto3" per its own docstring [VERIFIED: src/animatic/core/s3_writer.py] |
| stdlib `hashlib` | 3.14 stdlib | Beat-content hashing for the cache key | Already the mechanism `asset_manifest.py` uses for `content_hash` (`hashlib.sha256(image_bytes).hexdigest()` at asset_manifest.py:186 area) |
| stdlib `json` | stdlib | Index/manifest read-write | Matches every existing manifest module |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| stdlib `concurrent.futures.ThreadPoolExecutor` | stdlib | Optional bounded concurrency across the 49 image calls | Only if sequential ~9 min (D-10) proves too slow in practice; keep default sequential since it's the number D-10 already budgeted and rate limits are unverified (see Pitfall 3) |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Synchronous per-beat `generate_content` | `client.batches.create(...)` (Batch API) | Batch supports image output and is 50% cheaper, but its documented SLA is "designed to complete within a 24-hour turnaround" [CITED: ai.google.dev/gemini-api/docs/batch-api] — incompatible with a live/demo pipeline and with D-10's ~9-minute budget. Rejected for this phase; could revisit for a non-interactive nightly pre-render in a later phase. |
| Panel generation from beat text | Reference-image-conditioned panel generation | Proven (`output/experiments/refcond_panel.jpg`) and higher-fidelity, but explicitly HELD by the user (D-08). Do not build. |

**Installation:** No new packages required. `google-genai`, `boto3`, `pdfplumber` are already
in `requirements.txt` and already exercised by live API calls in Phase 3
(`output/assets/generated/*.jpg`, 13 real files).

**Version verification:**
```
$ pip show google-genai
Version: 2.19.0
```
[VERIFIED: local venv, `pip show google-genai` run this session] — `requirements.txt`'s
`google-genai>=0.8` pin is satisfied; no action needed for this phase.

## Package Legitimacy Audit

**Not applicable — this phase installs no new external packages.** Every dependency Phase 4
needs (`google-genai`, `boto3`, stdlib `hashlib`/`json`/`concurrent.futures`) is already
installed and already proven against the live API in Phase 3 (`output/assets/generated/`, 13
real generated files; `STATE.md`'s Google AI Access smoke test table).

**Packages removed due to [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

## Architecture Patterns

### System Architecture Diagram

```
output/beats.json (49 beats)          output/assets/manifest.json (16 slots)
        │                                        │
        │  (re-resolve slots — pure fn,          │  (read: content_hash,
        │   no API calls; same fn Phase 3         │   art_slot_id, source
        │   already uses)                         │   metadata per slot)
        ▼                                        │
  slot_resolver.resolve_slots(beats, pdf)         │
        │                                        │
        └──────────────┬─────────────────────────┘
                        ▼
              panel_generator: for each beat (in beat_id order)
                        │
          ┌─────────────┼──────────────────────────┐
          ▼             ▼                           ▼
   derive shot_size  resolve location slot   resolve character slot(s)
   (D-01, pure fn,   (scene ∈ slot.source_    (slugify(name) per beat.
    from beat.type)   scenes, slot_type==      characters, lookup in
                       "location")              resolved slots)
          │             │                           │
          └─────────────┴──────────┬────────────────┘
                                    ▼
                    compute cache key = sha256(
                      beat content fields + shot_size +
                      sorted (slot_id, content_hash) pairs +
                      prompt_template_version)
                                    │
                     ┌──────────────┴───────────────┐
                     ▼                               ▼
         cache HIT: reuse existing            cache MISS: build prompt
         panel file, record reason            (STYLE_BLOCK + location/
         "unchanged since prior run"          character grounding +
                     │                          shot-size clause +
                     │                          facial-rule clause LAST)
                     │                               │
                     │                    generate_content(model=...,
                     │                      contents=prompt,
                     │                      config=GenerateContentConfig(
                     │                        response_modalities=["IMAGE"],
                     │                        image_config=ImageConfig(
                     │                          aspect_ratio="16:9")))
                     │                               │
                     │                    on success: write panel bytes
                     │                      local + S3 (per-panel, not
                     │                      batched — see Pitfall 4)
                     │                    on failure: catch, log reason,
                     │                      continue to next beat
                     └──────────────┬───────────────┘
                                    ▼
                  panel entry appended to output/panels/index.json
                  (beat_id, scene, shot_size + reason, facial_features +
                   reason, asset_slots_used, prompt, panel_uri, panel_s3_uri,
                   content_hash, cache_key, source, source_reason,
                   duration_secs — copied from the beat, for Phase 7)
                                    │
                                    ▼
                  write_manifest-style local-then-S3 dual write
                  (output/panels/index.json, s3://.../panels/index.json)
                                    │
                                    ▼
                     Phase 7 (out of scope): reads index in beat
                     order, cuts each panel for its duration_secs
```

### Recommended Project Structure
```
src/animatic/core/
├── panel_prompt.py       # shot-size derivation (D-01), close-up facial clause,
│                         #   panel subject-note builder (parallels asset_generator._subject_note)
├── panel_generator.py    # generate_panel(beat, prompt) -> (bytes, mime_type); one call per beat;
│                         #   generate_missing_panels(beats, slots, manifest, previous_index, force)
│                         #   -- mirrors asset_generator.generate_missing_art's loop/try-except shape
└── panel_manifest.py     # build_index(), write_index(), write_panel() -- mirrors asset_manifest.py

scripts/
└── build_panels.py       # CLI mirroring scripts/build_assets.py's Step 1/4..4/4 structure,
                          #   with a --scene flag for D-09's tracer-scene-first iteration

tests/
└── test_panel_generator.py  # mirrors tests/test_asset_manifest.py's mock-Client / mock-Session pattern
```

### Pattern 1: Cache key = self-computed beat hash + shot size + dependent slot hashes
**What:** Because `beats.json` carries **no per-beat hash field** — verified directly:
```json
{
  "beat_id": "s1b1", "scene": 1, "beat": 1,
  "scene_heading": "INT. BLUE DOOR FIGHT CLUB - NIGHT",
  "type": "establishing",
  "content": "Establishing shot of the dark, tense interior of the Blue Door Fight Club at night.",
  "duration_secs": 2.2, "duration_source": "page_budget", "motion_candidate": false,
  "reason": "...", "characters": [], "dialogue": [], "spoken_words": 0,
  "min_speakable_secs": 0.0
}
```
[VERIFIED: output/beats.json, `s1b1` entry, read this session — no `hash`/`content_hash` key
present in the beat object] — Phase 4 must compute its own hash of the beat fields that affect
the picture (`type`, `content`, `characters`, `scene`; NOT `reason` or `duration_secs`, which
don't change what's drawn) and combine it with (a) the derived `shot_size` and (b) every
dependent slot's **current** `content_hash` read fresh from `output/assets/manifest.json` at
build time.

**When to use:** Every panel's cache-hit/miss decision.

**Why not just trust Phase 3's `stale_beat_ids`:** `asset_manifest.py`'s own docstring states the
design intent plainly:
> "`content_hash` was chosen over mtime because it is re-runnable and does not depend on
> filesystem timestamps." [VERIFIED: src/animatic/core/asset_manifest.py, module docstring]

`stale_beat_ids` is computed **once, at Phase-3-manifest-build time**, relative to whatever the
*previous* manifest was at that moment — it is not guaranteed to still describe "what changed
since Phase 4 last ran," because Phase 4 and Phase 3 run on independent schedules (a user can
regenerate slot art without touching Phase 4, then run Phase 4 later; `stale_beat_ids` from that
manifest is a valid signal at that instant, but Phase 4 has no guarantee it read the manifest at
that instant vs. three manifest-writes later). The robust, self-contained design mirrors
`asset_manifest._detect_changes`'s own approach one layer up: **Phase 4 keeps its own record**
(in `output/panels/index.json`) of which `(slot_id, content_hash)` pairs each panel was built
from, and compares that record against the *current* manifest on every run — exactly the
`content_hash`-not-mtime, re-runnable-not-order-dependent principle the codebase already commits
to.

```python
# Source: pattern, not yet implemented — reasoning from asset_manifest.py's own docstring
def panel_cache_key(beat: dict, shot_size: str, dependent_slots: list[dict],
                     prompt_template_version: str) -> str:
    payload = {
        "beat_id": beat["beat_id"],
        "type": beat["type"],
        "content": beat["content"],
        "characters": sorted(beat.get("characters", [])),
        "scene": beat["scene"],
        "shot_size": shot_size,
        "slot_hashes": sorted(
            (s["slot_id"], s["content_hash"]) for s in dependent_slots
        ),
        "prompt_template_version": prompt_template_version,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode("utf-8")
    ).hexdigest()
```

**Why include slot `content_hash` even though panels don't consume the image bytes this
phase (D-08 HELD):** ROADMAP Phase 3 criterion 4 — "Replacing a slot file and re-running
regenerates the panels that use it" — and FR-02's identical wording are asserted as **closed by
this phase** per CONTEXT.md line 27 ("Phase 3's criterion 4 ... is CLOSED BY THIS PHASE") and
Claude's Discretion explicitly requires the cache key to "at minimum cover beat content, shot
size, and the slot art each panel depends on" (04-CONTEXT.md, Claude's Discretion). Even though
Phase 4's own generation call is text-only, the caching contract is defined at the requirement
level, not at the "does this specific call consume the bytes" level — a human replacing a
slot's reference art is a signal of updated intent for that slot's dependent panels regardless
of which phase currently reads the pixels.

**Why also version the prompt template:** Phase 3's actual regression history is the strongest
evidence for this: the *same* beat content and the *same* slot art produced a passing vs. failing
image purely because `asset_generator._subject_note`'s wording changed
(`03-ART-REVIEW.md`: "Rewrote to name the specific interior linework that must not appear...").
Neither the beat hash nor the slot content_hash would catch a Phase-4-internal prompt-wording
fix the way Phase 3's fix required a `--force` regeneration. A `PROMPT_TEMPLATE_VERSION`
constant, bumped by hand whenever `panel_prompt.py` changes, makes that regeneration automatic
on the next run instead of requiring a manual `--force`.

### Pattern 2: Beat → slot resolution
**What:** No new resolution mechanism is needed — `slot_resolver.resolve_slots(beats, pdf_path)`
already returns every location slot's `source_scenes` (list of scene numbers) and every
character slot's `slot_id` (via the identical `_slugify` normalization beats' character names
already use). Verified directly:
```python
>>> from animatic.core.slot_resolver import _slugify
>>> _slugify("FIGHTER #1"), _slugify("BLACK FIGHTER"), _slugify("WOMAN")
('fighter_1', 'black_fighter', 'woman')
```
[VERIFIED: src/animatic/core/slot_resolver.py, ran `_slugify` directly this session against
real beat character names read from output/beats.json] — and cross-checked against the actual
character name set present in `beats.json`:
`['ANNOUNCER', 'BLACK FIGHTER', 'CORNERMAN', 'FAN', 'FIGHTER #1', 'FIGHTER #2', 'PROMOTER',
'ROCKY', 'WOMAN']` [VERIFIED: output/beats.json, aggregated `characters[]` + `dialogue[].character`
across all 49 beats, read this session].

**Resolution algorithm per beat:**
```python
# Source: pattern derived from slot_resolver.py's own field contract, not yet implemented
def location_slot_for(beat: dict, location_slots: list[Slot]) -> Slot:
    matches = [s for s in location_slots if beat["scene"] in s.source_scenes]
    assert len(matches) == 1, f"beat {beat['beat_id']} scene {beat['scene']} matched {len(matches)} location slots"
    return matches[0]

def character_slots_for(beat: dict, character_slots_by_id: dict[str, Slot]) -> list[Slot]:
    names = dict.fromkeys(beat.get("characters", []))  # beat.characters already the full cast for the beat
    return [character_slots_by_id[_slugify(name)] for name in names]
```

**Minor characters (D-05's shared art slot) keep distinct identity in this resolution:**
`FIGHTER #1` and `FIGHTER #2` slugify to two *different* slot_ids (`fighter_1`, `fighter_2`),
each with its own `beat_ids`/`voice_id`/`display_name` in the manifest, even though both share
`art_slot_id="generic_minor_character"`. A panel referencing `FIGHTER #1` should record
`asset_slots_used: ["fighter_1", ...]` (the character's own identity slot_id), not the shared
`art_slot_id` — this preserves NFR-04 traceability (which specific character was in this panel)
even though the *art* they'd be drawn from, if D-08 were ever un-held, would be shared.

**Dialogue beats are single-speaker by construction:** every one of the 18 dialogue beats in
the live corpus has exactly one entry in both `characters` and `dialogue`
[VERIFIED: output/beats.json, `Counter(len(b['characters']) for b in dialogue_beats)` = `{1: 18}`,
computed this session] — confirming STATE.md's "one beat per speaker turn" claim
(`_split_speaker_turns`) at the data level. This means a close-up panel's subject is always
unambiguous: the one character in that beat's `characters` list.

### Pattern 3: Panel prompt composition — reuse Phase 3's grounding, add a new facial clause
**What:** Reuse `style.STYLE_BLOCK` verbatim (D-08 of Phase 3: "panels import the same constant
so panels and slot art do not visually drift apart"). For location grounding, reuse
`style.describe_slot(location_slot, beats)` — it already strips on-screen text and quoted
lettering (the D-12 leak risk). For character wardrobe/world grounding, reuse
`style.character_context(char_slot, all_slots, beats)`. The **new** piece is the close-up
facial clause — Phase 3 has no analog because slot-art characters are always fully
face-suppressed; panels need a close-up variant that shows exactly three lines.

**The proven wording pattern to extend (not to copy verbatim — it suppresses everything;
close-ups need to suppress only eyes):**
```python
# Source: src/animatic/core/asset_generator.py, _subject_note(), the wording that passed
# 03-ART-REVIEW.md's second pass after the D-09 fix — VERIFIED, quoted exactly:
"Where the face sits, the outline traces one continuous blank plane bounded only by the "
"hairline and jaw contour — as bare and unmarked as the open background itself, with no "
"eyebrow, eye, nose or mouth line interrupting that plane anywhere."
```
[VERIFIED: src/animatic/core/asset_generator.py, `_subject_note`, minor-character branch —
this exact sentence is what `03-ART-REVIEW.md`'s second pass confirmed PASS on all 8 re-sampled
character slots]

**Recommended close-up variant (draft — not yet run against the live API, tag: [ASSUMED],
must be validated on the D-09 tracer scene before trusting it for all 49 beats):**
```python
# Draft — apply the same rules the working sentence above follows: positive prose,
# no bare negation opening a sentence, placed LAST in the prompt (D-06).
"Where the face sits, the outline draws three simple lines: a brow line above the eyes, "
"a single mouth line, and a short nose line down the center of the face. The eyes "
"themselves stay part of the same blank plane as the rest of the face, unmarked and "
"undrawn, carrying no iris, pupil, eyelid or eyebrow-arch line anywhere in that space."
```
Two design choices carried over deliberately from the Phase 3 lessons:
1. **No headwear/garment nouns** (D-07) — this draft names only `brow`, `eyes`, `mouth`, `nose`,
   `iris`, `pupil`, `eyelid`, none of which are objects that get drawn onto the frame the way
   `hat`/`scarf`/`collar` did. `tests/test_style.py::test_character_prompt_names_no_headwear_or_garment`
   is the exact guard pattern to extend to this new clause (add a
   `test_closeup_prompt_names_no_headwear_or_garment` in the same style, asserting on the built
   string).
2. **Positive statement of what appears, negative statement of what doesn't, in one sentence,
   placed last** — matches D-06 exactly ("state it positively... place it LAST").

**Why this needs live validation and can't be shipped on reasoning alone:** Phase 3's own
history is the reason — the *first* pass of the analogous full-suppression wording
("The head is a smooth, unbroken white shape... with hair, hat and jaw described by the same
outline work") **failed** on `black_fighter` and `generic_minor_character` even though it reads
as reasonable prose; it took naming the specific interior linework explicitly, plus one
`--force` regeneration pass, to pass (`03-ART-REVIEW.md`). A partial-suppression clause (show
3 of 4 features, suppress only the 4th) is a strictly harder case than full suppression and has
no precedent in this project yet. Treat the draft above as a first-pass hypothesis; D-09's
tracer-scene-first strategy (scene 2, 19 beats, before the other 30) is specifically the
mechanism for catching a systemic defect in this clause cheaply.

**Character presence in wide/medium (non-close-up) panels:** unlike slot-art character
isolation portraits (always exactly one figure, blank background), panel beats can name 0–2
characters and always have a location in-scene. Verified distribution across all 49 beats:
establishing `{0: 3, 1: 4, 2: 1}`, action `{0: 2, 1: 13, 2: 8}`, dialogue `{1: 18}` characters
per beat [VERIFIED: output/beats.json, `Counter(len(b['characters'])...)` per type, computed
this session]. For beats with characters present, the subject clause should combine the
location grounding with the character(s) acting *in* that location — this is the opposite of
the slot-art convention (which explicitly renders locations "quiet and unoccupied") and the
opposite of the slot-art character convention (isolated on blank white). Recommend building the
wide/medium subject clause primarily from `beat["content"]` itself (already a full descriptive
sentence of the specific action, already free of quoted dialogue text — verified: dialogue
beats' `content` fields describe the speech act, e.g. `"Rocky tries to interject."`, never the
literal spoken line [VERIFIED: output/beats.json, dialogue-type beat `content` fields, read this
session]) rather than re-deriving it from `describe_slot`, which was designed to average up to 3
beats into a general room description — the wrong granularity for one specific beat's action.
Still run `beat["content"]` through `style._strip_on_screen_text`/the quote stripper defensively
before it reaches the prompt (cheap insurance against the D-12 leak risk, same as every other
text this project hands to an image model).

### Pattern 4: Failure isolation — reuse `generate_missing_art`'s try/except-and-continue shape
**What:**
```python
# Source: src/animatic/core/asset_generator.py, generate_missing_art — the exact shape to reuse
try:
    image_bytes, mime_type = generate_slot_art(primary, prompt)
except Exception as e:  # noqa: BLE001 — one bad slot must not abort the run
    reason = f"generation failed: {type(e).__name__}: {e}"
    for member in members:
        member.source = "generation_failed"
        member.source_reason = reason
    continue
```
[VERIFIED: src/animatic/core/asset_generator.py, `generate_missing_art`] — apply the identical
shape per-beat in `panel_generator.generate_missing_panels`: one bad beat records
`source="generation_failed"` with a reason and the loop continues to the next beat (FR-02's
"system never blocks on a missing input" applies to panels the same way it applies to slots).

**Retry:** no retry mechanism exists yet in this codebase for image calls (the current code
fails once and records the failure). Recommend adding exactly one retry with a short fixed
backoff (e.g. one retry after 2s) before recording failure, since a single transient network/
5xx error costing one extra ~10s call is cheap against a 49-panel, ~9-minute budget, and the
project has no framework dependency for retry (`tenacity` is present only as a *transitive*
dependency of `google-genai`, not declared in `requirements.txt` — do not import it without
adding it explicitly; a five-line manual retry loop is simpler and consistent with the project's
existing "no new dependency for a small mechanism" pattern seen in `_cluster_near_matches`'s own
comment about preferring stdlib `difflib` over hand-rolling).

### Anti-Patterns to Avoid
- **Reference-image conditioning (D-08 HELD):** proven working, do not build into Phase 4. An
  additional `contents` part would be the mechanism if a later phase revisits this — do not
  add it speculatively now.
- **Batching all 49 panels into one Batch API job:** technically supported for image models, but
  the 24-hour SLA breaks the phase's own ~9-minute budget (D-10) and this project's live/demo
  execution model (DR-02: progress indicators must reflect real work happening now, not a job
  queued for later).
- **Writing all 49 panels to S3 in one batched call at the end of the run:** if the run is
  interrupted at panel 30 of 49, a batched-write design loses all 30 completed panels. Write
  per-panel, immediately, the same way `write_slot_art` does inside `generate_missing_art`'s
  loop — partial progress survives an interruption.
- **Trusting `output/assets/manifest.json`'s `stale_beat_ids` as Phase 4's own cache signal:**
  see Pattern 1 — compute panel staleness independently from the current manifest's
  `content_hash` values, not from a signal computed at a different point in time for a different
  purpose.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Character-name → slot_id normalization | A second slugify/alias function for panels | `slot_resolver._slugify` (import directly) | Single source of truth (D-01 of Phase 3: "no hand-curated alias list"); a second implementation risks drifting from the one beats.json's character names are actually keyed against |
| Room/character grounding text | Re-deriving location/wardrobe descriptions from raw beat text | `style.describe_slot`, `style.character_context` | Already strip on-screen text and quoted lettering (D-12 risk); already tested (`tests/test_style.py`) |
| Retry/backoff for transient API failures | A retry framework or hand-rolled exponential backoff class | A five-line manual retry loop (one retry, fixed short delay) | 49 calls total; a framework is overkill, and `tenacity` isn't a declared dependency |
| Content-change detection | mtime-based staleness | sha256 `content_hash` comparison | Established, explicit precedent: `asset_manifest.py`'s own docstring states this choice and why |
| Near-duplicate location key merging | A distance-metric library | stdlib `difflib.SequenceMatcher` (already used in `slot_resolver._cluster_near_matches`) | Not directly needed by Phase 4, but the same principle (stdlib over new dependency) applies to any hand-rolled matching Phase 4 might otherwise invent |

**Key insight:** Phase 4 is structurally a second pass through machinery Phase 3 already built
and hardened through two real regression cycles (the chrome/caption bug, the facial-feature
bug). The highest-leverage move is maximum reuse of `style.py` and the manifest/S3-write
patterns, not new abstractions.

## Common Pitfalls

### Pitfall 0: The manifest on disk right now is not the full 16-slot registry
**What goes wrong:** `output/assets/manifest.json` (and its S3 mirror) currently contains
**1 slot** (`int_dressing_room`), not the 16 slots (9 characters + 7 locations) Phase 3's
`03-03-SUMMARY.md`/STATE.md describe as shipped.
Verified directly this session:
```
$ python3 -c "import json; d=json.load(open('output/assets/manifest.json')); print(d['total_slots'], len(d['slots']))"
1 1
```
[VERIFIED: output/assets/manifest.json, read this session] and the S3 copy matches
(`aws s3 cp s3://animatic-media-628818/assets/manifest.json -` → same single-slot content)
[VERIFIED: live S3 read this session]. `manifest.json`'s `generated_at` is
`2026-08-25T05:13:10Z`, a full run's worth of time *after* `03-ART-REVIEW.md`'s
`--force` run (~22:05–22:13 the prior evening) — but all 13 art files from that earlier full
run are still present on disk in `output/assets/generated/` [VERIFIED: `ls -la`, this session].

**Why it happens:** `scripts/build_assets.py --only <slot_id>` (documented in its own usage
string as "the tracer path") **overwrites the full manifest** with only the resolved subset —
`build_manifest(slots, ...)` is called with whatever `slots` list survived the `--only` filter,
and `write_manifest` unconditionally overwrites `_LOCAL_MANIFEST` and the S3 key. Someone ran
`--only int_dressing_room` after the full run and it silently narrowed the shipped manifest back
down to one slot.

**How to avoid:** Before planning or executing Phase 4 against "the manifest," run
`python scripts/build_assets.py` (no `--only`) once. Because all 13 art files are still on disk
and their prompts are unchanged, `generate_missing_art`'s reuse path
(`prev.get("prompt") == prompt` and the file exists) should mean this costs **zero new API
calls** — the same zero-new-calls behavior `03-02-SUMMARY.md` already demonstrated for a clean
re-run. This should be Phase 4's first executable task, not an assumption baked into later
tasks.

**Warning signs:** `manifest["total_slots"] != 16`, or `len(manifest["slots"]) != 16`.
Recommend a cheap assertion at the top of `scripts/build_panels.py` that fails loudly rather
than silently generating panels for 1 of 49 beats' worth of usable slot data.

### Pitfall 1: `system_instruction` + image-output model raises `ClientError`
**What goes wrong:** Passing `system_instruction` to `generate_content` alongside
`response_modalities=["IMAGE"]` raises a `ClientError` on the MLDev (API-key) backend.
**Why it happens:** documented directly in the existing code's own docstring:
> "Deliberately does NOT pass `system_instruction` — RESEARCH Pitfall 1: `system_instruction`
> combined with an image-output model raises `ClientError` on this backend."
[VERIFIED: src/animatic/core/asset_generator.py, module docstring]
**How to avoid:** Fold every rule (style, shot size, facial clause) into the single `contents`
string, exactly as `asset_generator.py` and `style.build_slot_prompt` already do. Do not
introduce `system_instruction` for panels.
**Warning signs:** a `ClientError` on the very first live panel call — this would indicate the
plan tried to separate "system rules" from "prompt content."

### Pitfall 2: Negations and mid-prompt rules get rendered as literal text or lose to what follows
**What goes wrong:** The literal words "NO FACIALS" were painted into a frame in the original
Phase 3 smoke test; a rule stated mid-prompt lost to whatever text followed it.
**Why it happens:** documented in `style.py`'s own module docstring (D-09) and directly tested:
`tests/test_style.py::test_style_block_avoids_bare_negations_and_allcaps_imperatives` asserts no
sentence in `STYLE_BLOCK` starts with a bare negation or an all-caps imperative fragment
[VERIFIED: tests/test_style.py, read this session].
**How to avoid:** Every panel prompt clause follows the same two rules D-06 states: positive
prose describing the finished picture, and the facial-feature rule stated **last** in the
prompt (after style, after location/character grounding, after shot-size framing).
**Warning signs:** any prompt clause that reads as an imperative fragment ("NO EYES.") rather
than descriptive prose, or that appears before the subject/action description in the assembled
string.

### Pitfall 3: Rate limits for `gemini-3.1-flash-image` could not be verified this session
**What goes wrong:** Concurrent panel generation could hit per-minute request or "images per
minute" (IPM) limits, producing 429s partway through a 49-panel run.
**Why it happens:** Google's rate-limits documentation states limits "depend on a variety of
factors (such as your usage tier) and can be viewed in Google AI Studio"
[CITED: ai.google.dev/gemini-api/docs/rate-limits] — no numeric RPM/IPM figure for this specific
model was published on the page fetched this session, and this session has no AI Studio account
access to read the live dashboard value.
**How to avoid:** [ASSUMED] Default to sequential (not concurrent) generation for the initial
implementation — this is also what D-10's own ~10s/image, ~8-9 min/49-panel budget already
assumes, and it's also what Phase 3's real generation runs did (12 calls made sequentially,
`03-02-SUMMARY.md`; 13 calls, `03-ART-REVIEW.md`). If concurrency is added later, keep it small
(2-4 workers) and add 429-aware backoff.
**Warning signs:** `ClientError`/`ResourceExhausted`-shaped exceptions mentioning quota or rate
limit in the message.

### Pitfall 4: Batching writes (not calls) risks losing completed work on interruption
**What goes wrong:** A design that accumulates all 49 panel bytes in memory and writes the index
+ all panels to S3 in one pass at the end loses everything if the process is killed at panel 40.
**Why it happens:** Not observed yet in this codebase (Phase 3 already avoids it — `write_slot_art`
is called inside the per-slot loop, not batched), but it's an easy mistake to make when
"whether panels are written to S3 per-panel or batched" is explicitly left to this phase's
discretion (04-CONTEXT.md).
**How to avoid:** Write each panel's bytes (local + S3) immediately after that beat's
`generate_content` call succeeds, before moving to the next beat — mirrors `write_slot_art`'s
placement inside `generate_missing_art`'s loop exactly. Write the index file once at the end (or
incrementally after each panel — cheap, since it's a small JSON file, and gives an accurate
"in-progress" index if the run is interrupted).
**Warning signs:** a design where `write_index()` is the only write call in the function.

### Pitfall 5: `duration_source` has three values, not two
**What goes wrong:** Documentation drift — `STATE.md`'s own Phase 2 contract section states
`duration_source` is `` `model` | `dialogue_floor` `` , but the actual live `beats.json` and the
source code both show a third value.
**Why it happens:** `beat_extractor.py` sets `duration_source` in three places:
`duration_source: str = "model"` (dataclass default, beat_extractor.py:133),
`b.duration_source = "page_budget"` (beat_extractor.py:311),
`beat.duration_source = "dialogue_floor"` (beat_extractor.py:390)
[VERIFIED: src/animatic/core/beat_extractor.py, grepped this session, all three assignment
sites]. The live corpus is currently 100% `page_budget`:
`Counter({'page_budget': 49})` [VERIFIED: output/beats.json, computed this session].
**Why this matters for Phase 4:** none of Phase 4's own logic branches on `duration_source`, but
D-04 asks Phase 4 to follow "the `duration_source` precedent" for recording shot-size provenance
— the actual precedent has three enum values with three different trigger conditions, not two.
Don't copy STATE.md's summary; if the plan documents the precedent, cite the three real values.
**Warning signs:** a test or doc that asserts `duration_source in {"model", "dialogue_floor"}`
would incorrectly reject the 49/49 beats actually carrying `"page_budget"`.

## Code Examples

### Existing, verified image-generation call shape (reuse unchanged)
```python
# Source: src/animatic/core/asset_generator.py — the exact call shape smoke-tested live
# (STATE.md: "Panels (Phase 4) | gemini-3.1-flash-image | 697 KB image returned")
client = genai.Client(api_key=settings.google_api_key)
response = client.models.generate_content(
    model=f"models/{settings.gemini_image_model}",   # "models/gemini-3.1-flash-image"
    contents=prompt,
    config=types.GenerateContentConfig(response_modalities=["IMAGE"]),
)
parts = response.candidates[0].content.parts
for part in parts:
    if part.inline_data is not None:
        image_bytes, mime_type = part.inline_data.data, part.inline_data.mime_type
```

### New: aspect ratio control for a consistent panel frame
```python
# Source: installed SDK, .venv/lib/python3.14/site-packages/google/genai/types.py
# ImageConfig class, line 5763 — VERIFIED by reading the installed 2.19.0 source this session
from google.genai import types

config = types.GenerateContentConfig(
    response_modalities=["IMAGE"],
    image_config=types.ImageConfig(aspect_ratio="16:9"),  # supported: "1:1","2:3","3:2","3:4",
                                                             # "4:3","9:16","16:9","21:9" (verified
                                                             # from the installed SDK's own
                                                             # docstring, not currently used by
                                                             # asset_generator.py)
)
```
Recommend setting `aspect_ratio="16:9"` on every panel call — `asset_generator.py` does not set
this today (slot-art portraits/establishing shots don't need a specific video-frame aspect
ratio), but Phase 7 assembles panels into a video, so a consistent frame shape across all 49
panels is worth fixing explicitly rather than leaving to the model's per-call default.
**Caveat:** a WebFetch of `ai.google.dev/gemini-api/docs/image-generation` returned example code
using a different, newer-looking API surface (`client.interactions.create(...,
response_format={...})`) that does **not** match the installed SDK — `client.interactions` does
not exist as a construct verified in this session's SDK source read. Treat that page's exact
code sample as unverified against this project's pinned SDK version; the `GenerateContentConfig(image_config=...)`
form above is the one directly confirmed against the installed 2.19.0 source and is consistent
with `asset_generator.py`'s existing, live-tested call shape.

### Batch API — confirmed shape, not recommended for this phase (see Standard Stack)
```python
# Source: ai.google.dev/gemini-api/docs/batch-api — [CITED], fetched this session
inline_requests = [
    {
        "contents": [{"parts": [{"text": prompt}]}],
        "config": {"response_modalities": ["IMAGE"]},
    }
    for prompt in panel_prompts
]
batch_job = client.batches.create(model="gemini-3.1-flash-image", src=inline_requests)
# batch_job.state polled until done; target turnaround documented as 24h, "often quicker"
```
`client.batches.create(...)` exists in the installed SDK (`batches.py:2292`)
[VERIFIED: installed SDK source, read this session] and accepts an arbitrary model string plus
inlined requests, so nothing in the SDK *prevents* this — the rejection is purely on turnaround
time (see Standard Stack § Alternatives Considered).

## State of the Art

| Old Approach (Phase 3, per-slot) | Current Approach (Phase 4, per-beat) | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Character art: full facial suppression, isolated on blank white | Panel: facial suppression varies by shot size; character appears in-scene, not isolated | This phase | New prompt clause needed (Pattern 3); no direct precedent to copy verbatim |
| Slot cache: prompt-string equality (`prev.get("prompt") == prompt`) | Panel cache: structured hash over beat/shot-size/slot-hash/template-version | This phase | Prompt-string equality alone can't detect "the *referenced* slot's art changed" if the panel's own prompt text doesn't literally embed the slot's content_hash — a structured key is more precise for the D-08-held case |

**Deprecated/outdated:** none within this project; Phase 4 has no prior implementation to
deprecate.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The draft close-up facial clause (brow/mouth/nose shown, eyes suppressed) will pass on first generation the way the full-suppression clause did *not* on its first pass | Architecture Patterns § Pattern 3 | Likely wrong given Phase 3's own history — budget at least one regeneration pass for scene 2's tracer batch, matching D-09's own reasoning for doing a tracer scene first |
| A2 | A single retry with fixed ~2s backoff is sufficient failure handling for transient errors | Common Pitfalls § Pitfall 3, Don't Hand-Roll | If failures are rate-limit-driven rather than transient-network-driven, a fixed 2s backoff won't help — would need exponential backoff or a longer pause; unverified because rate limits themselves are unverified (A3) |
| A3 | Sequential (non-concurrent) generation stays within `gemini-3.1-flash-image`'s actual rate limits | Standard Stack § Supporting, Common Pitfalls § Pitfall 3 | If the real per-minute limit is lower than 1 request/~10s (unlikely but unverified), even sequential generation could 429; check actual limits in AI Studio before executing at scale |
| A4 | `aspect_ratio="16:9"` is the right frame shape for Phase 7's assembly | Code Examples | Not confirmed against any Phase 7 spec (Phase 7 is not yet planned) — reasonable default for "watchable video" (ROADMAP Phase 7 criterion 1) but not sourced from a Phase 7 requirement |

**If this table is empty:** N/A — see rows above.

## Open Questions

1. **Exact rate limits (RPM/IPM) for `gemini-3.1-flash-image` on this project's API key tier**
   - What we know: the model page confirms Batch API support and general "optimized for speed
     and high-volume" positioning; the rate-limits reference page explains the *dimensions*
     (RPM/TPM/RPD/IPM) but not this model's numeric values without an authenticated AI Studio
     session.
   - What's unclear: whether 49 sequential calls at ~10s apart (D-10's own budget) risk hitting
     any per-minute ceiling, or whether there's comfortable headroom.
   - Recommendation: check `https://aistudio.google.com/rate-limit` with the project's actual key
     before running the full 49-panel batch; keep sequential execution as the safe default
     regardless.

2. **Whether the close-up facial clause (Pattern 3's draft) needs iteration before scene 2's 19
   panels are shown to the user (D-09)**
   - What we know: the analogous full-suppression clause needed one regeneration pass in Phase 3.
   - What's unclear: whether partial suppression (3 of 4 features shown) is easier, harder, or
     differently-failure-prone than full suppression — no data yet.
   - Recommendation: budget the D-09 tracer-scene checkpoint explicitly as a prompt-iteration
     checkpoint, not just a "look at the pictures" checkpoint — the planner should expect this
     clause specifically to need at least one revision.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `google-genai` (Python package) | Panel generation calls | ✓ | 2.19.0 | — |
| `boto3` | Panel + index S3 writes | ✓ | already in use by `s3_writer.py` | local-only write (`s3_writer.put_bytes` already degrades honestly on failure) |
| `GOOGLE_API_KEY` env var | Auth for `genai.Client` | ✓ (proven live in Phase 3's real generation runs) | — | — |
| AWS credentials (`AWS_PROFILE=newaccount` locally / ECS task role in prod) | S3 writes | ✓ (proven live — `s3_ok: true` in Phase 3's manifest writes) | — | local-only write, `s3_ok=false` recorded honestly |
| `docs/rocky-1976.pdf` | Re-resolving slots via `slot_resolver.resolve_slots` (needs raw scene headings) | ✓ | — | — |
| `output/beats.json` | Beat source | ✓ (49 beats present) | — | — |
| `output/assets/manifest.json` (full 16-slot version) | Slot content_hash lookups for the cache key | **✗ currently only 1 slot on disk** (Pitfall 0) | — | Run `python scripts/build_assets.py` (no `--only`) first — expected zero new API calls given unchanged art/prompts |

**Missing dependencies with no fallback:** none — every runtime dependency is present and
already proven live.

**Missing dependencies with fallback:** the full 16-slot manifest is a *data* gap, not a
dependency gap; the fallback is re-running `build_assets.py`, documented in Pitfall 0.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.1.1 [VERIFIED: `pytest --version`, this session] |
| Config file | none found (`pytest.ini`/`setup.cfg` absent); `requirements-dev.txt` pins `pytest>=8`, `httpx>=0.27`, `pytest-asyncio>=0.23` |
| Quick run command | `PYTHONPATH=src python3 -m pytest tests/test_panel_generator.py -q` |
| Full suite command | `PYTHONPATH=src python3 -m pytest tests/ -q` — confirmed **88 passed** against the current tree this session (`PYTHONPATH=src` required; bare `pytest tests/` fails with `ModuleNotFoundError: No module named 'animatic'` since there's no installed package/conftest path shim) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| FR-03 (panel generation) | Every beat in scenes 1-8 produces a panel record | unit (mocked `generate_content`) | `PYTHONPATH=src pytest tests/test_panel_generator.py::test_every_beat_gets_a_panel_entry -x` | ❌ Wave 0 |
| FR-03 (no facial features wide/medium) | Built prompt string for a wide/medium beat contains the blank-plane clause and no headwear/garment nouns | unit, value-level (extend `test_style.py`'s pattern) | `PYTHONPATH=src pytest tests/test_panel_prompt.py::test_wide_medium_prompt_suppresses_all_features -x` | ❌ Wave 0 |
| FR-03 (close-up: brow/mouth/nose only) | Built prompt string for a close-up beat names brow/mouth/nose and explicitly keeps eyes blank | unit, value-level | `PYTHONPATH=src pytest tests/test_panel_prompt.py::test_closeup_prompt_shows_only_brow_mouth_nose -x` | ❌ Wave 0 |
| D-01 (shot size derived from beat type) | `establishing→wide`, `action→medium`, `dialogue→close-up`, deterministic | unit, pure function | `PYTHONPATH=src pytest tests/test_panel_prompt.py::test_shot_size_derivation -x` | ❌ Wave 0 |
| D-02 (shot size never written to beats.json) | Running panel generation does not mutate `output/beats.json` on disk | unit, regression | `PYTHONPATH=src pytest tests/test_panel_generator.py::test_beats_json_not_mutated -x` | ❌ Wave 0 |
| D-04 (panel records shot size + reason) | Panel index entry has non-empty `shot_size` and `shot_size_reason` fields | unit, value-level | `PYTHONPATH=src pytest tests/test_panel_manifest.py::test_index_entry_has_shot_size_reason -x` | ❌ Wave 0 |
| ROADMAP criterion 5 (cache reuse) | Re-running with unchanged beats/assets produces zero new `generate_content` calls | unit, mock-call-count assertion (mirrors `test_asset_manifest.py`'s reuse test pattern) | `PYTHONPATH=src pytest tests/test_panel_generator.py::test_unchanged_run_makes_zero_api_calls -x` | ❌ Wave 0 |
| Phase 3 criterion 4 (slot swap invalidates dependent panels) | Changing a dependent slot's `content_hash` in the manifest marks exactly that slot's beats' panels stale | unit, mirrors `test_asset_manifest.py`'s change-detection test | `PYTHONPATH=src pytest tests/test_panel_manifest.py::test_slot_content_hash_change_invalidates_dependent_panels -x` | ❌ Wave 0 |
| NFR-04 (machine-readable reason) | Every panel index entry has non-empty `prompt`, `source_reason`, `asset_slots_used` | unit, value-level | `PYTHONPATH=src pytest tests/test_panel_manifest.py::test_every_entry_has_reason_fields -x` | ❌ Wave 0 |
| Live integration (real API, manual/CI-gated) | Real `generate_content` call for one beat returns inline image data, mirrors STATE.md's smoke-test evidence | smoke, manual trigger | `python scripts/build_panels.py --scene 2 --only <one beat_id>` | ❌ Wave 0 (script doesn't exist yet) |

### Sampling Rate
- **Per task commit:** `PYTHONPATH=src python3 -m pytest tests/test_panel_generator.py tests/test_panel_prompt.py tests/test_panel_manifest.py -q`
- **Per wave merge:** `PYTHONPATH=src python3 -m pytest tests/ -q` (full suite, currently 88 passing, mocked — no live API calls in CI)
- **Phase gate:** Full suite green before `/gsd-verify-work`, plus a manual art-review pass on the
  scene-2 tracer batch against the PROJECT.md facial-feature rule (mirrors `03-ART-REVIEW.md`'s
  own methodology — sampled real generated images judged against explicit criteria, not a
  re-run of the automated check)

### Wave 0 Gaps
- [ ] `tests/test_panel_prompt.py` — shot-size derivation (D-01), close-up/wide/medium facial
      clause value-level guards (extends `test_style.py`'s pattern)
- [ ] `tests/test_panel_generator.py` — mocked `generate_content`, cache-hit/miss, failure
      isolation, zero-new-calls-on-unchanged-run (mirrors `test_asset_manifest.py`)
- [ ] `tests/test_panel_manifest.py` — index build/write, slot-hash-change invalidation
      (mirrors `test_asset_manifest.py`'s `_detect_changes` tests)
- [ ] `scripts/build_panels.py` — CLI entry point, no tests needed beyond the modules it calls,
      but needs a `--scene` flag for D-09's tracer-scene-first workflow

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | Phase 4 has no user-facing auth surface — it's a backend generation pipeline invoked by script/API on fixed content (DR-01) |
| V3 Session Management | No | Same as above |
| V4 Access Control | No | No per-user resources; single fixed script, anonymous demo per DR-01 is Phase 9's concern |
| V5 Input Validation | Yes (narrow) | Beat content is parser-generated from a fixed, trusted PDF (not user-uploaded — DR-01/PROJECT.md Non-Goals: "Arbitrary user script upload on the hosted demo" explicitly excluded), so this is not classic untrusted-input validation. The applicable control is defensive text-sanitization before content reaches the image model: reuse `style._strip_on_screen_text` / the quoted-lettering stripper on every beat-content string that reaches a prompt, the same control already applied to slot descriptions (D-12's known leak risk) |
| V6 Cryptography | No | No new secrets/crypto surface this phase; reuses existing `GOOGLE_API_KEY`/AWS credential handling unchanged |
| V12 File/Resource handling | Yes (narrow) | Panel filenames must be built from the already-validated `beat_id` (matches `[a-z0-9]+` pattern from `beat_assembler`'s own beat_id construction), never from raw beat content — mirrors `asset_manifest._write_art_bytes`'s existing rule: "Write paths are built from `Path(name).name` plus a slot_id that is already `[a-z0-9_]` by construction... never from a raw external filename" [VERIFIED: src/animatic/core/asset_manifest.py, module docstring] |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Prompt injection via beat content (a future phase adds user-uploaded scripts) | Tampering | Not exploitable *this* phase (fixed script only, DR-01), but the mitigation to carry forward if that Non-Goal is ever revisited is the same text-stripping already applied — flagging here for awareness, not building new controls now |
| Path traversal via a malformed `beat_id` used to build a filename | Tampering | `beat_id`s originate from `beat_assembler`'s own deterministic `sNbM` construction (verified pattern from `output/beats.json`, e.g. `"s1b1"`, `"s2b11"`), never from external input this phase — no new validation needed beyond continuing to key filenames off `beat_id`, not off arbitrary strings |
| S3 write failure silently reported as success | Tampering / Repudiation (data integrity) | Already solved project-wide by `s3_writer.put_bytes`'s honest `S3Result` — reuse unchanged, do not build a parallel write path |

## Sources

### Primary (HIGH confidence)
- `src/animatic/core/style.py`, `asset_generator.py`, `asset_manifest.py`, `s3_writer.py`,
  `slot_resolver.py`, `beat_extractor.py`, `beat_assembler.py`, `config.py` — read in full this
  session
- `tests/test_style.py`, `tests/test_asset_manifest.py` — read this session, guard patterns to
  extend
- `output/beats.json` (49 beats), `output/assets/manifest.json` (currently 1 slot — see
  Pitfall 0), `s3://animatic-media-628818/assets/manifest.json` (same content) — read live this
  session
- `.venv/lib/python3.14/site-packages/google/genai/{types.py,batches.py}` — installed SDK 2.19.0
  source, read directly this session for `ImageConfig`, `GenerateContentConfig`,
  `Batches.create`
- `.planning/phases/phase-3/03-ART-REVIEW.md`, `.planning/WINDOWS.md` — Phase 3's actual
  regression history against real API output

### Secondary (MEDIUM confidence)
- [ai.google.dev/gemini-api/docs/batch-api](https://ai.google.dev/gemini-api/docs/batch-api) —
  Batch API turnaround SLA, image-generation support, pricing discount, inline-request shape
- [ai.google.dev/gemini-api/docs/models/gemini-3.1-flash-image](https://ai.google.dev/gemini-api/docs/models/gemini-3.1-flash-image) —
  model ID confirmation, Batch API support flag
- [ai.google.dev/gemini-api/docs/rate-limits](https://ai.google.dev/gemini-api/docs/rate-limits) —
  rate-limit dimensions (RPM/TPM/RPD/IPM), no numeric value obtainable without an authenticated
  session

### Tertiary (LOW confidence)
- [ai.google.dev/gemini-api/docs/image-generation](https://ai.google.dev/gemini-api/docs/image-generation) —
  WebFetch summary described a `client.interactions.create(...)` surface not found in the
  installed SDK source; treated as unverified against this project's pinned SDK version and
  superseded by the direct `types.py` read for the `ImageConfig`/`GenerateContentConfig` shape
  actually used in Code Examples

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new packages; every dependency already installed and live-tested
- Architecture (caching, beat→slot mapping, manifest shape): HIGH — derived directly from Phase
  3's own shipped, tested code, not from external research
- Prompt phrasing for the close-up facial clause: MEDIUM — follows a proven pattern's rules but
  is a novel case (partial rather than full suppression) with no live-API confirmation yet;
  explicitly flagged as needing D-09's tracer-scene validation
- Batch API / rate limits: MEDIUM (Batch API turnaround, confirmed via official docs) / LOW
  (exact numeric rate limits, unverifiable without account access this session)
- Pitfall 0 (stale manifest on disk): HIGH — directly observed this session via live file read
  and live S3 read

**Research date:** 2026-08-25
**Valid until:** ~14 days for the Gemini API specifics (image-generation models/pricing/batch
terms are still described as "preview"-adjacent and shifted meaningfully within the last few
months per search results); indefinite for the in-repo architecture findings, which are only
invalidated by Phase 3 code changes
