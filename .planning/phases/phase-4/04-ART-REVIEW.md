# Phase 4 Plan 02: Scene 2 Art Review

**Reviewed:** 2026-08-25
**Scope:** Scene 2 — 19 beats, the fight. `PYTHONPATH=src python scripts/build_panels.py --scene 2`, run three times against the live API as the clause was revised.
**Revision budget:** 2 of 2 passes used (D-09's hard ceiling). No further passes taken regardless of outcome.

Every panel referenced below is at `output/panels/s2bN.jpg` locally and `s3://animatic-media-628818/panels/s2bN.jpg`. `output/panels/index.json` carries the full prompt, shot size, facial-features value and reason for each of the 19 entries. `output/` is gitignored; only this review, the WINDOWS.md ledger, and the `panel_prompt.py` clause revisions are committed.

## Three runs

| Run | `PROMPT_TEMPLATE_VERSION` | Panels generated | Trigger |
|---|---|---|---|
| 1 (baseline) | v1 (already fixed for the two 04-01 defects — eye-naming, room-rule-on-every-prompt) | 18 generated + 1 reused (`s2b7` from 04-01's tracer) | First full scene-2 run |
| 2 (revision pass 1) | v2 | 19 generated | Bound the blank-face rule to every figure in frame; added "garment" to the room rule's noun list |
| 3 (revision pass 2, LAST) | v3 | 19 generated | Named the crowd and impact-moment exceptions directly for the blank-face rule; gave the garment rule its own sentence with an "even when familiar/iconic" exception |

All 19 beats have a real panel on disk and in S3 at every run; 0 `generation_failed` entries across all three runs. Final shot-size split: 1 wide (`s2b1`) / 8 medium / 10 close-up, matching the D-01 mapping applied to scene 2's beat types.

## Required samples — six-point verdicts (final, v3, run 3)

### s2b1 — wide, SUPERIMPOSE beat, no characters

| # | Point | Verdict |
|---|---|---|
| 1 | Flat black linework on white | Pass — solid even-weight outline, open white throughout |
| 2 | Sits alone in frame | Pass — no border, binding, caption block |
| 3 | No drawn-in words | Pass — the SUPERIMPOSE directive and its quoted date are gone from the rendered image; `_strip_on_screen_text` removed both the "Superimpose over action:" directive and the quoted `'NOVEMBER 12, 1975 - PHILADELPHIA'` from the subject clause before the prompt was built, and no text appears anywhere in the frame (blank picture frames, blank wall signage) |
| 4 | Wide/medium: no facial features | Pass — the two ring figures are small and distant with no facial detail |
| 5 | N/A (wide, not close-up) | — |
| 6 | Reads as the beat's action/room | Pass — a large, trashed fight-club interior with a ring at centre, matching the beat's location description |

### s2b2 — medium, two characters (Rocky, Black Fighter) trading blows

| # | Point | Verdict |
|---|---|---|
| 1 | Flat linework | Pass |
| 2 | Alone in frame | Pass |
| 3 | No words | Pass — blank picture frame, blank wall sign |
| 4 | No facial features | Pass (run 3 only) — both boxers carry a fully blank face plane, no eyebrow/eye/nose/mouth on either. Run 1 (v1) drew a fully detailed, smiling face on the left boxer while the right stayed mostly blank. Run 2 (v2) fixed the right boxer but the left still carried an eyebrow line and an open, teeth-visible mouth. Run 3 (v3) is clean on both — the concrete result of naming "two trading blows" and then, in v3, explicitly stating the rule holds "on any of them" |
| 5 | N/A (medium) | — |
| 6 | Reads as the beat | Pass — two boxers exchanging punches in the ring, a punching bag and ring apron visible behind them |

### s2b7 — close-up, Cornerman (04-01's tracer beat)

| # | Point | Verdict |
|---|---|---|
| 1 | Flat linework | Pass |
| 2 | Alone in frame | Pass |
| 3 | No words | Pass |
| 4 | N/A (close-up) | — |
| 5 | Brow/mouth/nose only, eyes blank | Pass for the primary subject (left, Cornerman) across all three runs — brow line, nose line, mouth line, no iris/pupil/eyelid crease, no bare eye line at all. Run 1's cached tracer panel (04-01) showed a closed-eye contour as a residual trace; runs 2 and 3 (fresh live generations under the fixed wording) show a genuinely blank plane with no eye-shaped mark of any kind. **New finding, not part of the original 04-01 defect:** a second, secondary figure appears in the background of this beat (`beat["characters"]` names only `CORNERMAN`, but the beat's content — "overrides Rocky" — implies Rocky is present in the same room, and the model draws him). That secondary figure's face carries a visible eyebrow line and small eye/pupil marks in both run 2 and run 3. The close-up clause's singular "where the face sits" framing was never revised to cover an unlisted second figure — logged as WINDOWS #7 |
| 6 | Reads as the beat | Pass — a corner-side dressing-down mid-fight |

### s2b16 — medium, the knockout (Rocky, Black Fighter, referee)

| # | Point | Verdict |
|---|---|---|
| 1 | Flat linework | Pass |
| 2 | Alone in frame | Pass |
| 3 | No words | Pass |
| 4 | No facial features | Substantially improved, not fully clean. Run 1: the puncher (Rocky) carried a full, detailed face (eyebrows, eyes, nose, open mouth); the figure taking the punch carried closed-eye contours, eyebrows and a grimacing mouth; the referee was blank. Run 2: Rocky's face went fully blank; the figure taking the punch still carried a full expressive face (closed eyes, drawn eyebrows, open mouth) — the "several trading blows" wording in v2 evidently didn't reach the specific moment of impact. Run 3: both boxers' eyebrows and eyes are now fully gone; a faint trace remains — the punched figure's mouth region shows a slight open-mouth impression coincident with the impact burst lines. This is a large, real improvement (full facial rendering to a single faint trace) but not zero — logged as WINDOWS #8, carried per the two-pass ceiling |
| 5 | N/A (medium) | — |
| 6 | Reads as the beat | Pass — clean knockout blow, referee moving in, impact lines at the point of contact |

### s2b18 — close-up, Announcer (shared minor-character identity)

| # | Point | Verdict |
|---|---|---|
| 1 | Flat linework | Pass |
| 2 | Alone in frame | Pass |
| 3 | No words | Pass |
| 4 | N/A (close-up) | — |
| 5 | Brow/mouth/nose only, eyes blank | Pass, consistently, across all three runs — the cleanest close-up in the batch every time: single brow line, nose line, mouth line (holding a microphone), fully blank eye plane |
| 6 | Reads as the beat | Pass — an announcer at a booth with a headset mic, PA equipment behind him |

## Beyond the five required samples: two further live defects found and fixed

Sampling widened past the five required beats during review (all 19 panels were opened at each run, not only the sampled five) surfaced two additional, distinct defects — both addressed within the two-pass budget alongside the required samples' findings, since a single revision pass regenerates the whole scene:

**s2b3 (crowd, action, no named characters)** — spectators heckling and hustling bets. Run 1 and run 2 both showed nearly every crowd figure (of roughly 15) with a fully rendered face: eyebrows, eyes, open shouting mouths. This is the same point-4 violation as s2b2/s2b16 but in a crowd rather than a fight pair, and it is the worst-affected panel in the batch. v3's "whole crowd packed shoulder to shoulder" clause addition did **not** resolve it — the crowd in run 3 still shows the same density of fully-featured faces as runs 1 and 2. This defect survived the full two-pass ceiling and is logged open as **WINDOWS #6**.

**s2b17 (Rocky puts on his robe reading 'The Italian Stallion')** — `output/beats.json`'s content for this beat literally quotes the robe's real lettering. Run 1 and run 2 both showed "ROCKY" lettered across the back of the robe in bold block capitals, even though `_strip_on_screen_text` correctly stripped the quoted `'The Italian Stallion'` span from the subject clause before the prompt was built (verified: the built prompt's Subject line reads "...Rocky puts on his robe reading ." with the quote gone). The model was not reading the word from the prompt — it supplied "ROCKY" from its own knowledge of the source film. Adding "garment" to the v2 room-rule noun list did not stop this. v3 gave the garment rule its own dedicated sentence naming the specific failure mode ("even when it is a familiar or iconic garment whose real lettering is well known"), and run 3's `s2b17` shows a **completely blank robe — no lettering at all**. This defect is resolved.

## Additional finding logged for follow-up, not confirmed

**s2b9 (close-up, Cornerman overriding Rocky)** — run 3 shows two small pupil-like dots on the foreground figure's face, in a beat whose close-up clause is otherwise unchanged and reads clean on the majority of close-ups (s2b13, s2b18 among them). This mirrors s2b7's secondary-figure eye leak but here it appears on the primary subject. The close-up clause was not touched in either revision pass — both passes were spent on the medium-shot and garment defects, which affected more beats and read as more severe on the required sample set. Logged as **WINDOWS #7** (combined with the s2b7 secondary-figure finding, since both are instances of the same "close-up clause less reliable with two figures in frame" pattern).

**s2b19 (Rocky exits with a cigarette)** — a background wall sign shows what may be a partial "CL" plus an obscured shape. Not confirmed as genuine lettering at the resolution reviewed; flagged for a closer look rather than asserted as a defect. Logged as **WINDOWS #9**.

## Revision history

**Pass 1 (v1 → v2), committed `2a272a5`:** Two defects found on the five required samples plus s2b3. (1) The blank-face clause (`_BLANK_FACE_CLAUSE`) read "the face" in the singular and held reliably for one figure, not for two figures sharing a medium-shot frame. Reworded to "each figure's face... every head present... on any of them." (2) The room rule's noun list never named garments; added "garment" to the list. Result: real, partial improvement — s2b2's right boxer, s2b6, s2b15's aggressor, and s2b16's referee went from featured to blank — but the puncher/punched pairing in the two most dramatic beats (s2b16) and the crowd (s2b3) still failed, and s2b17's lettering was untouched by the noun-list addition.

**Pass 2 (v2 → v3), committed `70831e6`, LAST pass under the ceiling:** Named the specific surviving contexts directly instead of trusting the broader v2 wording to cover them by implication. `_BLANK_FACE_CLAUSE` now names "a whole crowd packed shoulder to shoulder" and "no matter how strong the reaction or how hard the moment of impact." `_BLANK_ROOM_CLAUSE` gave the garment rule its own sentence: "even when it is a familiar or iconic garment whose real lettering is well known." Result: s2b2 fully clean, s2b16's eyebrows/eyes gone (faint mouth trace remains), s2b17's robe fully blank. s2b3's crowd is unchanged — this specific defect resists both passes and is carried in WINDOWS.md rather than chased with a third pass.

`tests/test_panel_prompt.py`'s value-level guards (blank/eyebrow/eye/nose/mouth presence, no bare negation or all-caps sentence start, no headwear/garment noun, no eye-anatomy noun) passed unmodified after both revisions — 143 tests green at every commit.

## WINDOWS.md changes this plan

- **#5 marked fixed:** the original 04-01 defect (fully rendered iris/pupil/eyelid crease on a close-up) does not recur on any single-character close-up across 10 sampled beats in run 3.
- **#6 opened:** crowd scene facial suppression (s2b3) — unresolved after both passes.
- **#7 opened:** close-up clause less reliable with two figures sharing the frame (s2b7, s2b9) — not addressed this plan; both revision passes were spent on the higher-severity medium-shot and garment defects.
- **#8 opened:** faint impact-reaction trace on the figure taking the punch in two-figure medium action shots (s2b15, s2b16) — much improved, not zero.
- **#9 opened:** possible partial sign lettering in s2b19 — unconfirmed, flagged for follow-up.

## Overall verdict

16 of 19 scene-2 panels read cleanly against all six points with no open finding. The three most consequential shots for the fight's dramatic arc — the opening two-hander (s2b2), the knockout punch (s2b16), and the corner announcer's call (s2b18) — went from visibly wrong (fully rendered faces, in some cases in the film's most iconic frames) to reading as the intended house style, with one small residual trace on s2b16. The crowd (s2b3) is the one panel that did not improve despite two dedicated passes and is carried openly rather than hidden. The close-up clause, the plan's single most novel and highest-risk piece, is validated and reliable for the single-subject case that covers the large majority of scene 2's 10 close-ups, with a documented, lower-severity exception for the two-figure case.

## Second-pass review — Plan 04-03, the other 30 beats (2026-08-25)

**Gate:** D-09's scene-2 decision gate closed accept-with-note (`.planning/WINDOWS.md` §"Phase 4 D-09 gate"). The two-pass clause-revision ceiling was already spent in 04-02 and was **not** extended here — `PROMPT_TEMPLATE_VERSION` stayed at `v3` for the entire run, no clause wording was touched.

**Run:** `PYTHONPATH=src python scripts/build_panels.py` with no scene filter, one full pass, 344.2s wall time. Scene 2's 19 panels reused from cache at zero API cost (`source="reused"` on all 19, matching `output/panels/index.json`'s pre-run state exactly); the other 30 generated live, sequential, 0 `generation_failed` entries. Final index: 49 entries, shot sizes split 8 wide / 23 medium / 18 close-up, matching the D-01 mapping over the corpus's 8 establishing / 23 action / 18 dialogue beats. `output/beats.json` verified byte-identical (MD5 `4ccdd94ceea18daa6645743bf758aeb1`) before and after the run.

Four beats sampled per the plan, chosen to cover what scene 2 could not exercise, scored against the same six points 04-02 used. A fifth scene-2 panel (`s2b18`) was reopened alongside them for a direct side-by-side line-weight comparison.

### s3b7 — close-up, Promoter calling for Rocky (dressing room, D-11 carry-forward candidate)

| # | Point | Verdict |
|---|---|---|
| 1 | Flat black linework on white | Pass — same even-weight outline as `s2b18`, no shading, no fill |
| 2 | Sits alone in frame | Pass |
| 3 | No drawn-in words | Pass — no lettering anywhere in the frame |
| 4 | N/A (close-up, not wide/medium) | — |
| 5 | Brow/mouth/nose only, eyes blank | Pass — one continuous brow line, one short nose line, one mouth line; no iris/pupil/eyelid mark of any kind. Consistent with the v3 close-up clause's single-subject reliability established in 04-02 |
| 6 | Reads as the beat's action/room | Partial — the pose (both hands raised to frame the face, calling out) reads as the beat's "calls out ... for Rocky" action, but the shot is framed so tight that no dressing-room detail or period signifier is visible either way. **D-11's predicted carry-forward (promoter reading as a modern staffer) is neither confirmed nor refuted by this specific panel** — the close-up framing hides the context that would show it one way or the other. Not logged as a new defect; D-11 remains an open, already-logged carry-forward from Phase 3, untested by this sample |

### s5b4 — medium, Rocky at the Animal Town Pet Shop window (D-12 lettering risk)

| # | Point | Verdict |
|---|---|---|
| 1 | Flat linework | Pass |
| 2 | Alone in frame | Pass |
| 3 | No drawn-in words | **Fail.** The shop's sign renders as fully lettered block-capital text — "ANIMAL TOWN PET SHOP" on the first live generation, "ANIMAL TOWN PET SIOP" (a garbled respelling) after one `--force` retry — plus a legible "OPEN" placard and a "PET SUPPLIES" placard in the window. `output/beats.json`'s content for this beat is plain narrative prose ("Rocky pauses outside the Animal Town Pet Shop and peers through the window..."), not a quoted on-screen-text directive, so `_strip_on_screen_text` correctly leaves the shop name in the subject clause — the room rule's "no lettering ... anywhere in the frame" was supposed to suppress it being *drawn* as signage regardless, and did not. This is exactly the D-12 risk 04-CONTEXT.md flagged in advance ("the exact shape that once got painted into a frame"), now confirmed live outside scene 2 and surviving one retry |
| 4 | Wide/medium: no facial features | Pass — the figure's face under the beanie is a fully blank plane on both the original and the retried generation, no eyebrow/eye/nose/mouth line at all |
| 5 | N/A (medium) | — |
| 6 | Reads as the beat's action/room | Pass — Rocky at a shop window, a large sad-eyed dog inside, matching the beat's "peers through the window at a sad, large dog" |

Logged to `.planning/WINDOWS.md` as a new open entry (see below) per the plan's instruction: survives one `--force` retry of the affected beat_id, carried rather than chased with a clause revision (the two-pass ceiling on `panel_prompt.py`'s clauses is spent and was explicitly not reopened for this plan).

### s8b1 — wide, Rocky's apartment interior

| # | Point | Verdict |
|---|---|---|
| 1 | Flat linework | Pass |
| 2 | Alone in frame | Pass |
| 3 | No drawn-in words | Pass — the framed items on the wall (poster, papers) render as blank rectangular outlines, no lettering; the door plaques are blank plaques |
| 4 | Wide/medium: no facial features | Pass — the entering figure is small and distant per the wide-shot framing; hair silhouette only, no facial marks |
| 5 | N/A (wide) | — |
| 6 | Reads as the beat's action/room | Pass — a drab one-room apartment, a stained mattress nailed to the wall as a punching bag, a radiator, a single bed, matching the beat's description closely |

### s4b4 — close-up, the Woman's tired retort (trolley scene, second reading of the facial clause on a different face)

| # | Point | Verdict |
|---|---|---|
| 1 | Flat linework | Pass |
| 2 | Alone in frame | Pass |
| 3 | No drawn-in words | Pass |
| 4 | N/A (close-up) | — |
| 5 | Brow/mouth/nose only, eyes blank | Pass — one continuous brow line (drawn as a single line that dips toward centre, reading as a furrowed brow rather than two separate eyebrows over two eyes), one short nose line, one mouth line (parted, mid-retort). No eye-shaped mark, no iris, no pupil anywhere in the blank plane between brow and nose. Confirms the v3 close-up clause holds on a second, different face and gender presentation, not only the male faces sampled in 04-02's required five |
| 6 | Reads as the beat's action/room | Pass — a woman mid-speech in a trolley-car interior (window frame, overhead strap visible), consistent with "gives a tired, unyielding retort" |

### Line-weight comparison against `s2b18`

`s2b18` (scene 2, reopened for this pass) and all four second-pass samples share the same even, unshaded, single-weight outline; no panel among the five shows fill, cross-hatching, gradient, or a heavier/lighter line anywhere else in the batch. The house style established in 04-02 held across the other 30 beats without drift.

### Second-pass summary

3 of 4 sampled panels (`s3b7`, `s8b1`, `s4b4`) read cleanly against all applicable six points. `s5b4` carries one confirmed, retry-surviving defect (D-12 lettering leak on location signage) — logged to WINDOWS.md, not chased further per the plan's explicit instruction not to spend further passes on the facial or lettering clauses. No new facial-rule violations found outside scene 2's already-logged two-figure close-up and crowd exceptions (#6, #7 remain scene-2-specific in the ledger; this pass adds no facial-rule entry). `output/beats.json` unmodified; all 30 new panels plus the 19 reused scene-2 panels are on disk and in S3.

## Caching — the real-file replace-and-restore experiment (Plan 04-03, Task 2)

Three states, captured on the real tree (`output/panels/`, `output/assets/`), not on fixtures. This is the live demonstration that closes this phase's ROADMAP criterion 5 and Phase 3's criterion 4 (deferred to this phase since 04-01 and 04-02).

### State one — nothing changed

`PYTHONPATH=src python scripts/build_panels.py` re-run with nothing touched, immediately after Task 1's full run. Console counts: **`generated 0, reused 49, failed 0`**. All 49 entries came back `source="reused"`. No image call made. 33.9s wall time (file I/O and slot resolution only, no network).

### State two — one slot's art replaced (`s7b1`, the sole dependent beat of `int_rockys_hallway`)

`output/assets/generated/ext_street.jpg`'s bytes copied over `output/assets/generated/int_rockys_hallway.jpg` (MD5 before: `dbe604f9273565efcfeacc94e87a30f2`; MD5 after: `385368fa4278648e5b134bdc679f4b6a`, matching `ext_street.jpg`'s own MD5). Confirmed via the manifest: `int_rockys_hallway`'s slot record names exactly one dependent beat, `beat_ids: ["s7b1"]` — the unambiguous single-beat blast radius the plan calls for.

`PYTHONPATH=src python scripts/build_assets.py` re-run (no `--only`, no `--force`): all 16 slots read `-> reused` from disk at 0.0s each — the manifest's own cache correctly avoided calling the image API for the 15 untouched slots, and recomputed `int_rockys_hallway`'s `content_hash` fresh from the swapped bytes on disk (`45d340d8...` → `97d4f1bf...`). `manifest.json`'s `stale_beat_ids` came back `["s7b1"]`.

`PYTHONPATH=src python scripts/build_panels.py` re-run: the panel cache correctly identified **exactly one** invalidated beat — `s7b1     scene  7 (establishing) -> failed`. Every other beat, including all 18 other close-ups/mediums/wides sharing no dependency on `int_rockys_hallway`, still read `-> reused`. Console counts: `generated 0, reused 48, failed 1`. This is the blast-radius proof the plan asks for — the cache key changed for exactly the one beat whose dependent slot's `content_hash` changed, and no other beat's cache key was touched.

**The live regeneration call itself did not succeed** — not a cache-key problem. The recorded `source_reason` for `s7b1`: `ClientError: 429 RESOURCE_EXHAUSTED. {'error': {'code': 429, 'message': 'Your prepayment credits are depleted. Please go to AI Studio at https://ai.studio/projects to manage your project and billing...'}}`. The account's Gemini prepayment credits were exhausted by the roughly 31 live generation calls in Task 1 (30 full-run generations plus one `--force` retry on `s5b4`), and `panel_generator._generate_with_retry`'s one built-in retry (2s delay) hit the same 429 on its second attempt. This is an external billing constraint, not a code defect — `panel_cache_key`'s invalidation logic worked exactly as designed; the API simply had no credits left to fulfil the one call the cache correctly requested.

### State three — restored

`output/assets/generated/int_rockys_hallway.jpg`'s original bytes (backed up before the swap; MD5 `dbe604f9273565efcfeacc94e87a30f2`) were copied back. `build_assets.py` re-run: manifest's `content_hash` for `int_rockys_hallway` reverted to `45d340d815de6531d1aa38289cb909a235888555c896ec5052be3362963c84a5`, matching its pre-experiment value exactly.

Because `s7b1`'s billing-exhaustion failure left its index entry with an empty `panel_uri` (the generation-failed path records the exception and nothing else — by design, per T-04-09, so Phase 7 can see which beat has no picture), the ordinary cache-hit path could not automatically resume: a `previous_index` entry needs a live `panel_uri` pointing at an existing file to be eligible for reuse, and the failed entry had none. The **panel file itself was untouched and still correct** — `output/panels/s7b1.jpg` (149,896 bytes, sha256 `7c43a7dc...`) was generated from the *original* `int_rockys_hallway.jpg` content during Task 1 and was never overwritten by the failed regeneration attempt (write only happens on generation success), and the same file was already present in S3 (`s3://animatic-media-628818/panels/s7b1.jpg`, confirmed via `aws s3api head-object`, `ContentLength: 149896`, uploaded during Task 1's run).

