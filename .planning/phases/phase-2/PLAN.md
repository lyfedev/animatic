# Phase 2 — Beat Parser

**Milestone:** 1 — Actor
**Goal:** Parse Rocky PDF (scenes 1–8) into a structured beat list with machine-readable reasons. Every beat has a `beat_id`, type, content summary, duration estimate, and reason field. Output serialised to JSON and stored in S3.

---

## Context & decisions

| Decision | Choice | Reason |
|---|---|---|
| PDF extraction | `pdfplumber` | Clean text extraction; handles screenplay formatting better than PyMuPDF for text-heavy docs |
| Beat extraction AI | Google Gemini 1.5 Flash (via `google-genai`) | Fast, cheap, long-context — entire scenes fit in one call |
| Scene scope | Scenes 1–8 only | Contest requirement; scene numbers are embedded in the script as INT/EXT headers |
| Beat density model | Action > dialogue > establishing | Brief requirement; Gemini prompt encodes this rule explicitly |
| Output format | JSON file per run → S3 | Consistent with overall state manifest approach |
| Local output | Also write to `output/beats.json` | Developer convenience during testing |
| Gemini prompt strategy | Structured JSON output mode | `response_mime_type="application/json"` — no parsing fragility |
| Scene boundary detection | Regex on INT./EXT. headings + scene numbers | Rocky script has consistent `INT. LOCATION - TIME` + scene number format |

---

## Script structure (observed from Rocky PDF)

Scene headings follow this pattern:
```
INT. BLUE DOOR FIGHT CLUB - NIGHT  1  1
INT. DRESSING ROOM - NIGHT         3  3
INT. TROLLEY - NIGHT               4  4
EXT. STREET - NIGHT                5  5
```
Scene number appears at end of heading line. Scenes 1–8 map to:
1. INT. BLUE DOOR FIGHT CLUB - NIGHT
2. INT. DRESSING ROOM - NIGHT
3. INT. TROLLEY - NIGHT
4. EXT. STREET - NIGHT
5. EXT. ROCKY'S APARTMENT - NIGHT
6. INT. ROCKY'S HALLWAY - NIGHT
7. INT. ROCKY'S APARTMENT - NIGHT
8. EXT. SUNRISE OF PHILADELPHIA SKYLINE - DAWN

---

## Beat schema

```json
{
  "beat_id": "s1b3",
  "scene": 1,
  "beat": 3,
  "scene_heading": "INT. BLUE DOOR FIGHT CLUB - NIGHT",
  "type": "action",
  "content": "Rocky drives a flurry into the Black Fighter's body and knocks him out. Fans throw rubbish into the ring.",
  "duration_secs": 4.5,
  "motion_candidate": true,
  "reason": "High-intensity action beat; knockout moment warrants longer hold and motion candidacy",
  "characters": ["ROCKY", "BLACK FIGHTER"],
  "dialogue": null
}
```

**Beat types:**
- `action` — physical action, no or minimal dialogue
- `dialogue` — exchange of lines, minimal movement
- `establishing` — scene-setting, no characters or single character intro

**`motion_candidate`:** Pre-flagged by parser for Phase 6. True for action beats with high visual intensity.

---

## Task breakdown

### Task 1 — PDF text extractor
`src/animatic/core/pdf_extractor.py`

- Extract raw text from `docs/rocky-1976.pdf` using `pdfplumber`
- Split into scenes by INT./EXT. heading regex
- Filter to scenes 1–8 only
- Return `dict[int, str]` — scene number → raw scene text

**Verification:** `extract_scenes("docs/rocky-1976.pdf", scenes=range(1,9))` returns dict with 8 keys, each containing non-empty text.

---

### Task 2 — Gemini beat extractor
`src/animatic/core/beat_extractor.py`

- Accept scene number + raw scene text
- Build structured prompt instructing Gemini to:
  - Segment scene into beats
  - Assign type (action / dialogue / establishing)
  - Vary density: action scenes → more beats; dialogue → fewer; establishing → 1
  - Write a `reason` for each beat boundary and duration
  - Flag `motion_candidate` for high-intensity action beats
  - Return strict JSON array matching beat schema
