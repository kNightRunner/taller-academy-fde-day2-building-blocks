import unittest
from src.building_blocks.meeting import MeetingStore, goals, run_meeting_agent, specs, PEOPLE
from src.building_blocks.providers import ModelResponse, ToolCall


class ToolTests(unittest.TestCase):
    def setUp(self):
        self.store = MeetingStore()

    def test_known_person(self):
        self.assertEqual(self.store.find_person("ana")["id"], "ana")
        self.assertEqual(self.store.find_person("Ana")["id"], "ana")

    def test_missing_person_actionable(self):
        self.assertIn("Known ids", self.store.find_person("nobody")["error"])

    def test_name_query_requires_string(self):
        self.assertIn("non-empty", self.store.find_person(None)["error"])

    def test_available_busy_blocks(self):
        blocks = self.store.check_availability("ana", "2026-04-06")["busy_blocks"]
        self.assertEqual(blocks, [{"start_hour": 9, "end_hour": 11}])

    def test_invalid_relative_date(self):
        self.assertEqual(self.store.check_availability("ana", "next Monday")["error"],
                         "date must be ISO format YYYY-MM-DD, got 'next Monday'.")

    def test_unknown_id(self):
        self.assertIn("Call find_person first", self.store.check_availability("x", "2026-04-06")["error"])

    def test_successful_booking(self):
        result = self.store.book_meeting(["ana", "ben", "cai"], "2026-04-06", 11, 2, "Design review")
        self.assertEqual(result["booked"]["start_hour"], 11)
        self.assertEqual(len(self.store.booked), 1)

    def test_conflict_does_not_write(self):
        error = self.store.book_meeting(["ana", "ben", "cai"], "2026-04-06", 13, 2, "Review")
        self.assertIn("Conflicts found", error["error"])
        self.assertEqual(self.store.booked, [])

    def test_booked_meeting_prevents_double_booking(self):
        self.store.book_meeting(["ana", "ben", "cai"], "2026-04-06", 11, 2, "Review")
        err = self.store.book_meeting(["ana", "ben"], "2026-04-06", 11, 2, "Again")
        self.assertIn("Conflicts", err["error"])

    def test_3am_guard(self):
        self.assertIn("between 9 and 17", self.store.book_meeting(["ana"], "2026-04-06", 3, 2, "Review")["error"])

    def test_lab_only_3am_bypass(self):
        s = MeetingStore(allow_3am=True)
        self.assertEqual(s.book_meeting(["ana"], "2026-04-06", 3, 2, "Review")["booked"]["start_hour"], 3)

    def test_bool_is_not_int(self):
        self.assertIn("between 9", self.store.book_meeting(["ana"], "2026-04-06", True, 2, "Review")["error"])

    def test_bad_date_format(self):
        self.assertIn("ISO format", self.store.book_meeting(["ana"], "2026/04/06", 11, 2, "Review")["error"])

    def test_wrong_argument_name(self):
        self.assertIn("Bad arguments", self.store.execute("find_person", {"username": "ana"})["error"])

    def test_unknown_tool(self):
        self.assertIn("Unknown tool", self.store.execute("destroy_meeting", {})["error"])

    def test_duplicate_people(self):
        self.assertIn("duplicates", self.store.book_meeting(["ana", "ana"], "2026-04-06", 11, 2, "Review")["error"])

    def test_bad_duration(self):
        self.assertIn("between 1 and 4", self.store.book_meeting(["ana"], "2026-04-06", 11, 8, "Review")["error"])

    def test_title_required(self):
        self.assertIn("non-empty", self.store.book_meeting(["ana"], "2026-04-06", 11, 2, "")["error"])

    def test_specs_descriptive_and_erasable(self):
        self.assertEqual(len(specs()), 3)
        self.assertEqual(len(specs(without_find_person=True)), 2)
        self.assertEqual(specs(gut_book_description=True)[-1]["description"], "Books a meeting.")
        self.assertEqual(specs(remove_date_hint=True)[1]["input_schema"]["properties"]["date"]["description"], "The date.")

    def test_isolated_stores(self):
        s1, s2 = MeetingStore(), MeetingStore()
        s1.book_meeting(["ana"], "2026-04-06", 11, 2, "Meeting")
        self.assertEqual(s2.booked, [])


class FakeProvider:
    def __init__(self, replies):
        self.replies = iter(replies)
        self.model = "scripted-test-double"
    def generate(self, messages, tools=None):
        return next(self.replies)


def call(name, arg, ident):
    return ToolCall(ident, name, arg)


class AgentTests(unittest.TestCase):
    def test_full_scripted_booking(self):
        replies = [
            ModelResponse(tool_calls=[call("find_person", {"query": "Ana"}, "1"),
                                      call("find_person", {"query": "Ben"}, "2"),
                                      call("find_person", {"query": "Cai"}, "3")],
                          input_tokens=12, output_tokens=6),
            ModelResponse(tool_calls=[call("check_availability", {"person_id": k, "date": "2026-04-06"}, k)
                                      for k in ("ana", "ben", "cai")], input_tokens=24, output_tokens=8),
            ModelResponse(tool_calls=[call("book_meeting", {"person_ids": ["ana", "ben", "cai"],
                                                           "date": "2026-04-06", "start_hour": 11,
                                                           "duration_hours": 2, "title": "Review"}, "last")],
                          input_tokens=30, output_tokens=6),
            ModelResponse(text="Booked synthetic review.", input_tokens=38, output_tokens=4),
        ]
        result = run_meeting_agent(FakeProvider(replies), "test", goals()["baseline"])
        self.assertEqual(result.status, "completed")
        self.assertEqual(result.steps, 4)
        self.assertEqual(len(result.trace), 7)
        self.assertEqual(result.tokens_in, 104)
        self.assertEqual(result.booked[0]["start_hour"], 11)

    def test_step_limit_is_not_success(self):
        replies = [ModelResponse(tool_calls=[call("find_person", {"query": "Ana"}, "1")],
                                 input_tokens=1, output_tokens=2)]
        r = run_meeting_agent(FakeProvider(replies), "short", "book test", max_steps=1)
        self.assertEqual(r.status, "step_limit_incomplete")
        self.assertEqual(len(r.booked), 0)

    def test_model_answer_does_not_mean_booking(self):
        r = run_meeting_agent(FakeProvider([ModelResponse(text="All done", input_tokens=1,
                                                          output_tokens=1)]), "test", "book me")
        self.assertEqual(r.status, "no_booking_verified")
        self.assertEqual(r.booked, [])


if __name__ == "__main__":
    unittest.main()
