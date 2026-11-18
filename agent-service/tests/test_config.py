import os
import tempfile
import unittest
from pathlib import Path

from agent_service.config import AppConfig, ConfigError, ConfigStore


class AppConfigTest(unittest.TestCase):
    def test_prompt_file_default(self):
        config = AppConfig.model_validate(
            {"llm": {"api_key": "test", "model": "test-model"}}
        )
        self.assertEqual(config.llm.prompt_file, "prompts/shopping_agent.md")

    def test_demo_user_id_default(self):
        config = AppConfig.model_validate(
            {"llm": {"api_key": "test", "model": "test-model"}}
        )
        self.assertEqual(config.mall.demo_user_id, "u-demo")

    def test_demo_user_id_can_be_overridden(self):
        config = AppConfig.model_validate(
            {
                "llm": {"api_key": "test", "model": "test-model"},
                "mall": {"demo_user_id": "u-other"},
            }
        )
        self.assertEqual(config.mall.demo_user_id, "u-other")

    def test_legacy_system_prompt_is_rejected(self):
        with tempfile.TemporaryDirectory() as tempdir:
            path = Path(tempdir) / "llm.yaml"
            path.write_text(
                "llm:\n"
                "  api_key: test\n"
                "  model: test-model\n"
                "  system_prompt: legacy\n",
                encoding="utf-8",
            )

            previous = os.environ.get("AGENT_CONFIG_FILE")
            os.environ["AGENT_CONFIG_FILE"] = str(path)
            try:
                store = ConfigStore()
                with self.assertRaises(ConfigError) as context:
                    store.get()
                self.assertIn("已废弃", str(context.exception))
            finally:
                if previous is None:
                    os.environ.pop("AGENT_CONFIG_FILE", None)
                else:
                    os.environ["AGENT_CONFIG_FILE"] = previous


if __name__ == "__main__":
    unittest.main()