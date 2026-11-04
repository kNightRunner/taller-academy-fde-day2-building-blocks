# Day 2 — Building Blocks | Written Lab Submission

**Course:** AI Agents for Beginners  
**Module:** Day 2 — Building Blocks  
**Evidence policy:** Only synthetic data and documented experiments are used. Model behavior and token counts are copied from actual runs, never invented. Historical calendar dates remain intentionally fixed to the lesson's simulation.  
**Scripts:** `tools_lab.py`, `memory_lab.py`, `producer_critic.py`, `run_experiments.py`.

## Lab 2.1 — Design two meeting tools

I designed a read-only identity resolver and a read-only availability checker. Creating a calendar event is a different and riskier operation, so the booking API used in Lab 2.2 has an additional code-side validation gate.

### Tool 1: `find_person`

**Description for the model (four sentences):** Resolve one named attendee to a stable internal person ID, timezone and role. Call this before any tool needing `person_id`, especially when the user gives a name or nickname rather than an ID. It supports exact IDs and name matching, but it cannot search an entire team or infer identities from a role. Unlike `check_availability`, it does not read calendars or create events.

**Argument schema:**

```json
{
  "name": "find_person",
  "input_schema": {
    "type": "object",
    "properties": {"query": {"type": "string", "description": "Nonempty person name or stable ID, for example Ana or ana."}},
    "required": ["query"],
    "additionalProperties": false
  }
}
```

### Tool 2: `check_availability`

**Description for the model (four sentences):** Retrieve one resolved person's busy blocks and demo working hours on an exact date. Call this after resolving the attendee's ID and before choosing a shared meeting slot. It accepts one person and one date per call; it does not combine multiple people's schedules or choose a free slot. Unlike `book_meeting`, it is read-only and creates no invitations.

**Argument schema:**

```json
{
  "name": "check_availability",
  "input_schema": {
    "type": "object",
    "properties": {
      "person_id": {"type": "string", "description": "Known attendee ID returned by find_person."},
      "date": {"type": "string", "description": "Exact ISO calendar date YYYY-MM-DD; relative dates are not accepted.", "format": "date"}
    },
    "required": ["person_id", "date"],
    "additionalProperties": false
  }
}
```

**(a) Failure case.** Example exact returned error: `date must be ISO format YYYY-MM-DD, got 'next Monday'.` The agent can recover by obtaining or asking for the exact date rather than repeating an unusable relative value. If `person_id` is wrong, the exact returned error is `Unknown person_id 'unknown'. Call find_person first. Valid ids: ['ana', 'ben', 'cai'].` The available IDs and next action are explicit.

**(b) Confusable neighbour.** `book_meeting` can be mistaken for `check_availability`. The boundary in the first tool is “It resolves identity only; it never reads a calendar or makes a booking.” The boundary in the second tool is “It only reads one person's busy blocks; it never writes a booking or sends a notification.” The model cannot mistake either for `book_meeting` if it follows these constraints.

**(c) A tool I would refuse to expose.** I would not expose `cancel_all_meetings(person_ids, from_date, to_date)`. A wrong call could erase many people's commitments or issue notifications, making it high impact and not reliably reversible. A human should approve each cancellation in a separate, tightly scoped interface instead.

**(d) Blast radius when arguments are valid but wrong.** `find_person("ben")` would return the wrong *valid* attendee if the intended person was Ana; subsequent actions might expose Ben's availability or misroute a meeting. `check_availability("ana", "2026-04-07")` could make the agent choose a slot on the wrong valid day even though the response passes schema validation. Input correctness is more than type correctness: names, intent and date must be cross-checked against the user's request.

**Real-system caveat.** Ana, Ben and Cai have different timezones. The educational fixture uses a shared demonstration clock instead of doing timezone conversions; shipping this to a real calendar would be incorrect without UTC/timezone normalization, time-window alignment and explicit confirmation before writes.

---

## Lab 2.2 — Tool-using agent and deliberate breakages

