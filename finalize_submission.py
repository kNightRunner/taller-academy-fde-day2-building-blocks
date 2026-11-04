"""Fill the Day 2 written submission strictly from actual saved provider traces.

Never invent an observation or mark model performance as correct without evidence.
"""
from __future__ import annotations

import json
from pathlib import Path

START = "<!-- MEASURED_START -->"
END = "<!-- MEASURED_END -->"
ROOT = Path(__file__).parent


def flag(value):
    return "yes" if value else "no"


def tool_sequence(record):
    return " → ".join(e["tool"] for e in record.get("trace", [])) or "none"


def md_json(obj):
    return "```json\n" + json.dumps(obj, indent=2, ensure_ascii=False) + "\n```"


def one_event_where(record, test):
    for e in record.get("trace", []):
        if test(e):
            return e
    return None


def describe_tools(records):
    base = records.get("baseline", {})
    out = ["### Lab 2.2 — Observations from real tool-calling runs", "",
           "The following rows and notes are generated from the stored call trace; no example calls are synthesized.", "",
           "| Scenario | Status | Steps | Tool calls | Model input / output tokens | Bookings |",
           "| --- | --- | ---: | ---: | ---: | ---: |"]
    for name, r in records.items():
        if "error" in r:
            out.append(f"| {name} | ERROR | — | — | — | — |")
        else:
            out.append(f"| {name} | {r['status']} | {r['steps']} | {len(r['trace'])} | "
                       f"{r['tokens_in']} / {r['tokens_out']} | {len(r['booked'])} |")
    if "error" in base:
        return "\n".join(out + ["Baseline failed; the trace cannot support behavioral claims."])
    by_step = {}
    for e in base.get("trace", []):
        by_step.setdefault(e["step"], []).append(e["tool"])
    batched = {k: v for k, v in by_step.items() if len(v) > 1}
    find_steps = [e["step"] for e in base.get("trace", []) if e["tool"] == "find_person"]
    check_steps = [e["step"] for e in base.get("trace", []) if e["tool"] == "check_availability"]
    order_ok = bool(find_steps and check_steps and min(find_steps) <= min(check_steps))
    out.extend(["", "**Four observations:**", "",
                f"1. **Actual call sequence:** `{tool_sequence(base)}`. There were "
                f"{len(base.get('trace', []))} tool calls across {base.get('steps')} model turns. "
                f"`find_person` was called no later than the first availability query: **{flag(order_ok)}**.",
                "2. **Parallelizable requests:** Calls requested during a single model turn are batched. " +
                ("Observed batches: " + "; ".join(f"step {k} = {v}" for k, v in batched.items()) if batched
                 else "No multiple-call turn was observed in this baseline."),
                "3. **Slot reasoning:** The model's own text accompanying tool calls is captured in the raw trace. "
                "The tools return blocks, not a combined free slot. The confirmed in-memory booking, if any, is:",
                "", md_json(base.get("booked", [])), "",
                f"4. **Why steps differ from calls:** {base.get('steps')} means model iterations, while "
                f"{len(base.get('trace', []))} means individual tool calls; one turn can request zero, one or "
                "multiple tools, and the final text-only response also consumes a model turn.", ""])
    layers = {
        "gut_description": "Preventive tool-description instruction weakened; runtime slot/conflict validation remained active.",
        "relative_date": "The schema permits strings; runtime ISO-date validation rejects unsupported relative strings.",
        "force_conflict": "Runtime availability/conflict validation rejects overlaps; model can retry or explain.",
        "unsafe_3am": "The real code-side start-hour guard was deliberately disabled only in this isolated fixture.",
        "remove_find_person": "The missing model-visible resolver changes model planning; the runtime still validates IDs.",
    }
    out.extend(["**Five controlled experiments:**", ""])
    for name, desc in layers.items():
        r = records.get(name, {})
        out.append(f"**{name}** — {desc}")
        if "error" in r:
            out.extend(["", "*Experiment failed instead of producing a valid trace:* " + r["error"], ""])
            continue
        errors = [e for e in r["trace"] if "error" in e["result"]]
        out.append(f"Observed: `{tool_sequence(r)}`; status `{r['status']}`; "
                   f"{len(errors)} tool error(s); {len(r['booked'])} booking(s).")
        for e in errors[:6]:
            out.append(f"- Step {e['step']}: `{e['tool']}` returned **`{e['result']['error']}`**.")
        if r.get("booked"):
            out.append("- Actual synthetic write: " + "`" + json.dumps(r["booked"], ensure_ascii=False) + "`.")
        if name == "relative_date":
            formats = [e["arguments"].get("date") for e in r["trace"]
                       if e["tool"] == "check_availability" and isinstance(e.get("arguments"), dict)]
            out.append("- Dates the model actually supplied to check_availability: " + repr(formats) + ".")
        if name == "remove_find_person":
            guessed = [e["arguments"].get("person_id") for e in r["trace"]
                       if e["tool"] == "check_availability" and isinstance(e.get("arguments"), dict)]
            out.append("- IDs sent without the model-visible resolver: " + repr(guessed) + ".")
        out.append("\n**Exact model final response:**\n\n> " +
                   (r.get("answer", "").replace("\n", "\n> ") or "(empty)") + "\n")
    return "\n".join(out)


