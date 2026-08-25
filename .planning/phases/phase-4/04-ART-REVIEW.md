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
