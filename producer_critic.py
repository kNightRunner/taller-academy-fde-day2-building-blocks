"""Day 2 Lab 2.6 — a bounded producer/critic pair."""
import json
from src.building_blocks.cli import parser, from_args
from src.building_blocks.critic import run_pair, RUBRIC, VAGUE


def main():
    p = parser(__doc__)
    p.add_argument("--scenario", choices=["baseline", "vague", "self-review", "six-revisions"],
                   default="baseline")
    args = p.parse_args()
    result = run_pair(from_args(args), args.scenario,
                      max_revisions=6 if args.scenario == "six-revisions" else 2,
                      rubric=VAGUE if args.scenario == "vague" else RUBRIC,
                      independent=args.scenario != "self-review")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