- Call `google.genai` with `response_mime_type="application/json"`
- Parse and validate response
- Return `list[Beat]` (typed dataclass)

**Verification:** `extract_beats(scene_num=1, text=<scene1_text>)` returns ≥3 beats, all with `reason` field, valid JSON.

---

### Task 3 — Beat list assembler & S3 writer
`src/animatic/core/beat_assembler.py`

- Accept `dict[int, list[Beat]]` — all scenes
- Assign globally unique `beat_id` (`s{scene}b{beat}`)
- Compute `pct_motion_candidates`
- Serialise to full beat list JSON
- Write to:
  - S3: `beats/latest.json` in `animatic-media-628818`
  - Local: `output/beats.json` (gitignored)
- Return S3 URI

**Verification:** Output JSON validates against schema; all beats have `beat_id`, `reason`, `duration_secs`.

---

### Task 4 — CLI entry point
`scripts/parse_beats.py`

```bash
python scripts/parse_beats.py --scenes 1-8
```

- Runs full pipeline: extract → beat → assemble → write
- Prints summary table: scene, beat count, type breakdown
- Prints S3 URI of output

**Verification:** Running script against Rocky PDF produces `output/beats.json` with beats for all 8 scenes.

---

### Task 5 — FastAPI endpoint
`src/animatic/api/beats.py` — `POST /beats/parse`

- Triggers beat parsing pipeline
- Streams progress via response (scene-by-scene)
- Returns beat list summary + S3 URI
- Live execution (not cached) — per demo requirement

**Verification:** `POST /beats/parse` returns 200 with beat count per scene.

---

### Task 6 — Unit tests
`tests/test_beat_parser.py`

- Test scene extraction: 8 scenes detected from PDF
- Test beat schema validation: all required fields present
- Test beat types: valid values only
- Test reason field: non-empty string on all beats
- Mock Gemini API call (no real API calls in unit tests)

**Verification:** `pytest tests/test_beat_parser.py` — all pass, no real API calls made.

---

## Environment setup needed before execution

Google Cloud credentials must be configured before Task 2 can run:

1. Create a Google Cloud project (or use existing)
2. Enable the **Generative Language API** (Gemini)
3. Create a service account key → download JSON
4. Set in `.env`:
   ```
   GOOGLE_CLOUD_PROJECT=your-project-id
   GOOGLE_APPLICATION_CREDENTIALS=path/to/key.json
   ```
5. Update SSM parameters:
   ```bash
   aws ssm put-parameter --name "/animatic/google-cloud-project" \
     --value "your-project-id" --type String --overwrite --profile newaccount
   ```

**This is a prerequisite for Task 2. Tasks 1, 4 (partial), and 6 can proceed without it.**

---

## Dependencies to add to `requirements.txt`

```
pdfplumber>=0.11
google-genai>=0.8
```

---

## Verification checklist

- [ ] `extract_scenes()` returns 8 scenes from Rocky PDF
- [ ] `extract_beats(scene=1)` returns valid beat list with `reason` fields (requires Google Cloud creds)
- [ ] `python scripts/parse_beats.py --scenes 1-8` completes and writes `output/beats.json`
- [ ] `output/beats.json` has beats for all 8 scenes, all with `beat_id` and `reason`
- [ ] `POST /beats/parse` returns 200
- [ ] `pytest tests/test_beat_parser.py` — all pass
- [ ] Beats written to S3 `beats/latest.json`

---

## Commit plan

1. `feat(deps): add pdfplumber, google-genai to requirements`
2. `feat(parser): pdf scene extractor — scenes 1–8 from rocky script`
3. `feat(parser): gemini beat extractor with structured json output`
4. `feat(parser): beat assembler, beat_id assignment, s3 writer`
5. `feat(parser): cli entry point — parse_beats.py`
6. `feat(api): POST /beats/parse endpoint`
7. `test(parser): unit tests for beat parser pipeline`
