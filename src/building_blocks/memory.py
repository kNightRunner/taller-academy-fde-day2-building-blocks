"""Lab 2.3: provider-reported input token counts, compaction and projection.

Anthropic has a separate count_tokens endpoint. On Ollama, input counts come
from a real chat prefill with one predicted token, not character estimates;
this is not free in time or compute, but gives the actual model's counter.
"""
from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass

GOAL = ("Audit three synthetic cloud vendors and recommend which contract to "
        "renegotiate first. Consider spend, growth trend, and contract end date.")
SIMULATED_RUN = [
    ("I'll start by pulling total spend per vendor.",
     {"vendor_spend": [{"vendor": "Northwind Cloud", "usd": 412000},
                       {"vendor": "Acme Compute", "usd": 288500},
                       {"vendor": "Zephyr Hosting", "usd": 96200}],
      "period": "2025-04-01..2026-03-31", "currency": "USD",
      "note": "Excludes support contracts billed separately."}),
    ("Now the month-by-month trend for the largest vendor.",
     {"vendor": "Northwind Cloud",
      "monthly_usd": [31200, 32100, 30800, 33400, 35900, 34100,
                      36800, 38200, 37500, 39900, 41100, 42000],
      "trend": "+34.6% over 12 months", "driver": "object storage egress"}),
    ("Checking the same trend for the second vendor.",
     {"vendor": "Acme Compute",
      "monthly_usd": [25100, 24800, 24200, 24500, 23900, 24100,
                      23800, 24000, 23600, 23900, 23400, 23200],
      "trend": "-7.6% over 12 months", "driver": "workload migration off VMs"}),
    ("Pulling contract end dates and notice periods.",
     {"contracts": [{"vendor": "Northwind Cloud", "ends": "2026-09-30", "notice_days": 90,
                     "auto_renew": True, "discount_tier": "committed-use 15%"},
                    {"vendor": "Acme Compute", "ends": "2027-02-28", "notice_days": 30,
                     "auto_renew": False, "discount_tier": "none"},
                    {"vendor": "Zephyr Hosting", "ends": "2026-05-15", "notice_days": 60,
                     "auto_renew": True, "discount_tier": "startup credit"}]}),
    ("Looking for committed-use shortfalls or overage penalties.",
     {"commitments": [{"vendor": "Northwind Cloud", "committed_usd": 360000,
                       "actual_usd": 412000, "overage_usd": 52000,
                       "overage_rate": "list price, no discount"},
                      {"vendor": "Acme Compute", "committed_usd": 0, "actual_usd": 288500}],
      "note": "Northwind overage is billed at undiscounted list price."}),
    ("Checking whether any team has migration plans that change the picture.",
     {"planned_migrations": [{"from": "Acme Compute", "to": "Northwind Cloud",
                              "team": "data-platform", "estimated_monthly_usd": 8400,
                              "starts": "2026-06-01"}],
      "note": "Would increase Northwind spend further before renewal."}),
]
STANDARD = ("You compress an AI agent's working history. Preserve every concrete figure, "
            "date, name and finding that could matter later. Drop narration and restatements. "
            "Output a dense bulleted recap, nothing else.")
STRICT = ("Summarize the agent history into compact bullets. You MUST copy ALL monetary "
          "amounts, currency signs, exact dates, notice periods, and percentages VERBATIM "
          "without rounding or dropping any. Preserve vendor-to-fact relationships. "
          "Also preserve strategic caveats. Never invent missing data.")


def history(entries):
    messages = [{"role": "user", "content": GOAL}]
    for commentary, tool_data in entries:
        messages.append({"role": "assistant", "content": commentary})
        messages.append({"role": "user", "content": json.dumps(tool_data, sort_keys=True)})
    return messages


