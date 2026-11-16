import os
import tempfile
import time
import unittest
from pathlib import Path

from agent_service.config import ConfigError
from agent_service.prompts import PromptStore


class PromptStoreTest(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.store = PromptStore(root=self.root)

    def tearDown(self):
        self.tempdir.cleanup()

    def write(self, name: str, text: str) -> Path:
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def test_reads_relative_prompt_and_strips(self):
        self.write("prompts/a.md", "  hello  \n")
        self.assertEqual(self.store.get("prompts/a.md"), "hello")

    def test_reads_absolute_prompt(self):
        path = self.write("a.md", "absolute")
        self.assertEqual(self.store.get(str(path)), "absolute")

    def test_missing_file_raises(self):
        with self.assertRaises(ConfigError):
            self.store.get("missing.md")

    def test_empty_file_raises(self):
        self.write("empty.md", "  \n\t ")
        with self.assertRaises(ConfigError):
            self.store.get("empty.md")

    def test_overlong_file_raises(self):
        self.write("long.md", "x" * 20_001)
        with self.assertRaises(ConfigError):
            self.store.get("long.md")

    def test_reloads_when_mtime_changes(self):
        path = self.write("prompt.md", "first")
        self.assertEqual(self.store.get("prompt.md"), "first")

        time.sleep(0.02)
        path.write_text("second", encoding="utf-8")
        self.assertEqual(self.store.get("prompt.md"), "second")

    def test_returns_cached_text_when_unchanged(self):
        path = self.write("prompt.md", "stable")
        first = self.store.get("prompt.md")
        second = self.store.get("prompt.md")
        self.assertEqual(first, second)
        self.assertEqual(path.read_text(encoding="utf-8"), "stable")


if __name__ == "__main__":
    unittest.main()