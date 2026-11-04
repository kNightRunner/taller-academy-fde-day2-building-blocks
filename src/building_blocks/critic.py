"""Lab 2.6: a writer and separate critic with an observable revision limit."""
from __future__ import annotations
from dataclasses import asdict, dataclass, field
import re

BRIEF = ("Write a 120-word internal note recommending whether our 8-person team "
         "should adopt a shared on-call rotation. Assume we currently have no "
         "rotation and incidents are handled by whoever notices them.")
RUBRIC = ("1. Make a clear recommendation (adopt / do not adopt).\n"
          "2. Give at least two concrete reasons tied to the brief.\n"
          "3. Name at least one real risk or cost.\n"
          "4. Use between 100 and 140 words.\n"
          "5. Invent no facts beyond the brief.")
VAGUE = "The note should be good and professional."
WRITER_SYSTEM = ("You are a concise internal communications writer. Write an internal note "
                 "that satisfies the user prompt. Output only the note, nothing else.")
CRITIC_SYSTEM = ("You are a strict independent reviewer. You did not write the draft. "
                 "Evaluate ONLY against the rubric. Start with exactly PASS or FAIL, "
                 "on its own line; if FAIL list failed rubric item numbers and specific reasons. "
                 "Do not rewrite the draft.")
SELF_CRITIC_SYSTEM = ("You wrote this draft yourself. Review your own work using the rubric. "
                      "Start exactly PASS or FAIL on its own line. For failures give numbered reasons.")


def ask(provider, system, user):
    res = provider.generate([{"role": "system", "content": system},
                             {"role": "user", "content": user}])
    return res.text.strip(), res.input_tokens, res.output_tokens


def word_count(s):
    return len(s.split())


def run_pair(provider, scenario, max_revisions=2, rubric=RUBRIC, independent=True):
    draft, inp, out = ask(provider, WRITER_SYSTEM, BRIEF)
    calls = 1
    tokens_in, tokens_out = inp or 0, out or 0
    measured = inp is not None and out is not None
    records = [{"type": "draft", "revision": 0, "words": word_count(draft), "text": draft}]
    last_verdict = ""
    for review_round in range(1, max_revisions + 1):
        verdict, i, o = ask(provider, CRITIC_SYSTEM if independent else SELF_CRITIC_SYSTEM,
                            f"RUBRIC:\n{rubric}\n\nDRAFT:\n{draft}")
        calls += 1
        tokens_in += i or 0
        tokens_out += o or 0
        measured = measured and i is not None and o is not None
        is_pass = verdict.lstrip().upper().startswith("PASS")
        records.append({"type": "critique", "round": review_round,
                        "independent": independent, "passed": is_pass, "text": verdict})
        last_verdict = verdict
        if is_pass:
            break
        draft, i, o = ask(provider, WRITER_SYSTEM,
                          f"ORIGINAL BRIEF:\n{BRIEF}\n\nYOUR PREVIOUS DRAFT:\n{draft}\n\n"
                          f"REVIEWER NOTES:\n{verdict}\n\nRewrite to satisfy each rubric item. "
                          "Output only the revised note.")
        calls += 1
        tokens_in += i or 0
        tokens_out += o or 0
        measured = measured and i is not None and o is not None
        records.append({"type": "draft", "revision": review_round,
                        "words": word_count(draft), "text": draft})
    passed = last_verdict.lstrip().upper().startswith("PASS")
    return {"scenario": scenario, "model": provider.model,
            "rubric": rubric, "independent": independent,
            "max_revisions": max_revisions, "calls": calls, "tokens_in": tokens_in,
            "tokens_out": tokens_out, "tokens_complete": measured, "passed": passed,
            "status": "critic_passed" if passed else "limit_reached_human_review_required",
            "first_words": records[0]["words"], "final_words": word_count(draft),
            "draft": draft, "records": records,
            "objective_word_range_ok": 100 <= word_count(draft) <= 140}
