---
schema_version: 1
open_count: 5
waived_count: 0
fixed_count: 4
total_count: 9
last_updated: 2026-08-25T08:13:11.083Z
---

# Broken Windows Ledger

> Cross-phase defect register. With `workflow.windows_enforce` enabled, `/gsd-ship` blocks while `open_count > 0`.
> Waive with `gsd-tools windows waive <id> "<reason>"` (reason required).
> Mark fixed with `gsd-tools windows fixed <id>`.

| id | phase | kind | file | line | description | status | reason | recorded_at | resolved_at |
|----|-------|------|------|------|-------------|--------|--------|-------------|-------------|
| 1 | 3 | stub | output/assets/generated/generic_minor_character.jpg |  | Model drew a detailed face on the generic minor character art instead of the instructed blank white head-shape (PROJECT.md no-facial-features rule) | fixed |  | 2026-08-25T00:31:49.957Z | 2026-08-25T01:30:41.849Z |
| 2 | 3 | stub | output/assets/generated/promoter.jpg |  | Model drew a detailed face on the promoter character art instead of the instructed blank white head-shape (PROJECT.md no-facial-features rule) | fixed |  | 2026-08-25T00:31:54.885Z | 2026-08-25T01:30:41.938Z |
| 3 | 3 | stub | output/assets/generated/ext_street.jpg |  | Location art drew one sleeping figure on the sidewalk despite the peopleless-establishing-view instruction | fixed |  | 2026-08-25T00:31:57.115Z | 2026-08-25T01:30:48.450Z |
| 4 | 3 | stub | output/assets/generated/int_rockys_apartment.jpg |  | A jacket on the floor renders as a small solid-black filled shape rather than pure outline linework, a minor departure from the two-tone (white ground, black outline) style rule; not one of the D-09 chrome/shading/text failure modes | open |  | 2026-08-25T01:30:54.458Z |  |
| 5 | 4 | stub | output/panels/s2b7.jpg |  | Close-up facial clause (D-05, [ASSUMED]) failed on first live generation: the model drew a fully rendered eye (iris, pupil, eyelid crease) instead of leaving it part of the blank plane; brow/mouth/nose lines were drawn as intended. Flagged for 04-02's scene-2 tracer batch to revise the wording. | fixed |  | 2026-08-25T06:59:33.948Z | 2026-08-25T08:12:50.891Z |
| 6 | 4 | stub | output/panels/s2b3.jpg |  | Crowd scene (medium shot, ~15 figures) still shows fully rendered faces (eyebrows, eyes, open shouting mouths) on nearly every figure after both 04-02 revision passes; the blank-face clause's v3 'whole crowd packed shoulder to shoulder' exception did not suppress it. Two-pass ceiling reached (D-09) — carried, not chased further. | open |  | 2026-08-25T08:12:58.165Z |  |
| 7 | 4 | stub | output/panels/s2b9.jpg |  | Close-up clause holds reliably for a single-character close-up but is less reliable with two characters sharing the frame: visible eye pupil dots appeared on the foreground character in s2b9, and on the secondary (non-primary) character in s2b5 and s2b7, despite the same unmodified close-up wording that reads clean on single-character close-ups (s2b13, s2b18, and others). Not touched by 04-02's two revision passes (both spent on the medium-shot and garment defects); carried, not chased. | open |  | 2026-08-25T08:13:06.843Z |  |
| 8 | 4 | stub | output/panels/s2b15.jpg |  | Residual reaction marks (a closed/squinting eye line, a slightly open mouth) remain on the figure absorbing the punch in two-figure medium action shots (s2b15, s2b16) after 04-02's v3 impact-moment exception — full eyebrows/eyes are gone (major improvement over v1/v2) but a faint impact-reaction trace persists. Minor; within two-pass ceiling, carried not chased. | open |  | 2026-08-25T08:13:09.110Z |  |
| 9 | 4 | stub | output/panels/s2b19.jpg |  | Possible partial lettering ('CL' followed by an obscured shape) visible on a background wall sign, partly blocked by a foreground figure's head. Unconfirmed at full resolution — flagged for a closer look before phase 4 ships; the room rule already names 'sign' explicitly so this would be a rule miss rather than a coverage gap. | open |  | 2026-08-25T08:13:11.083Z |  |

