# Steering the animatic — workplan

Five ways to redirect a generated cut without regenerating it from scratch.
Decided 2026-08-25 with the developer; the decisions are recorded per feature
so a later reader can tell what was chosen from what was inferred.

The organising idea: **the pipeline already knows how to invalidate exactly
what changed.** Panel cache keys include their slot content hashes, the
shot-source seam resolves by filename priority, and `state.json` reports what
a rebuild would produce. Every feature below is a new *input* to machinery that
already exists, not new machinery.

---

## The constraint that shapes all of it

**Google's per-model daily cap is 100 requests.** A cold start already spends
62 image calls and 50 TTS calls. That is the budget these features draw on.

| Action | Image calls | Notes |
|---|---:|---|
| Swap Rocky's model sheet | **31** | a third of the daily image budget |
| Swap `black_fighter` or `promoter` | 5 | |
| Swap any of the other six | 1–4 | |
| Extend a beat (longer) | **0** | re-assembly only |
| Mark a panel edited | **0** | the file IS the result |
| Text-edit one panel | **1** | |
| Splice a daily over a beat range | **0** | the file is the result |
| Re-assemble the cut | 0 | ~30s of ffmpeg |

**Consequence for the UI:** it must show the remaining daily budget and the
cost of an action *before* the action, not discover the wall halfway through.
Phase 5 already learned this the expensive way — a run that hit the cap turned
a complete index into a half-failed one.

---

## A. Character model sheets

**Decided:** point a character at a folder of representative images; those
become the character's art; the animatic re-renders showing the impact.

**The catch, and the resolution.** Replacing the slot art alone changes
nothing today: panels are generated from **text only** (D-08, held through
Phase 4). The art file exists and nothing reads it. So this feature requires
lifting D-08 — panels condition on the slot plates their beat uses.

That is not speculative. Backlog **S-03 proved it on 2026-08-24**: feeding the
`black_fighter` character plate and the `int_blue_door_fight_club` location
plate plus a prompt returned one composed panel carrying the character's build
and clothing and the room's ring, benches and fittings
(`output/experiments/refcond_panel.jpg`).

**Already built, needs no work:**
- `assets/reference-art/<slot_id>/` adopts a named folder (tested, unexercised)
- `panel_cache_key` already hashes each dependent slot's `content_hash`, so
  replacing a plate invalidates exactly the panels that use it and nothing else
- `stale_beat_ids` already reports which those are

**Work:**
1. Condition panel generation on the beat's slot plates (lift D-08).
2. Re-verify the facial rule under conditioning — **the spike panel had facial
   features**, and Phase 4 spent two revision passes eliminating them. The
   clauses are prompt-side; a seed image can override them. This is the risk
   in this feature, not the plumbing.
3. A model-sheet picker: the developer curates folders; a demo visitor
   *selects* one. Never an arbitrary upload from the public demo.

**Open question for later:** how many images per folder, and whether they are
composited into one plate or passed as multiple reference images. S-03 used
two separate plates successfully.

---

## B. Extend a beat — longer, not denser

**Decided:** the same beat holds more screen time. Not a re-parse into more
beats.

**The rule, already settled as S-02:** *a stretch ADDS time; it must not
re-time other beats.* Today `fit_scene_to_budget` scales every beat in a scene
to hit the page target, so lengthening one silently shortens its neighbours —
beats the developer had already approved would change under them.

**Work:**
1. A per-beat duration override that survives re-parsing, stored outside
   `beats.json` so a re-parse does not discard it and `beats.json` stays a
   faithful record of what the script says.
2. `shot_secs` resolution honours it, above the audio floor — a shot may be
   held longer than its speech, never shorter.
3. Re-assemble. **Zero generation calls.**

**Known risk, worth surfacing in the UI:** a still held for 15 seconds reads
as dead air. The beats worth extending are usually the ones that should also
get motion, and motion is capped at 4 beats. Offer them together.

---

## C. Mark a panel as edited

**Decided:** hand-edit a panel — paint out a turtle, add a sign — and have the
cut use it, permanently.

**The mechanism already exists in another form.** `shot_sources.resolve_shot`
resolves a beat's *picture* by filename priority: footage, then motion, then
panel. This is the same idea one level down, for the panel itself.

