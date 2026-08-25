---
schema_version: 1
open_count: 3
waived_count: 0
fixed_count: 0
total_count: 3
last_updated: 2026-08-25T00:31:57.115Z
---

# Broken Windows Ledger

> Cross-phase defect register. With `workflow.windows_enforce` enabled, `/gsd-ship` blocks while `open_count > 0`.
> Waive with `gsd-tools windows waive <id> "<reason>"` (reason required).
> Mark fixed with `gsd-tools windows fixed <id>`.

| id | phase | kind | file | line | description | status | reason | recorded_at | resolved_at |
|----|-------|------|------|------|-------------|--------|--------|-------------|-------------|
| 1 | 3 | stub | output/assets/generated/generic_minor_character.jpg |  | Model drew a detailed face on the generic minor character art instead of the instructed blank white head-shape (PROJECT.md no-facial-features rule) | open |  | 2026-08-25T00:31:49.957Z |  |
| 2 | 3 | stub | output/assets/generated/promoter.jpg |  | Model drew a detailed face on the promoter character art instead of the instructed blank white head-shape (PROJECT.md no-facial-features rule) | open |  | 2026-08-25T00:31:54.885Z |  |
| 3 | 3 | stub | output/assets/generated/ext_street.jpg |  | Location art drew one sleeping figure on the sidewalk despite the peopleless-establishing-view instruction | open |  | 2026-08-25T00:31:57.115Z |  |

````json
[
  {
    "id": 1,
    "kind": "stub",
    "phase": "3",
    "file": "output/assets/generated/generic_minor_character.jpg",
    "line": null,
    "description": "Model drew a detailed face on the generic minor character art instead of the instructed blank white head-shape (PROJECT.md no-facial-features rule)",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-08-25T00:31:49.957Z",
    "resolved_at": null
  },
  {
    "id": 2,
    "kind": "stub",
    "phase": "3",
    "file": "output/assets/generated/promoter.jpg",
    "line": null,
    "description": "Model drew a detailed face on the promoter character art instead of the instructed blank white head-shape (PROJECT.md no-facial-features rule)",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-08-25T00:31:54.885Z",
    "resolved_at": null
  },
  {
    "id": 3,
    "kind": "stub",
    "phase": "3",
    "file": "output/assets/generated/ext_street.jpg",
    "line": null,
    "description": "Location art drew one sleeping figure on the sidewalk despite the peopleless-establishing-view instruction",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-08-25T00:31:57.115Z",
    "resolved_at": null
  }
]
````