The implementation is [`tools_lab.py`](tools_lab.py), backed by [`src/building_blocks/meeting.py`](src/building_blocks/meeting.py). The model can request `find_person`, `check_availability` and `book_meeting`. Python independently validates input types, identity, date formats, working hours, length and conflicts before writing to an in-memory `BOOKED` list. Every scenario starts with a clean store; no real invitations or outside changes occur. The five breaking experiments are separate synthetic runs, not risky production actions.

**Observed call order, repeated/batched calls, slot reasoning and step/call counts:** see **Measured results** below after the model runner executes. The model can request several tools in one step, so **model calls are not the same as tool calls**. Note that the fixed example date 2026-04-06 is historical; the lab deliberately replays it as a fixture.

**Experiment intent and expected catching layer (actual model behavior is documented after execution):**

- **(a) Gut booking description:** change only the `book_meeting` tool description to `Books a meeting.` The tool's actual conflict and range checks remain in Python. If the model prematurely books a conflicting slot, **Python validation**, not the wording, prevents the write; the description is the weakened preventive layer.
- **(b) Remove date format hint:** ask about `next Monday` with only `The date.` in the availability argument description. The **runtime ISO-date validator** catches a relative string if the model supplies one; the input schema still expects a string, which by itself cannot guarantee ISO formatting.
- **(c) Force four-hour conflict:** sample Ana/Cai have commitments on 2026-04-07. The **runtime conflict check** catches an overlap and provides the conflicting blocks; the model might recover, ask to change the date, or stop. Which happened is recorded below.
- **(d) Remove the start-hour guard:** intentionally disable the 09–17 range check *inside the local synthetic store only*. The value `3` is a valid JSON integer even though it violates the described business rule. **Nothing in the remaining schema guarantees that business-hour rule**; if the model books at 03:00, the bad write demonstrates why tool code is the authority. This unsafe variant is NEVER used with a live calendar.
- **(e) Delete identity tool from the model's tool list:** the code still knows the person records, but the model has no advertised name-resolution tool. If it invents `person_id` values, the **runtime ID validation** will still catch unknown IDs, while valid guessed IDs can slip through — another reason the model should explicitly verify the user's identity intent.

---

## Lab 2.3 — Context growth and compaction

The six-entry simulated vendor history lives in [`src/building_blocks/memory.py`](src/building_blocks/memory.py). It contains **fictional vendor names and invented finances**, not client data. The lab measures per-turn input tokens from the provider's own counters: `messages.count_tokens` on Anthropic, or `prompt_eval_count` from a one-token Ollama prefill. The Ollama method uses real model processing instead of estimating tokens from characters; the additional prefills use compute time and should not be mistaken for Anthropic's free counting endpoint.

The run records the seven context sizes, total accumulated token input, and the 6-step ratios. Growth of a *single* prompt can be approximately linear as history accumulates, while the sum of repeated full-history prompts grows approximately quadratically with the number of steps. The original goal is pinned throughout compaction. Losing the oldest goal message would change the purpose of later steps; only older supporting history is summarized.

**Compaction experiments:**

- Keep two recent turns verbatim and summarize older history (baseline).
- Keep only one recent turn verbatim (aggressive variant). This generally saves more tokens at the cost of forcing the model to reconstruct additional details from its summary.
- Strengthen the summarizer's system instruction to preserve every money amount and exact date verbatim. Compare both produced summaries against the *source records* to see whether crucial information survives.

**Cost projection method:** Let \(P_0\) be the observed first prompt size and \(d\) the mean increase between the seven measured prompt sizes. For prompts at steps \(0\) through \(20\), estimate \(\sum_{k=0}^{20}(P_0+kd)=21P_0+210d\). The generated evidence includes the measured \(P_0\), \(d\) and resulting projection. This is a **linear extrapolation of prompt sizes**, not a claim that a 20-step run was observed. An explicit memory budget, retrieval for durable facts and periodic compaction would flatten the context-growth curve.

---

## Lab 2.4 — Decompose a workshop goal properly

**Goal:** Organize a practical 90-minute internal workshop on debugging a fictional GraphQL integration. The scenario does not describe a real employer, event, customer or deployment.

### 1. Initial plan and colleague-test sharpening

