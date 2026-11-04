"""Day 2 Lab 2.3 — provider-reported input-token growth and memory compaction."""
import json
from src.building_blocks.cli import parser, from_args
from src.building_blocks.memory import measure


def main():
    args = parser(__doc__).parse_args()
    print(json.dumps(measure(from_args(args)), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
