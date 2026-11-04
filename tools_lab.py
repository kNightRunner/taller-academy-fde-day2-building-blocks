"""Day 2 Lab 2.2 — actual meeting agent and five deliberately broken variants."""
import json
from src.building_blocks.cli import parser, from_args
from src.building_blocks.meeting import goals, run_meeting_agent


def main():
    p = parser(__doc__)
    p.add_argument("--scenario", choices=["baseline", "gut_description", "relative_date",
                                           "force_conflict", "unsafe_3am", "remove_find_person"],
                   default="baseline")
    args = p.parse_args()
    provider = from_args(args)
    goal = goals()[{"gut_description": "baseline", "relative_date": "relative",
                    "force_conflict": "conflict", "remove_find_person": "baseline"}.get(args.scenario, args.scenario)]
    flags = {"gut_book_description": args.scenario == "gut_description",
             "remove_date_hint": args.scenario == "relative_date",
             "unsafe_3am": args.scenario == "unsafe_3am",
             "without_find_person": args.scenario == "remove_find_person"}
    result = run_meeting_agent(provider, args.scenario, goal, **flags)
    print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
