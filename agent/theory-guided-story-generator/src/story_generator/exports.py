from __future__ import annotations

import json
import re
from pathlib import Path

from .generator import GenerationResult


def _safe_stem(title: str) -> str:
    stem = re.sub(r"[^\w\-]+", "-", title, flags=re.UNICODE).strip("-_").lower()
    return stem[:60] or "story"


def export_result(
    result: GenerationResult,
    output_dir: str | Path,
) -> tuple[Path, Path]:
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    timestamp = result.created_at.replace(":", "-").replace("+", "_")
    stem = f"{timestamp}-{_safe_stem(result.story_config.title)}"
    json_path = directory / f"{stem}.json"
    markdown_path = directory / f"{stem}.md"

    json_path.write_text(
        json.dumps(result.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    markdown_path.write_text(
        f"# {result.story_config.title}\n\n{result.story}\n",
        encoding="utf-8",
    )
    return markdown_path, json_path
