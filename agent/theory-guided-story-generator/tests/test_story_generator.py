from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from story_generator import (
    ContextUpdate,
    GeneratedSection,
    ModelConfig,
    PromptBundle,
    SectionDraft,
    StoryConfig,
    accept_section,
    build_prompt,
    export_result,
    generate_next_section,
    generate_section,
    generate_story,
    load_story_config,
    load_story_config_data,
    result_from_context,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "configs" / "fox_and_crow"


def load_payload() -> dict[str, object]:
    return load_story_config_data(CONFIG_DIR)


def blank_payload() -> dict[str, object]:
    payload = load_payload()
    plot = payload["plot_structure"]
    assert isinstance(plot, dict)
    for stage_name in ("cause", "development", "turning_point", "climax", "resolution"):
        plot[stage_name] = {"purpose": "", "days": [], "requirements": []}
    return payload


def configured_payload() -> dict[str, object]:
    payload = blank_payload()
    plot = payload["plot_structure"]
    assert isinstance(plot, dict)
    cause = plot["cause"]
    development = plot["development"]
    assert isinstance(cause, dict)
    assert isinstance(development, dict)
    cause.update(
        {
            "purpose": "让狐狸经历三个早晨并意识到它们构成循环。",
            "days": [1, 2, 3],
            "requirements": ["狐狸的认识必须来自可见的重复。"],
        }
    )
    development.update(
        {
            "purpose": "让累积知识改变狐狸的行动。",
            "days": [8, 12, 15],
            "requirements": [],
        }
    )
    return payload


def draft_for(context, plot_stage: str, days: tuple[int, ...]) -> SectionDraft:
    labels = {
        "cause": "起因",
        "development": "发展",
    }
    label = labels[plot_stage]
    return SectionDraft(
        section=GeneratedSection(
            label=label,
            text=f"### Day {days[0]}\n\n{label}候选文本。",
            plot_stage=plot_stage,
            days=days,
        ),
        context_update=ContextUpdate(
            established_facts=(f"{label}已经发生。",),
            character_knowledge={"fox": (f"狐狸记得{label}。",)},
        ),
        prompt=PromptBundle(system="system", user="user"),
        base_sequence_index=context.current_position.sequence_index,
        usage={"total_tokens": 10},
        response_metadata={},
    )


class StoryGeneratorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.project_config = load_story_config(CONFIG_DIR)
        self.blank_config = StoryConfig.from_dict(blank_payload())
        self.config = StoryConfig.from_dict(configured_payload())

    def test_multi_file_config_directory_loads(self) -> None:
        self.assertEqual(self.project_config.title, "《狐狸与乌鸦》")
        self.assertTrue((CONFIG_DIR / "plot_structure" / "cause.json").is_file())
        self.assertTrue((CONFIG_DIR / "story_world.json").is_file())
        self.assertTrue((CONFIG_DIR / "narrative_constraints.json").is_file())

    def test_notebook_has_five_explicit_guarded_section_blocks(self) -> None:
        notebook = json.loads(
            (ROOT / "notebooks" / "story_generator_deepseek.ipynb").read_text(
                encoding="utf-8"
            )
        )
        source = "\n".join(
            "".join(cell["source"]) for cell in notebook["cells"]
        )
        for heading in (
            "## 1. 起因",
            "## 2. 发展",
            "## 3. 转折",
            "## 4. 高潮",
            "## 5. 结局",
        ):
            self.assertIn(heading, source)
        self.assertIn("当前 section「{label}」尚未配置", source)
        self.assertIn("前一 section「{previous_label}」尚未配置", source)
        self.assertIn("缺少前一 section「{previous_label}」的已确认文本", source)

    def test_notebook_supports_colab_bootstrap_and_download(self) -> None:
        notebook = json.loads(
            (ROOT / "notebooks" / "story_generator_deepseek.ipynb").read_text(
                encoding="utf-8"
            )
        )
        source = "\n".join(
            "".join(cell["source"]) for cell in notebook["cells"]
        )
        self.assertIn('IN_COLAB = "google.colab" in sys.modules', source)
        self.assertIn(
            "https://github.com/666feiyu666/Fox-and-Crow.git",
            source,
        )
        self.assertIn(
            'COMPONENT_RELATIVE = Path("agent") / "theory-guided-story-generator"',
            source,
        )
        self.assertIn("requirements-colab.txt", source)
        self.assertIn("api_key = getpass.getpass(", source)
        self.assertIn('load_dotenv(PROJECT_ROOT / ".env")', source)
        self.assertNotIn("from google.colab import userdata", source)
        self.assertIn("复制到云端硬盘", source)
        self.assertIn('drive.mount("/content/drive")', source)
        self.assertIn(
            '/content/drive/MyDrive/Fox-and-Crow-workshop',
            source,
        )
        self.assertIn("不会覆盖你的修改", source)
        self.assertNotIn('PROJECT_ROOT = Path("/content/story-generator")', source)
        self.assertIn("只在本次 Colab 运行期间保存在内存中", source)
        self.assertIn("files.download(str(markdown_path))", source)
        for cell in notebook["cells"]:
            if cell["cell_type"] == "code":
                self.assertIsNone(cell["execution_count"])
                self.assertEqual(cell["outputs"], [])

    def test_project_configuration_contains_only_supplied_story_information(self) -> None:
        self.assertEqual(
            self.project_config.plot_structure.generation_plan(),
            ("cause", "development", "turning_point", "climax", "resolution"),
        )
        self.assertEqual(self.project_config.plot_structure.cause.days, (1, 2, 3))
        self.assertEqual(
            self.project_config.plot_structure.development.days,
            (8, 11, 13),
        )
        crow = next(
            character
            for character in self.project_config.story_world.characters
            if character.id == "crow"
        )
        self.assertIn("找回掉进荆棘灌木深处的项链。", crow.goals)
        self.assertEqual(
            self.project_config.discourse.language,
            "简体中文。语言自然、准确、有画面感，避免翻译腔和刻意华丽的辞藻。",
        )
        self.assertIn(
            "第三人称有限视角",
            self.project_config.discourse.point_of_view,
        )
        self.assertIn(
            "控制角色数量，避免无关支线",
            self.project_config.narrative_constraints.cast_and_subplots[0],
        )

    def test_blank_config_exposes_five_constraint_layers(self) -> None:
        self.assertEqual(self.blank_config.story_world.characters[0].id, "fox")
        self.assertEqual(self.blank_config.story_world.characters[1].id, "crow")
        self.assertEqual(self.blank_config.plot_structure.generation_plan(), ())
        self.assertEqual(
            self.blank_config.generation_context.current_position.sequence_index, 0
        )
        self.assertIn(
            "第三人称有限视角",
            self.blank_config.discourse.point_of_view,
        )

    def test_each_configured_section_has_three_days(self) -> None:
        self.assertEqual(
            self.config.plot_structure.generation_plan(),
            ("cause", "development"),
        )
        self.assertEqual(self.config.plot_structure.cause.days, (1, 2, 3))
        self.assertEqual(self.config.plot_structure.development.days, (8, 12, 15))

    def test_section_with_other_than_three_days_is_rejected(self) -> None:
        payload = blank_payload()
        plot = payload["plot_structure"]
        assert isinstance(plot, dict)
        cause = plot["cause"]
        assert isinstance(cause, dict)
        cause.update({"purpose": "起因", "days": [1, 2], "requirements": []})
        with self.assertRaisesRegex(ValueError, "exactly three story days"):
            StoryConfig.from_dict(payload)

    def test_sections_must_be_configured_in_order(self) -> None:
        payload = blank_payload()
        plot = payload["plot_structure"]
        assert isinstance(plot, dict)
        development = plot["development"]
        assert isinstance(development, dict)
        development.update(
            {"purpose": "发展", "days": [4, 5, 6], "requirements": []}
        )
        with self.assertRaisesRegex(ValueError, "narrative order"):
            StoryConfig.from_dict(payload)

    def test_prompt_renders_three_days_and_all_constraint_layers(self) -> None:
        prompt = build_prompt(self.config).user
        for heading in (
            "Plot Structure",
            "Story World",
            "Generation Context",
            "Narrative Constraints",
            "Discourse Specification",
        ):
            self.assertIn(heading, prompt)
        self.assertIn("section：起因", prompt)
        self.assertIn("`### Day 1`", prompt)
        self.assertIn("`### Day 2`", prompt)
        self.assertIn("`### Day 3`", prompt)
        self.assertIn("控制角色数量，避免无关支线", prompt)

    def test_draft_is_not_context_until_explicitly_accepted(self) -> None:
        context = self.config.generation_context
        candidate = draft_for(context, "cause", (1, 2, 3))

        self.assertEqual(context.generated_sections, ())
        accepted = accept_section(self.config, context, candidate)

        self.assertEqual(accepted.generated_sections[-1].label, "起因")
        self.assertIn("起因已经发生。", accepted.established_facts)
        self.assertIn("狐狸记得起因。", accepted.character_knowledge["fox"])
        self.assertEqual(accepted.current_position.sequence_index, 1)
        self.assertEqual(accepted.current_position.plot_stage, "development")

    def test_next_section_receives_only_accepted_previous_text(self) -> None:
        seen_contexts = []

        def fake_generate_section(story_config, context, plot_stage, model_config):
            seen_contexts.append(context)
            return draft_for(context, plot_stage, story_config.plot_structure.stage(plot_stage).days)

        with patch(
            "story_generator.generator.generate_section",
            side_effect=fake_generate_section,
        ):
            cause_draft = generate_next_section(self.config)
            accepted = accept_section(
                self.config,
                self.config.generation_context,
                cause_draft,
            )
            generate_next_section(self.config, accepted)

        self.assertEqual(len(seen_contexts), 2)
        self.assertEqual(seen_contexts[0].generated_sections, ())
        self.assertEqual(seen_contexts[1].generated_sections[-1].label, "起因")
        self.assertIn("狐狸记得起因。", seen_contexts[1].character_knowledge["fox"])

    def test_generate_section_uses_deepseek_json_mode(self) -> None:
        payload = {
            "story_text": "### Day 1\n\n第一天。\n\n### Day 2\n\n第二天。\n\n### Day 3\n\n第三天。",
            "context_update": {
                "established_facts": [],
                "unresolved_threads_add": [],
                "unresolved_threads_resolve": [],
                "character_knowledge": {},
                "character_beliefs": {},
                "relationship_changes": [],
                "attempted_actions": [],
                "outcomes": [],
            },
        }
        raw = SimpleNamespace(
            usage_metadata={"total_tokens": 20},
            response_metadata={"finish_reason": "stop"},
        )

        class FakeStructuredModel:
            def invoke(self, messages):
                self.messages = messages
                return {"raw": raw, "parsed": payload, "parsing_error": None}

        class FakeModel:
            def __init__(self):
                self.method = None
                self.include_raw = None

            def with_structured_output(
                self, schema, *, method, include_raw
            ):
                self.schema = schema
                self.method = method
                self.include_raw = include_raw
                return FakeStructuredModel()

        model = FakeModel()
        context = self.config.generation_context
        with patch("story_generator.generator._build_model", return_value=model):
            draft = generate_section(
                self.config,
                context,
                "cause",
                ModelConfig(),
            )

        self.assertEqual(model.method, "json_mode")
        self.assertTrue(model.include_raw)
        self.assertEqual(draft.usage["total_tokens"], 20)
        self.assertEqual(draft.section.plot_stage, "cause")
        self.assertIn("### Day 1", draft.section.text)

    def test_generate_section_recovers_json_like_context_maps(self) -> None:
        malformed_payload = """{
          "story_text": "### Day 1\\n第一天。\\n### Day 2\\n第二天。\\n### Day 3\\n第三天。",
          "context_update": {
            "established_facts": [],
            "unresolved_threads_add": [],
            "unresolved_threads_resolve": [],
            "character_knowledge": {
              "fox": {"知道桥断了。", "知道自己处于循环中。"}
            },
            "character_beliefs": {
              "fox": "相信自己必须调查循环。"
            },
            "relationship_changes": [],
            "attempted_actions": [],
            "outcomes": []
          }
        }"""
        raw = SimpleNamespace(
            content=malformed_payload,
            usage_metadata={"total_tokens": 30},
            response_metadata={"finish_reason": "stop"},
        )

        class FakeStructuredModel:
            def invoke(self, messages):
                return {
                    "raw": raw,
                    "parsed": None,
                    "parsing_error": ValueError("Invalid json output"),
                }

        class FakeModel:
            def with_structured_output(self, schema, *, method, include_raw):
                return FakeStructuredModel()

        with patch(
            "story_generator.generator._build_model", return_value=FakeModel()
        ):
            draft = generate_section(
                self.config,
                self.config.generation_context,
                "cause",
                ModelConfig(),
            )

        self.assertEqual(
            draft.context_update.character_knowledge["fox"],
            ("知道桥断了。", "知道自己处于循环中。"),
        )
        self.assertEqual(
            draft.context_update.character_beliefs["fox"],
            ("相信自己必须调查循环。",),
        )

    def test_one_click_mode_still_generates_every_configured_section(self) -> None:
        def fake_generate_section(story_config, context, plot_stage, model_config):
            return draft_for(context, plot_stage, story_config.plot_structure.stage(plot_stage).days)

        with patch(
            "story_generator.generator.generate_section",
            side_effect=fake_generate_section,
        ):
            result = generate_story(self.config, ModelConfig())

        self.assertEqual([section.label for section in result.sections], ["起因", "发展"])
        self.assertIn("## 起因", result.story)
        self.assertIn("## 发展", result.story)
        self.assertEqual(result.usage["total_tokens"], 20)

    def test_blank_plan_cannot_generate(self) -> None:
        with self.assertRaisesRegex(ValueError, "no configured sections"):
            generate_story(self.blank_config)

    def test_result_exports_only_accepted_sections(self) -> None:
        accepted = accept_section(
            self.config,
            self.config.generation_context,
            draft_for(self.config.generation_context, "cause", (1, 2, 3)),
        )
        result = result_from_context(self.config, accepted, ModelConfig())
        with tempfile.TemporaryDirectory() as directory:
            markdown_path, json_path = export_result(result, directory)
            markdown = markdown_path.read_text(encoding="utf-8")
            payload = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertIn("## 起因", markdown)
            self.assertNotIn("## 发展", markdown)
            self.assertEqual(payload["sections"][0]["days"], [1, 2, 3])


if __name__ == "__main__":
    unittest.main()
