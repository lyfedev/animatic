---
schema_version: 1
open_count: 2
waived_count: 0
fixed_count: 3
total_count: 5
last_updated: 2026-08-25T06:59:33.948Z
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
| 5 | 4 | stub | output/panels/s2b7.jpg |  | Close-up facial clause (D-05, [ASSUMED]) failed on first live generation: the model drew a fully rendered eye (iris, pupil, eyelid crease) instead of leaving it part of the blank plane; brow/mouth/nose lines were drawn as intended. Flagged for 04-02's scene-2 tracer batch to revise the wording. | open |  | 2026-08-25T06:59:33.948Z |  |

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
    "status": "open",
    "reason": "",
    "recorded_at": "2026-08-25T06:59:33.948Z",
    "resolved_at": null
  }
]
````