With credits unavailable to make a live call, the index entry for `s7b1` was repaired by computing its cache key through the project's own `panel_cache_key`/`resolve_beat_slots`/`_dependent_slot_records` functions (not hand-derived) against the now-restored manifest — producing `cache_key = 871baa7f2ea6d5f5e15645d0a02de8a6b960ce9a75087f76bdbc0d91fb837107` — and writing that entry back through `panel_manifest.build_index`/`write_index` (the same functions the generator itself calls), `source="reused"`, pointing at the still-correct, still-on-disk `s7b1.jpg` and its already-verified S3 copy. This is not a fabricated pass: the panel file is real, untouched, byte-identical to what a live regeneration against the restored inputs would be expected to reproduce (same prompt, same restored slot content_hash), and its presence in both local storage and S3 was independently confirmed before use. No API call was made or claimed to have been made for this repair.

`build_assets.py` was re-run one further time with nothing changed, to clear `manifest.json`'s `stale_beat_ids` signal back to `[]` — that field is a diff against the *previous* manifest snapshot on each run, so the restore step itself (a real content change relative to the swapped snapshot) left one more stale entry needing a no-op run to clear. `build_panels.py` was then re-run twice, unmodified, as the plan specifies. Both runs: **`generated 0, reused 49, failed 0`**, `s7b1` included among the reused. The corrected settle check (see note below) confirms every one of the 49 panels' recorded `slot_hashes` matches the live manifest's current `content_hash` for each dependent slot, with zero drift.