````json
[
  {
    "id": 1,
    "kind": "stub",
    "phase": "3",
    "file": "output/assets/generated/generic_minor_character.jpg",
    "line": null,
    "description": "Model drew a detailed face on the generic minor character art instead of the instructed blank white head-shape (PROJECT.md no-facial-features rule)",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-08-25T00:31:49.957Z",
    "resolved_at": "2026-08-25T01:30:41.849Z"
  },
  {
    "id": 2,
    "kind": "stub",
    "phase": "3",
    "file": "output/assets/generated/promoter.jpg",
    "line": null,
    "description": "Model drew a detailed face on the promoter character art instead of the instructed blank white head-shape (PROJECT.md no-facial-features rule)",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-08-25T00:31:54.885Z",
    "resolved_at": "2026-08-25T01:30:41.938Z"
  },
  {
    "id": 3,
    "kind": "stub",
    "phase": "3",
    "file": "output/assets/generated/ext_street.jpg",
    "line": null,
    "description": "Location art drew one sleeping figure on the sidewalk despite the peopleless-establishing-view instruction",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-08-25T00:31:57.115Z",
    "resolved_at": "2026-08-25T01:30:48.450Z"
  },
  {
    "id": 4,
    "kind": "stub",
    "phase": "3",
    "file": "output/assets/generated/int_rockys_apartment.jpg",
    "line": null,
    "description": "A jacket on the floor renders as a small solid-black filled shape rather than pure outline linework, a minor departure from the two-tone (white ground, black outline) style rule; not one of the D-09 chrome/shading/text failure modes",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-08-25T01:30:54.458Z",
    "resolved_at": null
  },
  {
    "id": 5,
    "kind": "stub",
    "phase": "4",
    "file": "output/panels/s2b7.jpg",
    "line": null,
    "description": "Close-up facial clause (D-05, [ASSUMED]) failed on first live generation: the model drew a fully rendered eye (iris, pupil, eyelid crease) instead of leaving it part of the blank plane; brow/mouth/nose lines were drawn as intended. Flagged for 04-02's scene-2 tracer batch to revise the wording.",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-08-25T06:59:33.948Z",
    "resolved_at": "2026-08-25T08:12:50.891Z"
  },
  {
    "id": 6,
    "kind": "stub",
    "phase": "4",
    "file": "output/panels/s2b3.jpg",
    "line": null,
    "description": "Crowd scene (medium shot, ~15 figures) still shows fully rendered faces (eyebrows, eyes, open shouting mouths) on nearly every figure after both 04-02 revision passes; the blank-face clause's v3 'whole crowd packed shoulder to shoulder' exception did not suppress it. Two-pass ceiling reached (D-09) — carried, not chased further.",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-08-25T08:12:58.165Z",
    "resolved_at": null
  },
  {
    "id": 7,
    "kind": "stub",
    "phase": "4",
    "file": "output/panels/s2b9.jpg",
    "line": null,
    "description": "Close-up clause holds reliably for a single-character close-up but is less reliable with two characters sharing the frame: visible eye pupil dots appeared on the foreground character in s2b9, and on the secondary (non-primary) character in s2b5 and s2b7, despite the same unmodified close-up wording that reads clean on single-character close-ups (s2b13, s2b18, and others). Not touched by 04-02's two revision passes (both spent on the medium-shot and garment defects); carried, not chased.",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-08-25T08:13:06.843Z",
    "resolved_at": null
  },
  {
    "id": 8,
    "kind": "stub",
    "phase": "4",
    "file": "output/panels/s2b15.jpg",
    "line": null,
    "description": "Residual reaction marks (a closed/squinting eye line, a slightly open mouth) remain on the figure absorbing the punch in two-figure medium action shots (s2b15, s2b16) after 04-02's v3 impact-moment exception — full eyebrows/eyes are gone (major improvement over v1/v2) but a faint impact-reaction trace persists. Minor; within two-pass ceiling, carried not chased.",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-08-25T08:13:09.110Z",
    "resolved_at": null
  },
  {
    "id": 9,
    "kind": "stub",
    "phase": "4",
    "file": "output/panels/s2b19.jpg",
    "line": null,
    "description": "Possible partial lettering ('CL' followed by an obscured shape) visible on a background wall sign, partly blocked by a foreground figure's head. Unconfirmed at full resolution — flagged for a closer look before phase 4 ships; the room rule already names 'sign' explicitly so this would be a rule miss rather than a coverage gap.",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-08-25T08:13:11.083Z",
    "resolved_at": null
  }
]
````
