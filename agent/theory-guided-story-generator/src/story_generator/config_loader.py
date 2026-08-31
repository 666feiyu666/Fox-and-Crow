from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from .config import PLOT_STAGE_ORDER, ConfigError, StoryConfig


def _read_object(path: Path, label: str) -> dict[str, Any]:
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError as error:
        raise ConfigError(f"Missing {label} file: {path}") from error
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ConfigError(
            f"Invalid JSON in {label} file {path}: line {error.lineno}, "
            f"column {error.colno}."
        ) from error
    if not isinstance(value, Mapping):
        raise ConfigError(f"{label} file must contain a JSON object: {path}")
    return dict(value)


def _require_exact_keys(
    payload: Mapping[str, Any],
    required: set[str],
    label: str,
) -> None:
    missing = sorted(required - set(payload))
    unknown = sorted(set(payload) - required)
    if missing:
        raise ConfigError(f"{label} is missing fields: {', '.join(missing)}.")
    if unknown:
        raise ConfigError(f"{label} contains unsupported fields: {', '.join(unknown)}.")


def load_story_config_data(config_dir: str | Path) -> dict[str, object]:
    """Compose the conventional multi-file story configuration into one mapping."""
    directory = Path(config_dir).expanduser().resolve()
    if not directory.is_dir():
        raise ConfigError(f"Story configuration directory does not exist: {directory}")

    story = _read_object(directory / "story.json", "story metadata")
    _require_exact_keys(story, {"title", "premise"}, "story metadata")

    plot_directory = directory / "plot_structure"
    plot_structure: dict[str, object] = {
        stage_name: _read_object(
            plot_directory / f"{stage_name}.json",
            f"plot section {stage_name}",
        )
        for stage_name in PLOT_STAGE_ORDER
    }
    shared_plot = _read_object(
        plot_directory / "constraints.json",
        "shared plot constraints",
    )
    _require_exact_keys(
        shared_plot,
        {"constraints"},
        "shared plot constraints",
    )
    plot_structure["constraints"] = shared_plot["constraints"]

    narrative_constraint_fields = {
        "cast_and_subplots",
        "plot_and_pacing",
        "time_loop",
        "viewpoint_and_information",
        "character_and_relationships",
        "prose_and_dialogue",
        "continuity_and_resolution",
    }
    narrative_constraints = _read_object(
        directory / "narrative_constraints.json",
        "narrative constraints",
    )
    _require_exact_keys(
        narrative_constraints,
        narrative_constraint_fields,
        "narrative constraints",
    )

    return {
        "title": story["title"],
        "premise": story["premise"],
        "plot_structure": plot_structure,
        "story_world": _read_object(
            directory / "story_world.json",
            "story world",
        ),
        "generation_context": _read_object(
            directory / "generation_context.json",
            "generation context",
        ),
        "narrative_constraints": narrative_constraints,
        "discourse": _read_object(
            directory / "discourse.json",
            "discourse specification",
        ),
    }


def load_story_config(config_dir: str | Path) -> StoryConfig:
    """Load and validate a story configuration directory."""
    return StoryConfig.from_dict(load_story_config_data(config_dir))
