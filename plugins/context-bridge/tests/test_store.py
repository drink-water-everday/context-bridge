#!/usr/bin/env python3
import shutil
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parents[1] / "mcp-server"))
from server import Store  # noqa: E402


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="context-bridge-test-"))
        self.store = Store(self.temp_dir)

    def tearDown(self):
        self.store.db.close()
        shutil.rmtree(self.temp_dir)

    def test_task_context_and_promotion(self):
        task = self.store.create_task(
            scope="codex-project:brand-ai",
            title="Brand research",
            question="Find AI brand tools",
            task_id="brand-x1",
        )
        self.assertEqual(task["id"], "brand-x1")

        context = self.store.save_context(
            scope="codex-project:brand-ai",
            title="Budget",
            content="Monthly budget is at most 3000 CNY.",
            kind="constraint",
            source_task_id="brand-x1",
            context_id="brand-context-budget",
        )
        self.store.attach_context("brand-x1", context["id"])
        loaded = self.store.get_task("brand-x1")
        self.assertEqual(loaded["contexts"][0]["id"], "brand-context-budget")

        promoted = self.store.promote_context(
            "brand-context-budget", "codex-project:personal-brand"
        )
        self.assertEqual(promoted["scope"], "codex-project:personal-brand")
        self.assertEqual(promoted["metadata"]["promoted_from"], "brand-context-budget")

    def test_search_is_scoped(self):
        self.store.save_context("personal", "Personal note", "Obsidian is local-first", "research")
        self.store.save_context("codex-project:brand-ai", "Brand note", "Use a small team tool", "decision")
        self.assertEqual(len(self.store.search_context("local-first", scope="personal")), 1)
        self.assertEqual(len(self.store.search_context("local-first", scope="codex-project:brand-ai")), 0)


if __name__ == "__main__":
    unittest.main()