| Vague task | Actionable rewritten task | Colleague test |
| --- | --- | --- |
| Understand the workshop | Ask the fictional requester for target participants, learning objectives, headcount, format, and budget; record those in one-page scope notes | Another person knows what to ask and what document to produce |
| Find a date | Collect attendees' available dates and room/online-room constraints; propose two 90-minute slots with timezones and a deadline for selection | Clear inputs, candidate count and output |
| Prepare content | Draft a 90-minute agenda: 10-minute introduction, 20-minute example, 35-minute guided debugging, 15-minute debrief and 10-minute Q&A | Exact time budget and output are checkable |
| Prepare materials | Make a synthetic GraphQL project with three failing test cases, setup instructions, a solution key and a dry-run checklist | Clear concrete deliverables and safety boundary |
| Run and improve | Conduct a dry run with one reviewer, log at least three findings, revise setup/agenda, then gather a three-question participant survey | Measurable completion and feedback artifacts |

### 2. Dependencies and genuine parallelism

1. **Scope** has no upstream dependency and must be established first.
2. **Scheduling** depends on scope (audience, duration, format); it does **not** depend on content or lab materials, so scheduling can run in parallel with steps 3 and 4 once scope is settled.
3. **Agenda** depends on scope and learning objectives; it can start in parallel with lab preparation.
4. **Lab materials** depend on scope and the chosen technical level; they can be built in parallel with scheduling and the first agenda draft.
5. **Dry run and survey** depend on both agenda and materials, and the final workshop also needs a confirmed slot.

**Why not split into five agents?** Only scheduling and content preparation have enough independent work to benefit from parallel execution, and a small workshop may not justify coordination overhead. Two fixed workflow branches would probably suffice.

### 3. Forced replanning

**New finding during scope:** Only 30 minutes are available, rather than the expected 90. This invalidates the 35-minute hands-on component and the long Q&A.

**Revised plan:** Preserve objectives, audience and access constraints. Propose two 30-minute slots instead; rewrite the agenda as 5-minute framing, 10-minute live walkthrough, 10-minute one-bug exercise, 5-minute close. Reduce the sample project to one failure case with a ready-to-run test script. Dry-run it and retain the same three-question survey.

**What survived?** All **five high-level workstreams** survived, but the concrete agendas, scheduling durations and exercise scope changed. I would plan outcomes and dependencies up front, then leave detailed delivery content flexible until the first constraints are confirmed.

### 4. Mid-run progress tracker

```text
[done]    Confirm audience, goal, scope and 30-minute cap
[done]    Propose two feasible 30-minute slots
[current] Rewrite agenda and mini-exercise for the shorter duration
[todo]    Validate sample repository instructions with a reviewer
[todo]    Dry-run, fix problems, and distribute feedback survey
```

If the process crashed, the checklist would immediately show the committed new constraint, completed decisions and the exact next action. A long transcript might contain those facts, but they would be scattered among outdated plans, making accidental resumption from the abandoned 90-minute agenda more likely.

---

## Lab 2.5 — One agent or several?

**Task:** Write a short, sourced market overview of three *hypothetical* competing developer-tool products. No competitive intelligence or pricing claims about real companies are made in this exercise.

### 1. Single-agent design

A single agent would identify three products, search their official product/pricing documentation, record dated evidence, compare features and price bases, mark missing claims, draft the overview and check that citations support each statement. Its tools would be `search_public_docs(query)`, `open_public_url(url)`, `extract_pricing(page_url)`, and `save_evidence_record(record)`; all tools would be scoped to public research, not private systems. In its fullest context, the agent would hold the assignment and evaluation criteria, three products' pages and citations, extracted feature matrices, caveats, and a draft. If each product requires several verbose pages, this context becomes large; evidence records and retrieval are better than dumping every page into the prompt.

### 2. Multi-agent alternative and exact handoffs

**Agent A — Researcher:** Uses `search_public_docs`, `open_public_url` and `save_evidence_record`. It extracts source facts into an array of the following records:

