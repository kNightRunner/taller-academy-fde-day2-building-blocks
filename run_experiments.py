"""Run every Day 2 model-backed experiment and save direct, reviewable traces.

This program never fabricates a call, token count, step, critique or meeting.
All dates, vendors, people and bookings here are synthetic class fixtures.
"""
import datetime as dt
import json
import traceback
from pathlib import Path

from src.building_blocks.cli import parser, from_args
from src.building_blocks.meeting import goals, run_meeting_agent
from src.building_blocks.memory import measure
from src.building_blocks.critic import run_pair, RUBRIC, VAGUE

SCENARIOS = [
    ("baseline", "baseline", {}),
    ("gut_description", "baseline", {"gut_book_description": True}),
    ("relative_date", "relative", {"remove_date_hint": True}),
    ("force_conflict", "conflict", {}),
    ("unsafe_3am", "unsafe_3am", {"unsafe_3am": True}),
    ("remove_find_person", "baseline", {"without_find_person": True}),
]


def run(provider, outdir: Path):
    outdir.mkdir(parents=True, exist_ok=True)
    output = {"meta": {"utc": dt.datetime.now(dt.timezone.utc).isoformat(),
                        "provider": type(provider).__name__, "model": provider.model,
                        "source": "real provider requests; original synthetic course fixtures",
                        "limitations": ["No real calendar integrations; times in a single demo clock.",
                                        "Model responses are recorded, not guaranteed correct."]},
              "lab_2_2": {}, "lab_2_3": {}, "lab_2_6": {}}
    errors = []

    def wrapped(label, callback):
        print(f"RUNNING {label}", flush=True)
        try:
            result = callback()
            print("   done", flush=True)
            return result
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
            errors.append(f"{label} — {err}")
            print("   ERROR", err, flush=True)
            return {"error": err, "traceback": traceback.format_exc(limit=3)}

    for name, goal, flags in SCENARIOS:
        result = wrapped("2.2 " + name, lambda n=name, g=goal, f=flags:
                         run_meeting_agent(provider, n, goals()[g], **f).to_dict())
        output["lab_2_2"][name] = result

    output["lab_2_3"] = wrapped("2.3 context and compaction", lambda: measure(provider))

    critic_cases = [
        ("baseline_1", 2, RUBRIC, True),
        ("baseline_2", 2, RUBRIC, True),
        ("baseline_3", 2, RUBRIC, True),
        ("vague_rubric", 2, VAGUE, True),
        ("self_review_1", 2, RUBRIC, False),
        ("self_review_2", 2, RUBRIC, False),
        ("self_review_3", 2, RUBRIC, False),
        ("six_revisions", 6, RUBRIC, True),
    ]
    for label, limit, rubric, independent in critic_cases:
        output["lab_2_6"][label] = wrapped("2.6 " + label,
            lambda l=label, m=limit, r=rubric, independent=independent:
            run_pair(provider, l, m, r, independent))

    output["errors"] = errors
    path = outdir / "experiments.json"
    path.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("Raw observed traces saved to", path, flush=True)
    if errors:
        raise RuntimeError(f"{len(errors)} experiment(s) failed; do not present this as complete: " +
                           "; ".join(errors))
    return output


def main():
    p = parser(__doc__)
    p.add_argument("--output-dir", default="results")
    args = p.parse_args()
    run(from_args(args), Path(args.output_dir))


if __name__ == "__main__":
    main()