def describe_memory(r):
    out = ["### Lab 2.3 — Real provider token counts and compaction", ""]
    if "error" in r:
        return "\n".join(out + ["Lab 2.3 could not run: " + r["error"]])
    out.extend([f"**Model:** `{r['model']}`. **Counting method:** {r['token_measurement_method']}.", "",
                "| Step | Input tokens this prompt | Cumulative input tokens |",
                "| ---: | ---: | ---: |"])
    for row in r["table"]:
        out.append(f"| {row['step']} | {row['input_tokens_this_turn']:,} | {row['cumulative_input_tokens']:,} |")
    out.extend(["", f"- Final prompt / first prompt: **{r['last_vs_first']}×**.",
                f"- Cumulative processed / final prompt alone: **{r['cumulative_vs_last']}×**.",
                "- Accumulated input grows faster than step count because earlier messages are re-sent at each step.",
                "- Pinned goal: `" + r["standard"]["pinned"]["content"] +
                "` — this must survive so compaction does not silently change the task.",
                "", "**Compaction variants (all measured):**", "",
                "| Variant | Before | After | Saved | Saved % |", "| --- | ---: | ---: | ---: | ---: |"])
    for label in ["standard", "aggressive", "strict"]:
        item = r[label]
        out.append(f"| {label} (recent={item['recent_turns']}) | {item['before_tokens']:,} | "
                   f"{item['after_tokens']:,} | {item['saved_tokens']:,} | {item['saved_percent']}% |")
    missing = r.get("potentially_lost_literals", [])
    out.extend(["", "**Specific loss/blur check:** " +
                ("At least one literal from the fixture was absent in the standard summary: `" +
                 "`, `".join(missing) + "`. Missing numeric context could change which contract is urgent. "
                 "Exact source-to-vendor associations need review." if missing else
                 "The targeted numeric/date literals checked were retained; examine caveats, relationships and "
                 "untracked notes for subtler losses before claiming perfect compaction."),
                "", "**Does a stricter instruction help?** Compare the two generated summaries below. "
                "This is a prompt-level control, not a guarantee of completeness.", "",
                f"**Projection (20 steps):** initial {r['table'][0]['input_tokens_this_turn']} tokens; "
                f"average observed step growth {r['projection']['observed_increment_mean']:.2f} "
                f"tokens; projected cumulative **{r['projection']['projected_20_step_total']:,} input tokens** "
                "for steps 0–20 using the arithmetic series described above. "
                "This 20-step quantity is a forecast, not a measured 20-step run.", ""])
    for label in ["standard", "aggressive", "strict"]:
        item = r[label]
        out.extend(["#### Actual " + label + " summary", "", "> " +
                    item["summary"].replace("\n", "\n> "), ""])
    return "\n".join(out)