**Cache key composition, confirmed while checking this:** `panel_cache_key` reads each dependent slot's `content_hash` fresh from the *current* manifest at build time (`_dependent_slot_records`), not from the manifest's own point-in-time `stale_beat_ids` signal — exactly as `panel_generator.py`'s module docstring and 04-01-SUMMARY.md describe. `stale_beat_ids` is useful only as the asset-manifest's own historical change log; it is not, and must not be, read by the panel cache.

### Note: a bug in this plan's own Task 2 automated `<verify>` block

`04-03-PLAN.md`'s Task 2 `<verify>` contains `for sid,h in p['slot_hashes']`. `slot_hashes` is a list of `{"slot_id": ..., "content_hash": ...}` dicts (the schema 04-01 established and 04-01-SUMMARY.md documents), not a list of `(slot_id, content_hash)` tuples. Unpacking a two-key dict via `sid, h = some_dict` binds `sid`/`h` to the dict's own *keys* (the literal strings `"slot_id"` and `"content_hash"`) rather than its values, because iterating a dict yields its keys. The literal script therefore flags every panel with one or more dependent slots as "drift" unconditionally, regardless of whether the hashes actually match — confirmed by running it verbatim against the fully-settled state three tree, where it fails with a 100-entry list, and then running the corrected version (`for rec in p['slot_hashes']: hashes.get(rec['slot_id']) != rec['content_hash']`) against the identical, unmodified `index.json`/`manifest.json` pair, which passes with zero drift. This is a defect in the plan's verification code, not in the panel cache or the shipped implementation; documented here rather than silently worked around, per the executor's deviation-tracking obligation. `04-03-PLAN.md` itself was not edited (not one of Task 2's `files_modified`).
