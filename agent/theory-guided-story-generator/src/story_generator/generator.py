from __future__ import annotations

import ast
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Mapping

from .config import PLOT_STAGE_LABELS, ConfigError, ModelConfig, StoryConfig
from .context import (
    ContextUpdate,
    GeneratedSection,
    GenerationContext,
    GenerationPosition,
    apply_context_update,
)
from .prompt import PromptBundle, build_section_prompt


SECTION_OUTPUT_SCHEMA = {
    "title": "StorySectionOutput",
    "description": "One three-day story section plus continuity updates.",
    "type": "object",
    "properties": {
        "story_text": {"type": "string"},
        "context_update": {
            "type": "object",
            "properties": {
                "established_facts": {"type": "array", "items": {"type": "string"}},
                "unresolved_threads_add": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "unresolved_threads_resolve": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "character_knowledge": {
                    "type": "object",
                    "additionalProperties": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "character_beliefs": {
                    "type": "object",
                    "additionalProperties": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "relationship_changes": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "attempted_actions": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "outcomes": {"type": "array", "items": {"type": "string"}},
            },
            "required": [
                "established_facts",
                "unresolved_threads_add",
                "unresolved_threads_resolve",
                "character_knowledge",
                "character_beliefs",
                "relationship_changes",
                "attempted_actions",
                "outcomes",
            ],
            "additionalProperties": False,
        },
    },
    "required": ["story_text", "context_update"],
    "additionalProperties": False,
}


@dataclass(frozen=True)
class SectionDraft:
    """A candidate section that has not yet been accepted into the context."""

    section: GeneratedSection
    context_update: ContextUpdate
    prompt: PromptBundle
    base_sequence_index: int
    usage: dict[str, object]
    response_metadata: dict[str, object]


@dataclass(frozen=True)
class GenerationResult:
    story: str
    story_config: StoryConfig
    model_config: ModelConfig
    sections: tuple[GeneratedSection, ...]
    final_context: GenerationContext
    created_at: str
    usage: dict[str, object]

    def to_dict(self) -> dict[str, object]:
        return {
            "story": self.story,
            "story_config": self.story_config.to_dict(),
            "model_config": self.model_config.to_dict(),
            "sections": [section.to_dict() for section in self.sections],
            "final_context": self.final_context.to_dict(),
            "created_at": self.created_at,
            "usage": self.usage,
        }


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise RuntimeError(f"DeepSeek returned an invalid {label}.")
    return value


def _usage(raw: Any) -> dict[str, object]:
    return dict(getattr(raw, "usage_metadata", None) or {})


def _metadata(raw: Any) -> dict[str, object]:
    return dict(getattr(raw, "response_metadata", None) or {})


class _SetAsList(ast.NodeTransformer):
    """Preserve model-emitted set elements while making the literal JSON-shaped."""

    def visit_Set(self, node: ast.Set) -> ast.List:
        return ast.copy_location(
            ast.List(
                elts=[self.visit(element) for element in node.elts],
                ctx=ast.Load(),
            ),
            node,
        )


def _raw_text(raw: Any) -> str:
    content = getattr(raw, "content", "")
    if isinstance(content, str):
        return content.strip()
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for block in content:
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, Mapping) and isinstance(block.get("text"), str):
            parts.append(block["text"])
    return "\n".join(parts).strip()


def _without_code_fence(text: str) -> str:
    lines = text.strip().splitlines()
    if (
        len(lines) >= 2
        and lines[0].strip().startswith("```")
        and lines[-1].strip() == "```"
    ):
        return "\n".join(lines[1:-1]).strip()
    return text.strip()


def _decode_raw_payload(raw: Any) -> Mapping[str, Any] | None:
    """Recover JSON-like output without evaluating executable Python code."""
    text = _without_code_fence(_raw_text(raw))
    if not text:
        return None
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        try:
            tree = ast.parse(text, mode="eval")
            tree = _SetAsList().visit(tree)
            value = ast.literal_eval(tree)
        except (SyntaxError, ValueError):
            return None
    return value if isinstance(value, Mapping) else None


def _normalize_section_payload(value: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize narrow, unambiguous schema slips commonly emitted by chat models."""
    payload = dict(value)
    raw_update = payload.get("context_update")
    if not isinstance(raw_update, Mapping):
        return payload
    update = dict(raw_update)
    for field in (
        "established_facts",
        "unresolved_threads_add",
        "unresolved_threads_resolve",
        "relationship_changes",
        "attempted_actions",
        "outcomes",
    ):
        if isinstance(update.get(field), str):
            update[field] = [update[field]]
    for field in ("character_knowledge", "character_beliefs"):
        text_map = update.get(field)
        if isinstance(text_map, Mapping):
            update[field] = {
                str(key): [items] if isinstance(items, str) else items
                for key, items in text_map.items()
            }
    payload["context_update"] = update
    return payload


def _add_usage(total: dict[str, object], current: Mapping[str, object]) -> None:
    for key, value in current.items():
        if isinstance(value, int) and not isinstance(value, bool):
            existing = total.get(key, 0)
            if isinstance(existing, int):
                total[key] = existing + value


def _build_model(model_config: ModelConfig) -> Any:
    try:
        from langchain_deepseek import ChatDeepSeek
    except ImportError as error:
        raise RuntimeError(
            "langchain-deepseek is not installed. Run uv sync first."
        ) from error
    return ChatDeepSeek(
        model=model_config.model,
        temperature=float(model_config.temperature),
        max_tokens=model_config.max_tokens,
        timeout=float(model_config.timeout),
        max_retries=model_config.max_retries,
    )


def generate_section(
    story_config: StoryConfig,
    context: GenerationContext,
    plot_stage: str,
    model_config: ModelConfig,
) -> SectionDraft:
    """Generate a three-day section candidate without accepting it."""
    stage = story_config.plot_structure.stage(plot_stage)
    prompt = build_section_prompt(story_config, context, plot_stage)
    model = _build_model(model_config)
    structured_model = model.with_structured_output(
        SECTION_OUTPUT_SCHEMA,
        method="json_mode",
        include_raw=True,
    )
    response = structured_model.invoke(
        [("system", prompt.system), ("human", prompt.user)]
    )
    response_map = _mapping(response, "structured response")
    raw = response_map.get("raw")
    parsing_error = response_map.get("parsing_error")
    parsed_value = response_map.get("parsed")
    if parsed_value is None:
        parsed_value = _decode_raw_payload(raw)
    if parsed_value is None and parsing_error:
        raise RuntimeError(
            f"DeepSeek structured output could not be parsed: {parsing_error}"
        )
    if parsed_value is None:
        finish_reason = _metadata(raw).get("finish_reason", "unknown")
        raise RuntimeError(
            "DeepSeek returned no JSON section payload "
            f"(finish_reason={finish_reason}). Please retry this section."
        )
    parsed = _normalize_section_payload(
        _mapping(parsed_value, "section payload")
    )
    story_text = parsed.get("story_text")
    if not isinstance(story_text, str) or not story_text.strip():
        raise RuntimeError("DeepSeek returned an empty story section.")
    update = ContextUpdate.from_dict(parsed.get("context_update"))
    return SectionDraft(
        section=GeneratedSection(
            label=PLOT_STAGE_LABELS[plot_stage],
            days=stage.days,
            plot_stage=plot_stage,
            text=story_text.strip(),
        ),
        context_update=update,
        prompt=prompt,
        base_sequence_index=context.current_position.sequence_index,
        usage=_usage(raw),
        response_metadata=_metadata(raw),
    )


def generate_next_section(
    story_config: StoryConfig,
    context: GenerationContext | None = None,
    model_config: ModelConfig | None = None,
) -> SectionDraft:
    """Generate only the next configured section, leaving context unchanged."""
    selected_context = context or story_config.generation_context
    selected_model = model_config or ModelConfig()
    plan = story_config.plot_structure.generation_plan()
    index = selected_context.current_position.sequence_index
    if index >= len(plan):
        raise ConfigError("No next plot section is configured.")
    stage_name = plan[index]
    positioned_context = selected_context.at_position(
        GenerationPosition(
            sequence_index=index,
            plot_stage=stage_name,
            section_label=PLOT_STAGE_LABELS[stage_name],
        )
    )
    return generate_section(
        story_config,
        positioned_context,
        stage_name,
        selected_model,
    )


def accept_section(
    story_config: StoryConfig,
    context: GenerationContext,
    draft: SectionDraft,
) -> GenerationContext:
    """Accept a reviewed draft and make it a constraint on the next section."""
    plan = story_config.plot_structure.generation_plan()
    index = context.current_position.sequence_index
    if index >= len(plan):
        raise ConfigError("There is no configured section to accept.")
    if draft.base_sequence_index != index:
        raise ConfigError("This draft was generated from a different context position.")
    expected_stage = plan[index]
    if draft.section.plot_stage != expected_stage:
        raise ConfigError(
            f"Expected a {expected_stage} draft, got {draft.section.plot_stage}."
        )

    next_index = index + 1
    if next_index < len(plan):
        next_stage = plan[next_index]
        next_position = GenerationPosition(
            sequence_index=next_index,
            plot_stage=next_stage,
            section_label=PLOT_STAGE_LABELS[next_stage],
        )
    else:
        next_position = GenerationPosition(sequence_index=next_index)
    return apply_context_update(
        context,
        draft.section,
        draft.context_update,
        next_position,
    )


def result_from_context(
    story_config: StoryConfig,
    context: GenerationContext,
    model_config: ModelConfig | None = None,
    usage: Mapping[str, object] | None = None,
) -> GenerationResult:
    """Build an exportable result from the currently accepted sections."""
    story = "\n\n".join(
        f"## {section.label}\n\n{section.text}"
        for section in context.generated_sections
    )
    return GenerationResult(
        story=story,
        story_config=story_config,
        model_config=model_config or ModelConfig(),
        sections=context.generated_sections,
        final_context=context,
        created_at=datetime.now(UTC).isoformat(),
        usage=dict(usage or {}),
    )


def generate_story(
    story_config: StoryConfig,
    model_config: ModelConfig | None = None,
) -> GenerationResult:
    """Optional one-click mode: generate and accept every configured section."""
    selected_model = model_config or ModelConfig()
    plan = story_config.plot_structure.generation_plan()
    if not plan:
        raise ConfigError("Plot structure contains no configured sections.")

    context = story_config.generation_context
    aggregate_usage: dict[str, object] = {}
    while context.current_position.sequence_index < len(plan):
        draft = generate_next_section(story_config, context, selected_model)
        context = accept_section(story_config, context, draft)
        _add_usage(aggregate_usage, draft.usage)
    return result_from_context(
        story_config,
        context,
        selected_model,
        aggregate_usage,
    )