```json
{
  "product_id": "fictional-alpha",
  "claim": "Has a documented self-hosted deployment option",
  "source_url": "https://example.org/illustrative-only",
  "source_checked_on": "2026-11-04",
  "confidence": "medium",
  "source_type": "vendor_documentation",
  "limitations": ["Coverage may differ by plan"]
}
```

The URL is an **illustrative placeholder**, not a retrieved citation.

**Agent B — Analyst:** Receives the **complete JSON evidence list** plus explicit `{comparison_dimensions: ["features", "deployment", "pricing_basis"], required_products: 3}`. It checks that each cell is supported, produces a table with evidence-record IDs, and marks unavailable data as `unknown`. Tools: `lookup_evidence(id)` and `validate_schema(json)`.

**Agent C — Editor/Verifier:** Receives `{matrix: ..., evidence_ids: [...], unresolved_claims: [...]}` plus the original brief. It checks each written claim against a source record, then returns a short overview with citations and caveats. Tools: `lookup_evidence(id)` and `verify_citation(record_id)`.

**Handoff A → B:** Typed JSON list preserving claim, date, URL, reliability and limitation fields. **Handoff B → C:** Structured matrix, original evidence IDs and unresolved questions. None of these agents should pass an unsupported claim as a fact; the next agent can dereference IDs to recover omitted context.

### 3. Lossy handoff

Suppose Agent A reads a vendor's caveat that an advertised feature applies only to a costly enterprise plan. If A passes only `"has_feature": true` to B, that caveat is lost. B could write an incorrectly general claim, and C could repeat it. To prevent this, handoffs must preserve `plan_scope`, `limitations` and `source_id`, allowing later agents to inspect the original qualification.

### 4. Honest tradeoff and decision

The multi-agent system can improve quality **if** independent sourcing, specialized validation, parallel competitor research or strong context isolation are genuinely needed. It also adds model calls and a new failure point at every handoff. For a short comparison of only three products, I would **build one agent with structured evidence and a separate deterministic citation check**. The work is small, the tools are shared, and the coordination cost would likely outweigh specialization or parallelism benefits. I would split it only after evaluation demonstrated a specific quality or scale problem; multiple agents are not automatically more autonomous or reliable.

---

## Lab 2.6 — Producer–critic pair

The real two-role system is in [`producer_critic.py`](producer_critic.py), with implementation in [`src/building_blocks/critic.py`](src/building_blocks/critic.py). It begins with the same **fictional eight-person team** brief each time and uses two independent model contexts: one for drafting and one for critiquing against five explicit criteria. Each run has a hard revision ceiling. The tool records the original draft, every critic verdict and revision, word counts, total model calls and the provider's input/output token counters.

It repeats the baseline three times to observe nondeterminism; tests a vague one-line rubric; tests **self-review three times**, reporting pass/rejection rates alongside the three independent reviews; and permits six revisions in one bounded stress run. The script does not equate a critic's PASS with truth: its claims and word count still need separate checks. If the ceiling is exhausted, the final draft is flagged for human review instead of silently marked accepted.

---

## Measured results and model-behavior evidence

<!-- MEASURED_START -->
> No model-backed experiments have been run in this copy yet. Run `python run_experiments.py` with Ollama or Anthropic, then `python finalize_submission.py`. The automated GitHub workflow can do this and commit the real observations once the repository exists.
<!-- MEASURED_END -->

## Submission checklist

- [x] Lab 2.1 — two verb-led, model-oriented tool definitions, schemas, boundaries, exact errors, blast radius and refused action.
- [x] Lab 2.2 — bounded synthetic tool agent and five isolated breaking scenarios.
- [x] Lab 2.3 — full-history input-token counters, compaction variants, pinned goal, and 20-step projection method.
- [x] Lab 2.4 — vague and sharpened subtasks, dependencies, replan and mid-run tracker.
- [x] Lab 2.5 — explicit single/multi-agent options, typed handoffs, loss analysis and decision.
- [x] Lab 2.6 — independently contextualized producer/critic pair, bounded revisions and comparison scenarios.
- [ ] Actual provider-backed behavior and measured token counts (filled by the experiment workflow, not guessed).
- [ ] Final manual review of model output against source fixtures, including timezone limitations.