**Work:**
1. `assets/edited-panels/<beat_id>.<ext>` outranks the generated panel.
2. An edited panel is **immune to regeneration** — a prompt-version bump, a
   model-sheet swap, a `--force` must not silently overwrite hand work. It is
   the one artifact in this pipeline a human made.
3. The index records `source: edited` with the file it came from, so the cut
   can say how much of itself is hand-corrected — the same way it reports how
   much is real footage.

**Zero generation calls.** The file is the result.

---

## D. Text-driven panel edit

**Decided:** describe a change — *"s8b5 is the character singing into a
hairbrush alone in the room. No other people."* — and have the panel redrawn
**in place**, keeping the room, framing and line weight.

**Work:**
1. Send the existing panel plus the instruction to the image model.
2. Write the result through C's edited-panel path, so it is equally immune to
   later regeneration and equally visible in the index.
3. Keep the original: an edit that comes back worse must be revertible without
   a regeneration call.

**One image call per edit.**

**Prompt-side risk, already paid for once:** the instruction as the developer
would naturally write it — *"no other people"* — is a **negation**, and this
project's most expensive lesson is that negations get rendered. "NO FACIALS"
was once lettered into a frame. The UI must not pass raw negations to the
model; it should restate them positively (*"the room holds one figure alone"*)
and show the developer what it actually sent.

---

## E. Dailies — splice a take across a beat range

**Decided:** an MP4 in a `dailies/` folder is spliced in over a **range** of
beats, plays its **own full length**, and carries its **own production sound**.

Those three decisions hold together, and it is worth saying why, because the
first two look like they conflict. A daily that plays whole no longer matches
the runtime of the beats it covers — five beats totalling 26.4s replaced by a
22-second take makes the cut 4.4 seconds shorter. That would desync the
synthesised audio, *except* the daily brings its own sound, so the picture and
audio arrive together and the synthesised clips for that span are simply not
used. Picture and sound move as one piece.

This is a different shape from the footage swap already built. That is one
file, one beat, fixed duration. A daily is one file, N beats, its own duration.

**Work:**
1. Read the range from the filename — `s2b5-s2b9.mp4`. The beat numbers come
   from the FILENAME, never from the footage; PROJECT.md lists inferring them
   as an explicit non-goal, and that rule does not change because the unit did.
2. A new shot kind, `daily`, at the top of the priority ladder in
   `shot_sources` — above single-beat footage, which is above motion, above the
   panel. One place decides, as it does now.
3. Assembly emits **one segment** for the whole range rather than one per beat,
   using the daily's own audio stream.
4. `state.json` reports the runtime delta plainly: the cut is no longer the
   length the beat list says it is, and a manifest that does not say so is
   lying. Every beat in the range reports `state: daily` and names the file and
   the span.
5. Overlaps are refused, not resolved: two dailies covering `s2b5-s2b9` and
   `s2b8-s2b12` is a mistake to report, not a precedence puzzle to guess at.

**Zero generation calls.** As with footage, the file is the result.

**Open question, deferred until there are real takes:** whether a daily should
be able to cover a range that crosses a scene boundary. Nothing prevents it
technically; whether it means anything editorially is a question for when it
happens.

---

## Sequencing

| | Feature | Calls | Depends on |
|---|---|---:|---|
| **11** | C — edited panels outrank generated | 0 | nothing |
| **12** | B — beat duration override | 0 | nothing |
| **13** | E — dailies spliced over a beat range | 0 | nothing |
| **14** | D — text-driven edit | 1/edit | 11 |
| **15** | A — model sheets + panel conditioning | up to 31 | 11 |
| **16** | UI for all five, with a visible quota budget | 0 | 11–15 |

**11, 12 and 13 first because they cost nothing to run and nothing to undo.** They
also make 13 and 14 safe: once a hand-edited panel is immune to regeneration,
a model-sheet swap that goes wrong cannot destroy earlier work.

**15 last of the generation features** because it is the only one that can
break the facial rule Phase 4 paid two revision passes for, and because it is
the only one that can spend a third of a day's image budget in a single click.

---

## What this does not include

- **Re-parsing a scene into more beats** (the other reading of "extend").
  Deliberately excluded per the decision above; S-02 remains in the backlog
  with its rule intact if it is ever wanted.
- **Public upload of reference images.** The developer curates the folders; a
  demo visitor selects from them. Anonymous upload of arbitrary images plus a
  31-call re-render is a quota-exhaustion button.
