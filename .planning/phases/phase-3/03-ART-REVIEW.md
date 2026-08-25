# Phase 3 Plan 03 — Art Review

**Reviewed:** 2026-08-24/25 (worktree wall clock)
**Reviewer:** Claude (executor), against the five D-09/PROJECT.md points, on real
`gemini-3.1-flash-image` output — not a mock, not a description of intended behavior.

## Context

Wave 2's manifest had `rocky` resolved as `source="reference"` (matched by loose
filename tokens under `assets/reference-art/`). Commit `5f581e0` (landed after 03-03
was written, before this plan executed) tightened reference-art adoption to **only**
`assets/reference-art/<slot_id>/` — a named slot directory. The four loose files in
`assets/reference-art/` (`boxing_poses.jpeg`, `rocky_porkpie.jpg`, `rocky_porkpie2.jpg`,
`rocky_trunks_front.jpg`) are no longer adopted; they're recorded as `candidates` on
the `rocky` slot's reference scan and never promoted. **Consequence for this review:
`rocky` is now a generated slot** — the run in this plan made 13 image calls (16 slots,
7 shared with the minor-character generic art_slot_id, minus 4 = 13 distinct art files),
not the 12 the plan text anticipated. `rocky.jpg` is judged here as generated art
alongside everything else.

## Run judged

First full run: `output/assets/manifest.json` generated_at `2026-08-25T01:19:...Z`
(local wall clock ~2026-08-24 18:19–18:21), 13 files written to
`output/assets/generated/` and `s3://animatic-media-628818/assets/art/`. A second,
`--force`-regenerated run (below) is the one actually shipped and referenced by the
manifest currently on disk.

## First pass — verdicts against the five points

Sampled per the plan's instruction: highest-priority location
`int_blue_door_fight_club`, one exterior (`ext_street`), one bespoke character
(`black_fighter`), and `generic_minor_character`. Also spot-checked `rocky`, `woman`,
`promoter`, `int_rockys_apartment`, `int_dressing_room` for a broader read since `rocky`
is no longer a free pass via reference art.

| Slot | 1. Flat black linework on white | 2. Sits alone, no chrome | 3. No drawn-in words | 4. No facial features (characters) | 5. Reads as the script's place |
|---|---|---|---|---|---|
| `int_blue_door_fight_club` | PASS — pure outline, two tones, no shading | PASS — no border/binding/caption | PASS — no lettering | n/a (location) | PASS — tiny boxing ring, ropes, low-rent gym signage boards left blank; matches "trashy, dimly lit fight club... tiny boxing ring" from the beats |
| `ext_street` | PASS | PASS | PASS | n/a (location) | PASS — storefronts, streetlamp, trash can, cracked sidewalk; peopleless as instructed |
| `black_fighter` | PASS | PASS | PASS | **FAIL** — beret, scarf, tactical gear drawn correctly, but the face carries a visible brow ridge, nose bridge and mouth line instead of a blank plane | n/a |
| `generic_minor_character` | PASS | PASS | PASS | **FAIL** — full face: eyes, eyebrows, nose, mouth all drawn in | n/a |
| `rocky` | PASS | PASS | PASS | PASS — genuinely blank oval face under the fedora, only hair/hat/jaw outline | n/a |
| `promoter` | PASS | PASS | PASS | PASS — smooth blank face silhouette | n/a |

**Verdict: 2 of 4 sampled slots (both characters) failed point 4.** This is the one
regression this project has repeatedly hit (Wave 2's `03-02-SUMMARY.md` logged the same
failure mode on different slots — `generic_minor_character` and `promoter` that time,
`black_fighter` and `generic_minor_character` this time). Non-deterministic per
character, not systemic to one slot, but frequent enough across two independent runs
that the prompt wording itself was underspecified.

## Fix applied