def describe_critic(records):
    out = ["### Lab 2.6 — Real producer/critic observations", "",
           "| Scenario | Review mode | PASS | Calls | First/final words | Input/output tokens |",
           "| --- | --- | --- | ---: | --- | ---: |"]
    for name, r in records.items():
        if "error" in r:
            out.append(f"| {name} | ERROR | — | — | — | — |")
        else:
            out.append(f"| {name} | {'independent' if r['independent'] else 'self-review'} | "
                       f"{flag(r['passed'])} | {r['calls']} | {r['first_words']}/{r['final_words']} | "
                       f"{r['tokens_in']}/{r['tokens_out']} |")
    bases = [r for n, r in records.items() if n.startswith("baseline_") and "error" not in r]
    selves = [r for n, r in records.items() if n.startswith("self_review_") and "error" not in r]
    if bases and selves:
        failures_b = sum(any(e["type"] == "critique" and not e["passed"] for e in b["records"]) for b in bases)
        failures_s = sum(any(e["type"] == "critique" and not e["passed"] for e in s["records"]) for s in selves)
        out.extend(["", f"- **Independent reviewer:** rejected at least one draft in "
                    f"**{failures_b}/{len(bases)}** observed runs.",
                    f"- **Self-review framing:** rejected at least one draft in "
                    f"**{failures_s}/{len(selves)}** observed runs. These frequencies describe "
                    "this small sample, not a causal proof of critic independence."])
    out.extend(["", "**Why more calls?** The producer writes once; each review adds a model call, "
                "and each failed review adds a rewrite call. The extra spend buys targeted feedback "
                "and a recorded opportunity to fix errors, but the critic itself may miss or invent issues.",
                "", "**Objective rubric check:** The measured first/final word counts allow the 100–140-word "
                "requirement to be independently checked; the other four items require semantic review. "
                "An unsuccessful verdict at the revision ceiling is flagged for a person.", ""])
    for name, r in records.items():
        out.append("#### " + name)
        if "error" in r:
            out.extend(["", "Experiment errored: " + r["error"], ""])
            continue
        out.extend(["", f"- Status: `{r['status']}`; final word count {r['final_words']}; "
                    f"objective length criterion met: {flag(r['objective_word_range_ok'])}.",
                    "- Exact observed draft(s) and critique(s):", ""])
        for item in r["records"]:
            title = (f"Draft revision {item['revision']} ({item['words']} words)" if item["type"] == "draft"
                     else f"Critic round {item['round']} — PASS={flag(item['passed'])}")
            out.extend([f"**{title}:**", "", "> " + item["text"].replace("\n", "\n> "), ""])
    return "\n".join(out)


def build_report(data):
    meta = data.get("meta", {})
    out = ["## Direct experimental evidence", "",
           "All outputs below are generated mechanically from the provider response and the trusted tool trace. "
           "No bookable real meetings, external accounts or client data were used.", "",
           f"- UTC experiment timestamp: `{meta.get('utc', 'unknown')}`",
           f"- Provider: `{meta.get('provider', 'unknown')}`; model: `{meta.get('model', 'unknown')}`",
           "- This is a **synthetic exercise** and the calendar dates are historical fixtures.", "",
           describe_tools(data.get("lab_2_2", {})), "",
           describe_memory(data.get("lab_2_3", {})), "",
           describe_critic(data.get("lab_2_6", {})), ""]
    if data.get("errors"):
        out.extend(["**Execution failures:**", ""] + ["- " + e for e in data["errors"]])
    return "\n".join(out)


def main():
    source = ROOT / "results" / "experiments.json"
    if not source.exists():
        raise SystemExit("No real experiment trace exists. Run python run_experiments.py first.")
    data = json.loads(source.read_text(encoding="utf-8"))
    if data.get("errors"):
        raise SystemExit("Some experiments failed: cannot mark the submission complete.")
    if any("error" in r for r in data["lab_2_2"].values()) or "error" in data["lab_2_3"] or \
       any("error" in r for r in data["lab_2_6"].values()):
        raise SystemExit("One or more model-backed experiments failed; report must not be finalized.")
    result = build_report(data)
    (ROOT / "results" / "EVIDENCE.md").write_text(result + "\n", encoding="utf-8")
    sub_path = ROOT / "SUBMISSION.md"
    submission = sub_path.read_text(encoding="utf-8")
    if START not in submission or END not in submission:
        raise SystemExit("SUBMISSION.md has no section markers; refusing to overwrite")
    first, rest = submission.split(START, 1)
    _, last = rest.split(END, 1)
    updated = first + START + "\n" + result + "\n" + END + last
    updated = updated.replace("- [ ] Actual provider-backed behavior and measured token counts (filled by the experiment workflow, not guessed).",
                              "- [x] Actual provider-backed behavior and measured token counts from stored provider traces.")
    sub_path.write_text(updated, encoding="utf-8")
    print("Updated SUBMISSION.md with real evidence; saved results/EVIDENCE.md")


if __name__ == "__main__":
    main()
