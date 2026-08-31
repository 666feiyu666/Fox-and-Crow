from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .config import (
    PLOT_STAGE_LABELS,
    PLOT_STAGE_ORDER,
    CharacterConfig,
    ConfigError,
    StoryConfig,
    WorldEntityConfig,
)
from .context import GenerationContext, GenerationPosition


@dataclass(frozen=True)
class PromptBundle:
    system: str
    user: str

    def to_dict(self) -> dict[str, str]:
        return {"system": self.system, "user": self.user}


def _bullets(title: str, items: tuple[str, ...]) -> list[str]:
    if not items:
        return []
    return [f"### {title}", *(f"- {item}" for item in items), ""]


def _character(character: CharacterConfig) -> list[str]:
    lines = [f"### {character.name} (`{character.id}`)"]
    if character.role:
        lines.append(f"- 角色：{character.role}")
    fields = (
        ("性格", character.traits),
        ("目标", character.goals),
        ("初始信念", character.beliefs),
        ("初始知识", character.knowledge),
        ("关系", character.relationships),
        ("约束", character.constraints),
    )
    for label, values in fields:
        if values:
            lines.append(f"- {label}：{'；'.join(values)}")
    lines.append("")
    return lines


def _entities(title: str, entities: tuple[WorldEntityConfig, ...]) -> list[str]:
    if not entities:
        return []
    lines = [f"### {title}"]
    for entity in entities:
        lines.append(f"- {entity.name} (`{entity.id}`)：{entity.description}")
        lines.extend(f"  - {item}" for item in entity.properties)
    lines.append("")
    return lines


def _plot_structure(config: StoryConfig, current_stage: str) -> list[str]:
    lines = ["## Plot Structure｜整体情节结构"]
    for stage_name in PLOT_STAGE_ORDER:
        stage = config.plot_structure.stage(stage_name)
        marker = "（当前 section）" if stage_name == current_stage else ""
        lines.append(f"### {PLOT_STAGE_LABELS[stage_name]}{marker}")
        if stage.configured:
            lines.append(f"- 目标故事日：{', '.join(f'Day {day}' for day in stage.days)}")
            lines.append(f"- section 功能：{stage.purpose}")
            lines.extend(f"- section 要求：{item}" for item in stage.requirements)
        else:
            lines.append("- 尚未配置")
        lines.append("")
    lines.extend(_bullets("跨 section 约束", config.plot_structure.constraints))
    return lines


def _story_world(config: StoryConfig) -> list[str]:
    world = config.story_world
    lines = ["## Story World｜故事世界", "### 角色"]
    for character in world.characters:
        lines.extend(_character(character))
    lines.extend(_entities("地点", world.locations))
    lines.extend(_entities("物品", world.items))
    lines.extend(_entities("障碍", world.obstacles))
    lines.extend(_bullets("客观事实", world.facts))
    lines.extend(_bullets("世界规则", world.rules))
    lines.extend(_bullets("初始状态", world.initial_state))
    lines.extend(_bullets("每日重置规则", world.reset_rules))
    lines.extend(_bullets("跨循环保留规则", world.persistence_rules))
    return lines


def _text_map(
    title: str,
    values: Mapping[str, tuple[str, ...]],
) -> list[str]:
    if not values:
        return []
    lines = [f"### {title}"]
    for key, items in values.items():
        lines.append(f"- `{key}`：{'；'.join(items)}")
    lines.append("")
    return lines


def _generation_context(context: GenerationContext) -> list[str]:
    position = context.current_position
    lines = [
        "## Generation Context｜生成上下文",
        f"- 已确认 section 数：{position.sequence_index}",
        f"- 当前情节阶段：{position.plot_stage or '未指定'}",
        f"- 当前 section：{position.section_label or '未指定'}",
        "",
    ]
    if context.generated_sections:
        lines.append("### 已确认的此前文本")
        for section in context.generated_sections:
            lines.extend([f"#### {section.label}", section.text, ""])
    lines.extend(_bullets("已确立事实", context.established_facts))
    lines.extend(_bullets("未解决线索", context.unresolved_threads))
    lines.extend(_text_map("角色累积知识", context.character_knowledge))
    lines.extend(_text_map("角色当前信念", context.character_beliefs))
    lines.extend(_bullets("关系变化", context.relationship_changes))
    lines.extend(_bullets("已经尝试的行动", context.attempted_actions))
    lines.extend(_bullets("行动结果", context.outcomes))
    return lines