`src/animatic/core/asset_generator.py::_subject_note` — both the bespoke-character and
minor-character subject clauses previously said "The head is a smooth, unbroken white
shape... with hair, hat and jaw described by the same outline work." The model kept
reading that as license to still draw a face *inside* that shape. Rewrote to name the
specific interior linework that must not appear, inside a full descriptive sentence
(not a bare imperative, consistent with D-09's phrasing rule): "Where the face sits,
the outline traces one continuous blank plane bounded only by the hairline, hat brim
and jaw contour — as bare and unmarked as the open background itself, with no eyebrow,
eye, nose or mouth line interrupting that plane anywhere." No change to `STYLE_BLOCK`
or to `style.py` — the failure was specific to the character subject clause, not the
shared style block, and `style.py`'s protected fixes (6e263e8) were left untouched.

Full test suite re-run after the edit: 81/81 passing, no prompt text pinned by any
test, so no test updates were needed.

## Second pass — after `python scripts/build_assets.py --force`

All 13 slots regenerated (132.4s, 13 real API calls). Re-judged the same four sampled
slots plus `rocky`, `promoter`, `woman`, `cornerman`, `int_dressing_room`,
`int_rockys_apartment` (8 of 13 total, covering every bespoke character and 4 of 7
locations):

| Slot | Facial features | Notes |
|---|---|---|
| `black_fighter` | PASS — fully blank plane, beret/scarf/gear intact | regenerated with a different pose (soldier-style loadout) but face compliant |
| `generic_minor_character` | PASS — fully blank plane | |
| `rocky` | PASS | new pose (fedora + jacket), still blank |
| `promoter` | PASS | |
| `woman` | PASS — blank oval under sun hat | |
| `cornerman` | PASS — blank plane under cap | |
| `int_blue_door_fight_club` | n/a | re-checked, still compliant on all location points, ring/gym reads correctly |
| `ext_street` | n/a | re-checked, still compliant, peopleless, storefronts read as Philadelphia street |
| `int_dressing_room` | n/a | compliant — lockers, bench, tile floor; no chrome, no text, reads as a locker room |
| `int_rockys_apartment` | n/a | compliant on points 1-3 and 5 — one-room interior, goldfish bowl, worn armchair, torn mattress cover, matches the beats' description of a run-down apartment. **Minor note:** a jacket on the floor is rendered as a small solid-black filled shape rather than pure outline — a very localized departure from "exactly two tones... outline only," not the greyscale-shading failure mode D-09 targets, and not blocking. |

**Verdict: every sampled character slot now passes all five points after the fix.**
No location regressed. The one residual minor-quality note (a single filled black
garment shape in `int_rockys_apartment`) is left unfixed — it is not one of the three
D-09 failure modes (greyscale shading, storyboard chrome, drawn-in words), the plan's
own instruction is to ship the best first pass rather than chase perfection, and a
single small filled shape does not compromise the slot's use as an establishing view.

## Slots not individually re-inspected this pass

`int_trolley`, `ext_rockys_apartment`, `int_rockys_hallway`, `fighter_1`/`fighter_2`/
`fan`/`announcer` (all share `generic_minor_character`'s art, already checked). No
reason to expect these differ in kind from the sampled set — same prompt template,
same `--force` regeneration pass, same style block. Flagged here rather than silently
assumed compliant, consistent with this plan's own instruction that the review "must
say what was actually looked at, not that a check was run."

## Disposition

**Approved.** All four originally-required samples plus every additional bespoke
character checked pass all five D-09/PROJECT.md points on the second (force-regenerated)
pass. The `int_rockys_apartment` filled-shape note is logged to `.planning/WINDOWS.md`
as a non-blocking visual-quality item, not treated as a failed gate. Per this plan's own
ceiling ("a second regeneration pass is the sensible ceiling before the 2026-09-09
deadline"), no further iteration was performed. The manifest and art on disk after the
`--force` run are what Task 3's STATE.md contract and Phase 4 both point to.
