"""Configurable, local-first story generator."""

from .config import (
    CharacterConfig,
    ConfigError,
    DiscourseConfig,
    ModelConfig,
    NarrativeConstraintsConfig,
    PlotStageConfig,
    PlotStructureConfig,
    StoryConfig,
    StoryWorldConfig,
    WorldEntityConfig,
)
from .context import (
    ContextUpdate,
    GeneratedSection,
    GenerationContext,
    GenerationPosition,
    apply_context_update,
)
from .config_loader import load_story_config, load_story_config_data
from .exports import export_result
from .generator import (
    GenerationResult,
    SectionDraft,
    accept_section,
    generate_next_section,
    generate_section,
    generate_story,
    result_from_context,
)
from .prompt import PromptBundle, build_prompt, build_section_prompt

__all__ = [
    "CharacterConfig",
    "ConfigError",
    "ContextUpdate",
    "DiscourseConfig",
    "GeneratedSection",
    "GenerationContext",
    "GenerationPosition",
    "GenerationResult",
    "ModelConfig",
    "NarrativeConstraintsConfig",
    "PlotStageConfig",
    "PlotStructureConfig",
    "PromptBundle",
    "SectionDraft",
    "StoryConfig",
    "StoryWorldConfig",
    "WorldEntityConfig",
    "accept_section",
    "apply_context_update",
    "build_prompt",
    "build_section_prompt",
    "export_result",
    "generate_next_section",
    "generate_section",
    "generate_story",
    "load_story_config",
    "load_story_config_data",
    "result_from_context",
]