def token_count(provider, messages):
    if hasattr(provider, "client"):
        # Official server-side tokenizer; not a guessed chars/4 ratio.
        from .providers import AnthropicProvider
        if isinstance(provider, AnthropicProvider):
            system, converted = provider._anthropic_messages(messages)
            kwargs = {"model": provider.model, "messages": converted}
            if system:
                kwargs["system"] = system
            return provider.client.messages.count_tokens(**kwargs).input_tokens
    # Ollama has no separate public count_tokens endpoint as in Anthropic.
    # Chat with num_predict=1 reports the input tokens actually evaluated.
    data = provider._request("/api/chat", {"model": provider.model,
                                           "messages": provider._ollama_messages(messages),
                                           "stream": False,
                                           "options": {"temperature": 0, "num_predict": 1}})
    count = data.get("prompt_eval_count")
    if not isinstance(count, int):
        raise ValueError("Provider did not return an actual prompt token count")
    return count


def prompt_projection(counts, target=20):
    """Linear extrapolation of per-step prompt size, then triangular cumulative sum.

    This is a forecast, not an observed 20-step result.
    """
    increments = [(b - a) for a, b in zip(counts, counts[1:])]
    mean = sum(increments) / len(increments)
    return {"observed_increment_mean": mean,
            "projected_20_step_total": round((target + 1) * counts[0] +
                                             mean * target * (target + 1) / 2),
            "method": "Sum over k=0..20 of prompt_0 + k * mean observed per-step increase."}


def compact(provider, recent_turns=2, instruction=STANDARD):
    if not 1 <= recent_turns < len(SIMULATED_RUN):
        raise ValueError("recent_turns should be in [1, 5]")
    full = history(SIMULATED_RUN)
    pinned, middle, recent = full[0], full[1:-(recent_turns * 2)], full[-(recent_turns * 2):]
    prompt = [{"role": "system", "content": instruction},
              {"role": "user", "content": "Compress this historical simulation:\n" +
               json.dumps(middle, indent=2, ensure_ascii=False)}]
    response = provider.generate(prompt)
    summary = response.text.strip()
    if not summary:
        raise ValueError("Model returned empty compaction summary")
    rebuilt = [pinned, {"role": "assistant", "content": "[EARLIER WORK]\n" + summary}] + recent
    before = token_count(provider, full)
    after = token_count(provider, rebuilt)
    if after >= before:
        warning = "Compaction did not reduce the context in this run."
    else:
        warning = None
    return {"recent_turns": recent_turns, "instruction": instruction,
            "pinned": pinned, "summarized_message_count": len(middle),
            "verbatim_message_count": len(recent), "summary": summary,
            "before_tokens": before, "after_tokens": after,
            "saved_tokens": before - after,
            "saved_percent": round(100 * (1 - after / before), 2),
            "model_input_tokens_for_summary": response.input_tokens,
            "model_output_tokens_for_summary": response.output_tokens,
            "warning": warning}


def measure(provider):
    table = []
    cumulative = 0
    counts = []
    for step in range(len(SIMULATED_RUN) + 1):
        tokens = token_count(provider, history(SIMULATED_RUN[:step]))
        counts.append(tokens)
        cumulative += tokens
        table.append({"step": step, "input_tokens_this_turn": tokens,
                      "cumulative_input_tokens": cumulative})
    standard = compact(provider, recent_turns=2, instruction=STANDARD)
    aggressive = compact(provider, recent_turns=1, instruction=STANDARD)
    strict = compact(provider, recent_turns=2, instruction=STRICT)
    facts = ["412000", "288500", "96200", "+34.6%", "-7.6%", "2026-09-30",
             "2027-02-28", "2026-05-15", "52000", "360000", "8400", "2026-06-01",
             "90", "30", "60"]
    lost = [fact for fact in facts if fact not in standard["summary"].replace(",", "")]
    return {"provider": provider.__class__.__name__, "model": provider.model,
            "token_measurement_method": "official Anthropic count_tokens endpoint" if hasattr(provider, "client")
             else "Ollama /api/chat prompt_eval_count, one-token prefill per measurement",
            "table": table, "last_vs_first": round(counts[-1] / counts[0], 2),
            "cumulative_vs_last": round(cumulative / counts[-1], 2),
            "projection": prompt_projection(counts),
            "standard": standard, "aggressive": aggressive, "strict": strict,
            "potentially_lost_literals": lost,
            "raw_source_is_synthetic": True}
