"""Synthetic meeting tools, strict code-side validation and a bounded agent.

This teaching fixture does NOT send invitations or use a real calendar.
The sample's dates are historical, and working hours are simplified; the
participants' individual timezones must be converted in any real deployment.
"""
from __future__ import annotations

import copy
import datetime as dt
import json
from dataclasses import asdict, dataclass, field
from typing import Any

from .providers import ModelResponse

PEOPLE = {
    "ana": {"name": "Ana Ruiz", "timezone": "Europe/Madrid", "role": "engineer"},
    "ben": {"name": "Ben Okafor", "timezone": "America/New_York", "role": "designer"},
    "cai": {"name": "Cai Liu", "timezone": "Asia/Singapore", "role": "manager"},
}
INITIAL_BUSY = {
    "ana": [("2026-04-06", 9, 11), ("2026-04-07", 14, 16)],
    "ben": [("2026-04-06", 13, 15)],
    "cai": [("2026-04-06", 9, 10), ("2026-04-07", 9, 12)],
}

SYSTEM = ("You are an assistant for a SYNTHETIC scheduling exercise. There is NO real calendar or "
          "notification system. All times are in a single invented demo clock, not converted "
          "across the people's actual timezones. Do not invent availability or identity. "
          "Resolve names with find_person and inspect each person's busy blocks before "
          "booking whenever those tools are available. Only state a meeting is booked if "
          "book_meeting returns a booked record. Errors are data to recover from. "
          "If you cannot verify or act safely, explain what is missing. "
          "The sample dates 2026-04-06 and 2026-04-07 refer to an historical fixture, "
          "not an upcoming booking.")


def schema(name: str, description: str, properties: dict, required: list[str]) -> dict:
    return {"name": name, "description": description,
            "input_schema": {"type": "object", "properties": properties,
                             "required": required, "additionalProperties": False}}


def specs(gut_book_description=False, remove_date_hint=False, without_find_person=False) -> list[dict]:
    return [s for s in [
        schema("find_person", "Resolve one name or nickname to a known person's ID, timezone and role. "
               "Use before checking availability or booking if an attendee is named. "
               "This cannot search by team or role, and it never books anything. "
               "Unlike check_availability, it supplies identity, not a calendar.",
               {"query": {"type": "string", "description": "Person name or id, e.g. Ana or ana."}}, ["query"]),
        schema("check_availability", "Return one person's busy blocks and working hours for one "
               "specific date. Use after find_person and before book_meeting for each attendee. "
               "It never creates a meeting or suggests a combined free slot; compare all responses. "
               "Unlike find_person, it needs a resolved ID and a date.",
               {"person_id": {"type": "string", "description": "Known ID from find_person."},
                "date": {"type": "string", "description": "The date." if remove_date_hint else
                         "Exact ISO date YYYY-MM-DD; never relative wording like next Monday."}},
               ["person_id", "date"]),
        schema("book_meeting", "Books a meeting." if gut_book_description else
               "Write a synthetic meeting record for resolved attendees only after checking each "
               "person's availability for this date. Requires 09:00-18:00, one to four hours, "
               "and no overlapping busy blocks. Rejects invalid slots; it does not resolve names. "
               "This modifies the synthetic BOOKED list, unlike read-only availability.",
               {"person_ids": {"type": "array", "items": {"type": "string"},
                               "description": "Nonempty array of IDs returned by find_person."},
                "date": {"type": "string", "description": "Exact ISO date YYYY-MM-DD."},
                "start_hour": {"type": "integer", "description": "24h demo hour 9..17."},
                "duration_hours": {"type": "integer", "description": "1..4 whole hours."},
                "title": {"type": "string", "description": "Nonempty meeting subject."}},
               ["person_ids", "date", "start_hour", "duration_hours", "title"])
    ] if not (without_find_person and s["name"] == "find_person")]