def _discourse(config: StoryConfig) -> list[str]:
    discourse = config.discourse
    fields = (
        ("语言", discourse.language),
        ("风格", discourse.style),
        ("每个 section 的长度", discourse.length),
        ("形式", discourse.format),
        ("视角", discourse.point_of_view),
        ("时态", discourse.tense),
    )
    lines = ["## Discourse Specification｜话语规格"]
    lines.extend(f"- {label}：{value}" for label, value in fields if value)
    lines.extend(f"- 约束：{item}" for item in discourse.constraints)
    if len(lines) == 1:
        lines.append("- 尚未配置")
    lines.append("")
    return lines


def _narrative_constraints(config: StoryConfig) -> list[str]:
    constraints = config.narrative_constraints
    categories = (
        ("角色与支线", constraints.cast_and_subplots),
        ("情节与节奏", constraints.plot_and_pacing),
        ("时间循环", constraints.time_loop),
        ("视角与信息", constraints.viewpoint_and_information),
        ("人物与关系", constraints.character_and_relationships),
        ("语言与对话", constraints.prose_and_dialogue),
        ("连续性与结局", constraints.continuity_and_resolution),
    )
    lines = [
        "## Narrative Constraints｜全局限制与禁区",
        "- 以下规则是全局硬限制；不得为了制造戏剧性、悬念或篇幅而绕过。",
        "",
    ]
    for title, items in categories:
        lines.extend(_bullets(title, items))
    return lines


def build_section_prompt(
    config: StoryConfig,
    context: GenerationContext,
    plot_stage: str,
) -> PromptBundle:
    if plot_stage not in PLOT_STAGE_ORDER:
        raise ConfigError(f"Unsupported plot stage: {plot_stage}.")
    stage = config.plot_structure.stage(plot_stage)
    if not stage.configured:
        raise ConfigError(f"Plot stage {plot_stage} is not configured.")

    section_label = PLOT_STAGE_LABELS[plot_stage]
    day_headings = [f"Day {day}" for day in stage.days]
    system = (
        "你是一个按五段结构逐步生成小说的 Story Generator。每次只生成当前一个 "
        "section；当前 section 包含三个指定故事日。必须同时服从 Plot Structure、"
        "Story World、Generation Context、Narrative Constraints 和 Discourse "
        "Specification。只有已经由用户"
        "确认的 section 才会出现在 Generation Context。世界重置不等于角色记忆重置。"
        "不要重复角色已经做过且没有理由重做的行动，不要泄露视角角色尚未知晓的事实。"
    )
    lines = [
        *([f"# {config.title}"] if config.title else []),
        *([f"- 故事核心：{config.premise}"] if config.premise else []),
        *([""] if config.title or config.premise else []),
        *_plot_structure(config, plot_stage),
        *_story_world(config),
        *_generation_context(context),
        *_narrative_constraints(config),
        *_discourse(config),
        "## 当前生成任务",
        f"- section：{section_label}",
        f"- 目标故事日：{'、'.join(day_headings)}",
        f"- section 功能：{stage.purpose}",
        *(f"- section 要求：{item}" for item in stage.requirements),
        "",
        "`story_text` 必须包含且只包含以下三个三级标题，并在各标题下生成对应一天：",
        *(f"- `### {heading}`" for heading in day_headings),
        "不要在 `story_text` 中添加起因、发展等 section 标题；调用程序会统一添加。",
        "三个故事日共同完成当前 section 的功能，但每天都必须发生可辨认的推进或变化。",
        "`context_update` 只能记录本次 `story_text` 实际建立的内容，不得预写未来事实。",
        "如要解决既有线索，请在 `unresolved_threads_resolve` 中原样复制该线索。",
        "",
        "## 输出格式",
        "只返回一个有效 JSON 对象，不要添加说明文字或 Markdown 代码围栏。",
        "JSON 必须严格使用以下结构；没有内容的数组或对象也必须保留：",
        "{",
        '  "story_text": "包含三个指定 Day 标题的完整正文",',
        '  "context_update": {',
        '    "established_facts": [],',
        '    "unresolved_threads_add": [],',
        '    "unresolved_threads_resolve": [],',
        '    "character_knowledge": {"fox": ["本段新增知识"]},',
        '    "character_beliefs": {"fox": ["本段形成或改变的信念"]},',
        '    "relationship_changes": [],',
        '    "attempted_actions": [],',
        '    "outcomes": []',
        "  }",
        "}",
        "`character_knowledge` 和 `character_beliefs` 中，每个角色 ID 对应的值"
        "必须是 JSON 字符串数组，即使只有一项也必须使用方括号。",
    ]
    return PromptBundle(system=system, user="\n".join(lines).strip())


def build_prompt(
    config: StoryConfig,
    context: GenerationContext | None = None,
) -> PromptBundle:
    """Preview the prompt for the next configured, unconfirmed section."""
    selected_context = context or config.generation_context
    plan = config.plot_structure.generation_plan()
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
    return build_section_prompt(config, positioned_context, stage_name)
