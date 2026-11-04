# Taller Academy — AI Agents for Beginners — Day 2: Building Blocks

A **complete, reproducible course project** for the six Day 2 lab exercises: two tool definitions, a bounded meeting agent, deliberate tool breakages, context-window compaction, decomposition and handoffs, and producer–critic evaluation.

**Read [`SUBMISSION.md`](SUBMISSION.md) for the six written answers.** The three model-backed labs have scripts that record their own evidence instead of inventing results. On GitHub, a dedicated workflow can run every scenario with Ollama and commit that evidence back to this repository.

> **Privacy and scope:** This project uses entirely **synthetic** people, calendars, vendors and companies. Dates in April 2026 are historical fixtures taken from the exercise; this agent does not schedule real meetings. The fixture deliberately ignores actual cross-timezone alignment—do not connect it to a production calendar without timezone conversion, authentication, authorization, consent and idempotency.

## Project contents

| Path | Purpose |
| --- | --- |
| `SUBMISSION.md` | All six lab answers, with a generated measured-results section |
| `tools_lab.py` | Lab 2.2 — runnable tool agent and all five deliberate breaking variants |
| `memory_lab.py` | Lab 2.3 — measured input-token growth, compaction and projection |
| `producer_critic.py` | Lab 2.6 — independent producer/critic with a strict revision limit |
| `run_experiments.py` | Runs all **15 model-backed scenarios** and records their exact outputs |
| `finalize_submission.py` | Converts stored evidence to an updated submission **without inventing observations** |
| `src/building_blocks/meeting.py` | Synthetic calendar, tool definitions, validation and bounded model loop |
| `src/building_blocks/memory.py` | Synthetic vendor history, provider token counting and compaction |
| `src/building_blocks/critic.py` | Writer, independent critic, rubric and bounded revision mechanics |
| `src/building_blocks/providers.py` | Minimal Ollama REST adapter and optional Anthropic SDK adapter |
| `tests/` | Fast deterministic test suite (no API key or model required) |
| `.github/workflows/live_model_lab.yml` | One-time-on-push and manual real-model evidence generation |
| `.github/workflows/tests.yml` | Offline tests in CI |

## Quick start — free Ollama

Install Ollama from its official distribution, then start it and pull a tool-capable model:

```bash
ollama serve       # run in a separate terminal if Ollama is not already running
ollama pull qwen2.5:3b
```

Use Python 3.9+ (3.12 recommended). The Ollama path requires **no Python dependencies** and no paid API key.

```bash
python3 -m unittest discover -s tests -v
python3 tools_lab.py --model qwen2.5:3b
python3 tools_lab.py --scenario gut_description --model qwen2.5:3b
python3 memory_lab.py --model qwen2.5:3b
python3 producer_critic.py --model qwen2.5:3b
```

Run all experiments and fill in the measured-results section:

```bash
python3 run_experiments.py --model qwen2.5:3b
python3 finalize_submission.py
```

The commands produce `results/experiments.json` (raw observations) and `results/EVIDENCE.md` (readable trace), and populate the measured-results section in `SUBMISSION.md`.

**Important:** Ollama may make incorrect tool decisions: that is part of the learning exercise. The tests verify the Python tool boundaries; the model trace records the model's decisions, not a guarantee those decisions were correct. A no-booking answer is not treated as proof of a successful booking.

## Alternative — Anthropic

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-anthropic.txt
export ANTHROPIC_API_KEY='...'   # set privately in your shell; never commit
python3 run_experiments.py --provider anthropic --model YOUR_ACCESSIBLE_MODEL
python3 finalize_submission.py
```

A model identifier is not hardcoded in the Anthropic route; use a model available to your own account. This project has no need to store any token or API key in files.

## What is actually counted?

- **Anthropic:** provider `messages.count_tokens`, reported for each context before generation.
- **Ollama:** provider `prompt_eval_count` from a real `/api/chat` call with `num_predict=1`. This is a real prompt token count returned by Ollama, not an estimate such as `characters / 4`; these prefill requests use real compute time. Results reflect Ollama's chat format and model-specific tokenization, and are not directly interchangeable with Anthropic's.
- All model calls in `run_experiments.py` preserve actual input/output counters where reported; missing counters are marked as unavailable, never filled with fake values.

## How the experiment suite maps to the rubric

**Lab 2.2:** six meeting agent runs: baseline, gut description, remove date hint, force a conflict, disable start-hour validation **only in the fictional fixture**, and remove the identity tool from model-visible specs. The JSON trace records step, tool, arguments, output, errors and actual synthetic writes.

**Lab 2.3:** seven accumulated-history measurements; baseline compaction keeping two recent turns, aggressive compaction keeping one, stricter monetary/date-preserving instruction, and a **calculated** 20-step forecast based on measured prompt growth. The synthetic goal remains pinned.

**Lab 2.6:** three independent critic baselines, one vague-rubric variant, three self-review variants, and one six-revision-limit variant. Each records all draft and review texts, verdicts, word counts, model calls and tokens. A critic verdict is not automatically accepted as factual truth.

The three design labs, **2.1, 2.4 and 2.5**, are fully written in the submission without needing model calls.

## GitHub Actions — let GitHub run the model

After **all files** are pushed to a new public repository on `main`, commit `.github/workflows/live_model_lab.yml` **last**. That starts the `Day 2 measured lab evidence` workflow once. It installs Ollama on an ephemeral Linux runner, runs all fifteen scenarios, generates the evidence and commits `SUBMISSION.md` and the two results files. `workflow_dispatch` can rerun the workflow manually. Make sure the repo permits GitHub Actions to write repository contents (Settings → Actions → General → Workflow permissions → Read and write permissions, where needed). Hosted runners may impose CPU/time limits; if installation or the long experiment suite fails, the workflow will show that explicitly rather than inventing results. You can use the same scripts locally.

## Safety decisions

The tool layer is a deterministic Python boundary: a model can **request**, but it cannot directly write. The demonstration writes only into an in-memory list. Under the deliberate 3 a.m. validation-break scenario, unsafe behavior is confined to a newly created synthetic store. No emails, invitations, real events, secret keys, or live system data are accessed.

## License / assessment

Educational, independent lab implementation and written assessment. The `SUBMISSION.md` document is meant to be reviewed against the Day 2 rubric; include recorded results before submitting for grading.