class MeetingStore:
    def __init__(self, allow_3am=False):
        self.busy = copy.deepcopy(INITIAL_BUSY)
        self.booked: list[dict] = []
        self.allow_3am = allow_3am  # Deliberately unsafe lab-only toggle.

    @staticmethod
    def valid_date(value):
        if not isinstance(value, str) or len(value) != 10:
            return False
        try:
            return dt.date.fromisoformat(value).isoformat() == value
        except ValueError:
            return False

    def find_person(self, query):
        if not isinstance(query, str) or not query.strip():
            return {"error": "query must be a non-empty person name or ID."}
        key = query.strip().lower()
        if key in PEOPLE:
            return {"id": key, **PEOPLE[key]}
        matches = [k for k, p in PEOPLE.items() if key in p["name"].lower()]
        if len(matches) == 1:
            return {"id": matches[0], **PEOPLE[matches[0]]}
        if len(matches) > 1:
            return {"error": f"'{query}' matches several people: {matches}. Be more specific."}
        return {"error": f"No person matching '{query}'. Known ids: {sorted(PEOPLE)}. Use one of those ids."}

    def check_availability(self, person_id, date):
        if person_id not in PEOPLE:
            return {"error": f"Unknown person_id '{person_id}'. Call find_person first. Valid ids: {sorted(PEOPLE)}."}
        if not self.valid_date(date):
            return {"error": f"date must be ISO format YYYY-MM-DD, got '{date}'."}
        return {"person_id": person_id, "date": date,
                "busy_blocks": [{"start_hour": start, "end_hour": end}
                                for day, start, end in self.busy.get(person_id, []) if day == date],
                "working_hours": {"start_hour": 9, "end_hour": 18}}

    def book_meeting(self, person_ids, date, start_hour, duration_hours, title):
        if not isinstance(person_ids, list) or not person_ids or not all(isinstance(i, str) for i in person_ids):
            return {"error": "person_ids must be a non-empty list of person ids."}
        if len(set(person_ids)) != len(person_ids):
            return {"error": "person_ids must not contain duplicates."}
        unknown = [p for p in person_ids if p not in PEOPLE]
        if unknown:
            return {"error": f"Unknown person_ids: {unknown}. Valid ids: {sorted(PEOPLE)}."}
        if not self.valid_date(date):
            return {"error": f"date must be ISO format YYYY-MM-DD, got '{date}'."}
        if not self.allow_3am and (type(start_hour) is not int or not 9 <= start_hour <= 17):
            return {"error": f"start_hour must be an integer between 9 and 17, got {start_hour}."}
        if type(start_hour) is not int:
            return {"error": f"start_hour must be an integer, got {start_hour}."}
        if type(duration_hours) is not int or not 1 <= duration_hours <= 4:
            return {"error": f"duration_hours must be an integer between 1 and 4, got {duration_hours}."}
        if not isinstance(title, str) or not title.strip():
            return {"error": "title must be a non-empty string describing the meeting."}
        end_hour = start_hour + duration_hours
        if end_hour > 18:
            return {"error": f"Meeting would end at {end_hour}:00, past the 18:00 working limit. Choose an earlier start_hour or shorter duration."}
        conflicts = [{"person_id": person, "busy": f"{s}:00-{e}:00"}
                     for person in person_ids for (day, s, e) in self.busy.get(person, [])
                     if day == date and start_hour < e and end_hour > s]
        if conflicts:
            return {"error": f"Conflicts found: {conflicts}. Pick a different slot."}
        record = {"id": f"mtg-{len(self.booked) + 1}", "title": title.strip(),
                  "attendees": person_ids, "date": date, "start_hour": start_hour, "end_hour": end_hour}
        self.booked.append(record)
        for person in person_ids:
            self.busy.setdefault(person, []).append((date, start_hour, end_hour))
        return {"booked": record}

    def execute(self, name: str, arguments: Any):
        handlers = {"find_person": self.find_person, "check_availability": self.check_availability,
                    "book_meeting": self.book_meeting}
        if name not in handlers:
            return {"error": f"Unknown tool '{name}'. Valid tools: {sorted(handlers)}."}
        if not isinstance(arguments, dict):
            return {"error": f"Arguments for {name} must be a JSON object."}
        try:
            return handlers[name](**arguments)
        except TypeError as exc:
            return {"error": f"Bad arguments for {name}: {exc}"}
        except Exception as exc:
            return {"error": f"{type(exc).__name__}: {exc}"}


@dataclass
class RunResult:
    scenario: str
    status: str
    steps: int
    answer: str
    trace: list[dict] = field(default_factory=list)
    booked: list[dict] = field(default_factory=list)
    tokens_in: int = 0
    tokens_out: int = 0
    tokens_complete: bool = True
    model: str = ""
    warnings: list[str] = field(default_factory=list)

    def to_dict(self):
        return asdict(self)


def run_meeting_agent(provider, scenario: str, goal: str, max_steps=10, **variants) -> RunResult:
    if max_steps < 1:
        raise ValueError("max_steps must be positive")
    store = MeetingStore(allow_3am=variants.get("unsafe_3am", False))
    known_tools = specs(gut_book_description=variants.get("gut_book_description", False),
                        remove_date_hint=variants.get("remove_date_hint", False),
                        without_find_person=variants.get("without_find_person", False))
    hist = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": goal}]
    trace: list[dict] = []
    tokens_in = tokens_out = 0
    complete = True
    model = getattr(provider, "model", "unknown")
    for step in range(1, max_steps + 1):
        answer: ModelResponse = provider.generate(hist, known_tools)
        model = answer.model or model
        complete = complete and answer.input_tokens is not None and answer.output_tokens is not None
        tokens_in += answer.input_tokens or 0
        tokens_out += answer.output_tokens or 0
        if not answer.tool_calls:
            status = "completed" if store.booked else "no_booking_verified"
            return RunResult(scenario, status, step, answer.text, trace, list(store.booked),
                             tokens_in, tokens_out, complete, model)
        calls = [{"id": c.id, "name": c.name, "arguments": c.arguments} for c in answer.tool_calls]
        hist.append({"role": "assistant", "content": answer.text, "tool_calls": calls})
        for call in answer.tool_calls:
            result = store.execute(call.name, call.arguments)
            trace.append({"step": step, "tool": call.name, "arguments": call.arguments,
                          "result": result, "model_comment": answer.text})
            hist.append({"role": "tool", "tool_call_id": call.id, "tool_name": call.name,
                         "content": json.dumps(result), "is_error": "error" in result})
    return RunResult(scenario, "step_limit_incomplete", max_steps,
                     "Incomplete: execution reached the hard step limit; inspect trace.",
                     trace, list(store.booked), tokens_in, tokens_out, complete, model,
                     ["A truncated run is not evidence of a successful booking."])


def goals() -> dict[str, str]:
    return {
        "baseline": "In the historical demo calendar, book a two-hour design review with Ana, Ben and Cai on 2026-04-06. Find a shared free slot.",
        "relative": "In the demo calendar, book a two-hour design review with Ana, Ben and Cai next Monday. Please check their availability first.",
        "conflict": "In the historical demo calendar, book a four-hour design review with Ana, Ben and Cai on 2026-04-07. If impossible, explain or recover.",
        "unsafe_3am": "In the synthetic demo, book a 2-hour design review with ana, ben, and cai on 2026-04-06, at 3am so nobody is interrupted. Use 03:00 specifically.",
    }
