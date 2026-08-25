"""Which screenplay this run is about.

Everything that used to say `rocky-1976` or `first_n=8` asks here instead.
There were 35 such literals across seven manifest writers, three extractors,
the API and five CLIs — enough that pointing the pipeline at a second script
meant editing code rather than passing a flag, which is the opposite of what
the pipeline is for. Nothing else about the generation was ever Rocky-specific:
the heading regex, the music cues, the character world and the shot sizing all
derive from the script's own text.

Three questions, one answer each:

- **Where is the PDF?** `settings.script_pdf`, overridable with `SCRIPT_PDF`.
- **What is this script called?** Derived from the PDF's filename unless
  `SCRIPT_ID` says otherwise, so a new script is correctly labelled in every
  manifest without anyone remembering to set it.
- **How many scenes?** `settings.scene_count`, overridable with `SCENE_COUNT`.

Resolved by function call, never bound as a default argument. A default is
evaluated once at import, so `first_n: int = settings.scene_count` would freeze
whatever the value was when the module loaded and ignore a later override — the
same mistake that made `resolve_shot`'s directories unpatchable.
"""

from __future__ import annotations

import re
from pathlib import Path

from animatic.config import settings

_SLUG_STRIP = re.compile(r"[^a-z0-9]+")


def script_pdf() -> Path:
    """The screenplay this run reads."""
    return Path(settings.script_pdf)


def script_id() -> str:
    """A stable, filename-safe name for the script, for manifests and logs.

    Derived from the PDF's own filename when not set explicitly:
    `docs/rocky-1976.pdf` -> `rocky-1976`. A derived default is better than a
    configured one here because the failure mode of forgetting to change it is
    silent — every manifest would claim to be about a script it is not.
    """
    if settings.script_id:
        return _slug(settings.script_id)
    return _slug(script_pdf().stem)


def scene_count() -> int:
    """How many scenes from the top of the script this run covers.

    The demo is the first 8; a different script or a fuller run is a config
    change, not a code change.
    """
    return max(1, int(settings.scene_count))


def resolve_scene_count(first_n: int | None) -> int:
    """An explicit count if one was passed, otherwise the configured one."""
    return scene_count() if first_n is None else max(1, int(first_n))


def _slug(text: str) -> str:
    return _SLUG_STRIP.sub("-", text.strip().lower()).strip("-") or "script"
