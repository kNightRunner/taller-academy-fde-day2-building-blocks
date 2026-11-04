import unittest
from src.building_blocks.memory import SIMULATED_RUN, history, prompt_projection, GOAL
from src.building_blocks.critic import run_pair, word_count, RUBRIC
from src.building_blocks.providers import ModelResponse


class MemoryTests(unittest.TestCase):
    def test_one_step_history(self):
        self.assertEqual(len(history(SIMULATED_RUN[:1])), 3)
        self.assertEqual(history([])[0]["content"], GOAL)

    def test_full_synthetic_history(self):
        self.assertEqual(len(history(SIMULATED_RUN)), 13)

    def test_linear_projection(self):
        r = prompt_projection([50, 60, 70, 80, 90, 100, 110])
        self.assertEqual(r["projected_20_step_total"], 21 * 50 + 210 * 10)
        self.assertEqual(r["observed_increment_mean"], 10)


class FakeModel:
    model = "fake"
    def __init__(self, texts):
        self.texts = iter(texts)
    def generate(self, messages, tools=None):
        return ModelResponse(text=next(self.texts), input_tokens=2, output_tokens=3)


class CriticTests(unittest.TestCase):
    def test_critic_pass(self):
        out = run_pair(FakeModel(["draft one", "PASS\nNo failures"]), "pass")
        self.assertTrue(out["passed"])
        self.assertEqual(out["calls"], 2)
        self.assertEqual(out["tokens_in"], 4)

    def test_failure_revision_success(self):
        out = run_pair(FakeModel(["draft one", "FAIL\n4 word count", "draft two", "PASS"]), "retry")
        self.assertTrue(out["passed"])
        self.assertEqual(out["calls"], 4)
        self.assertEqual(len(out["records"]), 4)

    def test_hard_revision_ceiling(self):
        out = run_pair(FakeModel(["first", "FAIL", "second", "FAIL", "third"]),
                       "bounded", max_revisions=2)
        self.assertFalse(out["passed"])
        self.assertEqual(out["status"], "limit_reached_human_review_required")
        self.assertEqual(out["calls"], 5)

    def test_count_words(self):
        self.assertEqual(word_count("one two\nthree"), 3)


if __name__ == "__main__":
    unittest.main()
