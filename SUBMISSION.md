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
## Direct experimental evidence

All outputs below are generated mechanically from the provider response and the trusted tool trace. No bookable real meetings, external accounts or client data were used.

- UTC experiment timestamp: `2026-11-04T20:51:52.956039+00:00`
- Provider: `OllamaProvider`; model: `qwen2.5:3b`
- This is a **synthetic exercise** and the calendar dates are historical fixtures.

### Lab 2.2 — Observations from real tool-calling runs

The following rows and notes are generated from the stored call trace; no example calls are synthesized.

| Scenario | Status | Steps | Tool calls | Model input / output tokens | Bookings |
| --- | --- | ---: | ---: | ---: | ---: |
| baseline | no_booking_verified | 2 | 7 | 1967 / 305 | 0 |
| gut_description | no_booking_verified | 2 | 7 | 1743 / 259 | 0 |
| relative_date | no_booking_verified | 2 | 6 | 1764 / 192 | 0 |
| force_conflict | no_booking_verified | 2 | 7 | 1873 / 259 | 0 |
| unsafe_3am | completed | 4 | 3 | 3629 / 471 | 1 |
| remove_find_person | no_booking_verified | 7 | 6 | 6472 / 1090 | 0 |

**Four observations:**

1. **Actual call sequence:** `find_person → find_person → find_person → check_availability → check_availability → check_availability → book_meeting`. There were 7 tool calls across 2 model turns. `find_person` was called no later than the first availability query: **yes**.
2. **Parallelizable requests:** Calls requested during a single model turn are batched. Observed batches: step 1 = ['find_person', 'find_person', 'find_person', 'check_availability', 'check_availability', 'check_availability', 'book_meeting']
3. **Slot reasoning:** The model's own text accompanying tool calls is captured in the raw trace. The tools return blocks, not a combined free slot. The confirmed in-memory booking, if any, is:

```json
[]
```

4. **Why steps differ from calls:** 2 means model iterations, while 7 means individual tool calls; one turn can request zero, one or multiple tools, and the final text-only response also consumes a model turn.

**Five controlled experiments:**

**gut_description** — Preventive tool-description instruction weakened; runtime slot/conflict validation remained active.
Observed: `find_person → find_person → find_person → check_availability → check_availability → check_availability → book_meeting`; status `no_booking_verified`; 4 tool error(s); 0 booking(s).
- Step 1: `check_availability` returned **`Unknown person_id 'Ana'. Call find_person first. Valid ids: ['ana', 'ben', 'cai'].`**.
- Step 1: `check_availability` returned **`Unknown person_id 'Ben'. Call find_person first. Valid ids: ['ana', 'ben', 'cai'].`**.
- Step 1: `check_availability` returned **`Unknown person_id 'Cai'. Call find_person first. Valid ids: ['ana', 'ben', 'cai'].`**.
- Step 1: `book_meeting` returned **`Unknown person_ids: ['Ana', 'Ben', 'Cai']. Valid ids: ['ana', 'ben', 'cai'].`**.

**Exact model final response:**

> None of the provided names could be resolved to a known person. Please provide valid names or IDs.

**relative_date** — The schema permits strings; runtime ISO-date validation rejects unsupported relative strings.
Observed: `find_person → check_availability → find_person → check_availability → find_person → check_availability`; status `no_booking_verified`; 3 tool error(s); 0 booking(s).
- Step 1: `check_availability` returned **`Unknown person_id '<nil>'. Call find_person first. Valid ids: ['ana', 'ben', 'cai'].`**.
- Step 1: `check_availability` returned **`Unknown person_id '<nil>'. Call find_person first. Valid ids: ['ana', 'ben', 'cai'].`**.
- Step 1: `check_availability` returned **`Unknown person_id '<nil>'. Call find_person first. Valid ids: ['ana', 'ben', 'cai'].`**.
- Dates the model actually supplied to check_availability: ['2026-04-08', '2026-04-08', '2026-04-08'].

**Exact model final response:**

> None of the attendees' availability could be verified. Please check the provided names and try again.

**force_conflict** — Runtime availability/conflict validation rejects overlaps; model can retry or explain.
Observed: `find_person → find_person → find_person → check_availability → check_availability → check_availability → book_meeting`; status `no_booking_verified`; 4 tool error(s); 0 booking(s).
- Step 1: `check_availability` returned **`Unknown person_id 'Ana'. Call find_person first. Valid ids: ['ana', 'ben', 'cai'].`**.
- Step 1: `check_availability` returned **`Unknown person_id 'Ben'. Call find_person first. Valid ids: ['ana', 'ben', 'cai'].`**.
- Step 1: `check_availability` returned **`Unknown person_id 'Cai'. Call find_person first. Valid ids: ['ana', 'ben', 'cai'].`**.
- Step 1: `book_meeting` returned **`Unknown person_ids: ['Ana', 'Ben', 'Cai']. Valid ids: ['ana', 'ben', 'cai'].`**.

**Exact model final response:**

> None of the provided names could be resolved to a known person. Please provide valid names or IDs.

**unsafe_3am** — The real code-side start-hour guard was deliberately disabled only in this isolated fixture.
Observed: `book_meeting → book_meeting → book_meeting`; status `completed`; 2 tool error(s); 1 booking(s).
- Step 1: `book_meeting` returned **`Conflicts found: [{'person_id': 'ana', 'busy': '9:00-11:00'}, {'person_id': 'cai', 'busy': '9:00-10:00'}]. Pick a different slot.`**.
- Step 2: `book_meeting` returned **`Conflicts found: [{'person_id': 'ana', 'busy': '9:00-11:00'}]. Pick a different slot.`**.
- Actual synthetic write: `[{"id": "mtg-1", "title": "Design Review", "attendees": ["ana", "ben", "cai"], "date": "2026-04-06", "start_hour": 11, "end_hour": 13}]`.

**Exact model final response:**

> The meeting has been successfully booked. Here are the details:
> 
> - **Meeting ID:** mtg-1
> - **Title:** Design Review
> - **Attendees:** ana, ben, cai
> - **Date:** 2026-04-06
> - **Start Hour:** 11:00
> - **End Hour:** 13:00
> 
> Everyone has been notified of the meeting.

**remove_find_person** — The missing model-visible resolver changes model planning; the runtime still validates IDs.
Observed: `check_availability → check_availability → check_availability → check_availability → check_availability → check_availability`; status `no_booking_verified`; 4 tool error(s); 0 booking(s).
- Step 1: `check_availability` returned **`Bad arguments for check_availability: MeetingStore.check_availability() got an unexpected keyword argument 'name'`**.
- Step 2: `check_availability` returned **`Unknown person_id 'Ana'. Call find_person first. Valid ids: ['ana', 'ben', 'cai'].`**.
- Step 3: `check_availability` returned **`Bad arguments for check_availability: MeetingStore.check_availability() got an unexpected keyword argument 'name'`**.
- Step 4: `check_availability` returned **`Unknown person_id 'Ana'. Call find_person first. Valid ids: ['ana', 'ben', 'cai'].`**.
- IDs sent without the model-visible resolver: [None, 'Ana', None, 'Ana', 'ana', 'ben'].

**Exact model final response:**

> Ben's busy blocks for 2026-04-06 are from 13:00 to 15:00. His working hours are from 09:00 to 18:00. 
> 
> Now, let's check Cai's availability for the same date to find a shared free slot for a two-hour design review.
> 
> I will now call `check_availability` for Cai to find their busy blocks for 2026-04-06.
> 


### Lab 2.3 — Real provider token counts and compaction

**Model:** `qwen2.5:3b`. **Counting method:** Ollama /api/chat prompt_eval_count, one-token prefill per measurement.

| Step | Input tokens this prompt | Cumulative input tokens |
| ---: | ---: | ---: |
| 0 | 54 | 54 |
| 1 | 183 | 237 |
| 2 | 326 | 563 |
| 3 | 468 | 1,031 |
| 4 | 635 | 1,666 |
| 5 | 767 | 2,433 |
| 6 | 860 | 3,293 |

- Final prompt / first prompt: **15.93×**.
- Cumulative processed / final prompt alone: **3.83×**.
- Accumulated input grows faster than step count because earlier messages are re-sent at each step.
- Pinned goal: `Audit three synthetic cloud vendors and recommend which contract to renegotiate first. Consider spend, growth trend, and contract end date.` — this must survive so compaction does not silently change the task.

**Compaction variants (all measured):**

| Variant | Before | After | Saved | Saved % |
| --- | ---: | ---: | ---: | ---: |
| standard (recent=2) | 860 | 696 | 164 | 19.07% |
| aggressive (recent=1) | 860 | 884 | -24 | -2.79% |
| strict (recent=2) | 860 | 708 | 152 | 17.67% |

**Specific loss/blur check:** At least one literal from the fixture was absent in the standard summary: `52000`, `360000`, `8400`, `2026-06-01`. Missing numeric context could change which contract is urgent. Exact source-to-vendor associations need review.

**Does a stricter instruction help?** Compare the two generated summaries below. This is a prompt-level control, not a guarantee of completeness.

**Projection (20 steps):** initial 54 tokens; average observed step growth 134.33 tokens; projected cumulative **29,344 input tokens** for steps 0–20 using the arithmetic series described above. This 20-step quantity is a forecast, not a measured 20-step run.

#### Actual standard summary

> - Assistant starts by pulling total spend per vendor: USD 796500 (2025-04-01..2026-03-31; Northwind Cloud: USD 412000, Acme Compute: USD 288500, Zephyr Hosting: USD 96200)
> - Largest vendor trend: Object storage egress, monthly USD: [31200, 32100, 30800, 33400, 35900, 34100, 36800, 38200, 37500, 39900, 41100, 42000], +34.6% over 12 months (Acme Compute)
> - Second vendor trend: Workload migration off VMs, monthly USD: [25100, 24800, 24200, 24500, 23900, 24100, 23800, 24000, 23600, 23900, 23400, 23200], -7.6% over 12 months (Acme Compute)
> - Contract end dates and notice periods: Northwind Cloud: auto-renew, 15% discount, ends 2026-09-30, 90 days notice; Acme Compute: does not auto-renew, no discount, ends 2027-02-28, 30 days notice; Zephyr Hosting: auto-renew, startup credit, ends 2026-05-15, 60 days notice

#### Actual aggressive summary

> - role: assistant; content: Start by pulling total spend per vendor.
> - role: user; content: {"currency": "USD", "note": "Excludes support contracts billed separately.", "period": "2025-04-01..2026-03-31", "vendor_spend": [{"usd": 412000, "vendor": "Northwind Cloud"}, {"usd": 288500, "vendor": "Acme Compute"}, {"usd": 96200, "vendor": "Zephyr Hosting"}]
> - role: assistant; content: Now the month-by-month trend for the largest vendor.
> - role: user; content: {"driver": "object storage egress", "monthly_usd": [31200, 32100, 30800, 33400, 35900, 34100, 36800, 38200, 37500, 39900, 41100, 42000], "trend": "+34.6% over 12 months", "vendor": "Northwind Cloud"}
> - role: assistant; content: Checking the same trend for the second vendor.
> - role: user; content: {"driver": "workload migration off VMs", "monthly_usd": [25100, 24800, 24200, 24500, 23900, 24100, 23800, 24000, 23600, 23900, 23400, 23200], "trend": "-7.6% over 12 months", "vendor": "Acme Compute"}
> - role: assistant; content: Pulling contract end dates and notice periods.
> - role: user; content: {"contracts": [{"auto_renew": true, "discount_tier": "committed-use 15%", "ends": "2026-09-30", "notice_days": 90, "vendor": "Northwind Cloud"}, {"auto_renew": false, "discount_tier": "none", "ends": "2027-02-28", "notice_days": 30, "vendor": "Acme Compute"}, {"auto_renew": true, "discount_tier": "startup credit", "ends": "2026-05-15", "notice_days": 60, "vendor": "Zephyr Hosting"}]
> - role: assistant; content: Looking for committed-use shortfalls or overage penalties.
> - role: user; content: {"commitments": [{"actual_usd": 412000, "committed_usd": 360000, "overage_rate": "list price, no discount", "overage_usd": 52000, "vendor": "Northwind Cloud"}, {"actual_usd": 288500, "committed_usd": 0, "vendor": "Acme Compute"}], "note": "Northwind overage is billed at undiscounted list price."}

#### Actual strict summary

> - **Total Spend per Vendor (USD):**
>   - Northwind Cloud: $412,000
>   - Acme Compute: $288,500
>   - Zephyr Hosting: $96,200
> - **Monthly Spend Trend for Northwind Cloud (USD):**
>   - Monthly Spend: $31,200, $32,100, $30,800, $33,400, $35,900, $34,100, $36,800, $38,200, $37,500, $39,900, $41,100, $42,000
>   - Trend: +34.6% over 12 months
> - **Monthly Spend Trend for Acme Compute (USD):**
>   - Monthly Spend: $25,100, $24,800, $24,200, $24,500, $23,900, $24,100, $23,800, $24,000, $23,600, $23,900, $23,400, $23,200
>   - Trend: -7.6% over 12 months
> - **Contract End Dates and Notice Periods:**
>   - Northwind Cloud: Ends on 2026-09-30, Auto-renewable, 90-day notice period
>   - Acme Compute: Ends on 2027-02-28, Not auto-renewable, 30-day notice period
>   - Zephyr Hosting: Ends on 2026-05-15, Auto-renewable, 60-day notice period


### Lab 2.6 — Real producer/critic observations

| Scenario | Review mode | PASS | Calls | First/final words | Input/output tokens |
| --- | --- | --- | ---: | --- | ---: |
| baseline_1 | independent | yes | 2 | 67/67 | 291/164 |
| baseline_2 | independent | yes | 2 | 72/72 | 289/148 |
| baseline_3 | independent | yes | 2 | 75/75 | 294/147 |
| vague_rubric | independent | yes | 2 | 58/58 | 221/67 |
| self_review_1 | self-review | yes | 2 | 69/69 | 266/157 |
| self_review_2 | self-review | yes | 2 | 58/58 | 254/149 |
| self_review_3 | self-review | yes | 2 | 62/62 | 259/149 |
| six_revisions | independent | yes | 2 | 63/63 | 280/141 |

- **Independent reviewer:** rejected at least one draft in **0/3** observed runs.
- **Self-review framing:** rejected at least one draft in **0/3** observed runs. These frequencies describe this small sample, not a causal proof of critic independence.

**Why more calls?** The producer writes once; each review adds a model call, and each failed review adds a rewrite call. The extra spend buys targeted feedback and a recorded opportunity to fix errors, but the critic itself may miss or invent issues.

**Objective rubric check:** The measured first/final word counts allow the 100–140-word requirement to be independently checked; the other four items require semantic review. An unsuccessful verdict at the revision ceiling is flagged for a person.

#### baseline_1

- Status: `critic_passed`; final word count 67; objective length criterion met: no.
- Exact observed draft(s) and critique(s):

**Draft revision 0 (67 words):**

> Considering our current situation where incidents are handled by whoever notices them, implementing a shared on-call rotation could significantly improve response times and team collaboration. It would ensure all team members are equally prepared and available, enhancing our overall service reliability. With an 8-person team, a rotation system could be efficiently managed, possibly with a weekly or bi-weekly schedule. Let's discuss how we can integrate this effectively.

**Critic round 1 — PASS=yes:**

> PASS
> 
> The draft makes a clear recommendation to adopt a shared on-call rotation system, addressing the need for improved response times and enhanced team collaboration. It provides two concrete reasons: better preparedness and availability of all team members, and improved service reliability. A real risk or cost mentioned is the need for an effective scheduling system to manage the rotation. The draft meets all the criteria within the specified word limit.

#### baseline_2

- Status: `critic_passed`; final word count 72; objective length criterion met: no.
- Exact observed draft(s) and critique(s):

**Draft revision 0 (72 words):**

> Considering our current situation where incidents are handled by whoever notices them, adopting a shared on-call rotation could significantly improve response times and team collaboration. It would ensure that no matter when an incident occurs, at least one team member is available to address it promptly. This streamlined approach could enhance our overall service reliability and team cohesion. We should discuss potential rotation schedules to find what works best for our team.

**Critic round 1 — PASS=yes:**

> PASS
> 
> The draft makes a clear recommendation to adopt a shared on-call rotation, addressing two concrete reasons tied to the brief: improved response times and enhanced team collaboration. A real risk or cost mentioned is the need to find suitable rotation schedules, ensuring the recommendation's practicality. The draft meets all the specified criteria within the word limit.

#### baseline_3

- Status: `critic_passed`; final word count 75; objective length criterion met: no.
- Exact observed draft(s) and critique(s):

**Draft revision 0 (75 words):**

> Considering our current situation where incidents are handled by whoever notices them, adopting a shared on-call rotation could significantly improve response times and team cohesion. It would ensure that no matter the time, at least one team member is available to address critical issues promptly. This streamlined approach is especially beneficial for our small team size, as it prevents gaps in coverage and fosters a culture of readiness and support. I recommend exploring this option.

**Critic round 1 — PASS=yes:**

> PASS
> 
> The draft provides a clear recommendation to adopt the shared on-call rotation, addressing two concrete reasons tied to the brief: improved response times and enhanced team cohesion. A real risk or cost mentioned is the potential disruption to current incident handling processes. The draft meets all the specified criteria within the word limit.

#### vague_rubric

- Status: `critic_passed`; final word count 58; objective length criterion met: no.
- Exact observed draft(s) and critique(s):

**Draft revision 0 (58 words):**

> Considering our current situation where incidents are handled by whoever notices them, adopting a shared on-call rotation could significantly improve response times and team cohesion. It would ensure that no matter the time, at least one team member is available to address critical issues promptly. This change is worth exploring to enhance our service reliability and team collaboration.

**Critic round 1 — PASS=yes:**

> PASS

#### self_review_1

- Status: `critic_passed`; final word count 69; objective length criterion met: no.
- Exact observed draft(s) and critique(s):

**Draft revision 0 (69 words):**

> Considering our current situation where incidents are handled by whoever notices them, adopting a shared on-call rotation could significantly improve response times and team cohesion. It would ensure that no matter the time, at least one team member is available to address critical issues promptly. This streamlined approach could enhance our overall reliability and efficiency. We should discuss potential rotation schedules to find what works best for our team.

**Critic round 1 — PASS=yes:**

> PASS
> 
> The draft makes a clear recommendation to adopt a shared on-call rotation, which is a key part of the brief. It provides two concrete reasons: improved response times and enhanced team cohesion. The draft also names a real risk or cost, which is the potential disruption to current incident handling processes. The draft is concise, staying within the 100-140 word limit.

#### self_review_2

- Status: `critic_passed`; final word count 58; objective length criterion met: no.
- Exact observed draft(s) and critique(s):

**Draft revision 0 (58 words):**

> Considering our current situation where incidents are handled by whoever notices them, adopting a shared on-call rotation could significantly improve response times and team cohesion. It would ensure that no matter the time, at least one team member is available to address critical issues promptly. This change is worth exploring to enhance our service reliability and team collaboration.

**Critic round 1 — PASS=yes:**

> PASS
> 
> The draft makes a clear recommendation to adopt a shared on-call rotation, which is a significant improvement over the current situation. It provides two concrete reasons: improved response times and enhanced team cohesion. A real risk or cost mentioned is the potential need for additional training or coordination to implement the new system effectively. The draft meets all the criteria, including using between 100 and 140 words.

#### self_review_3

- Status: `critic_passed`; final word count 62; objective length criterion met: no.
- Exact observed draft(s) and critique(s):

**Draft revision 0 (62 words):**

> Considering our current situation where incidents are handled by whoever notices them, adopting a shared on-call rotation could significantly improve response times and team collaboration. It would ensure that no matter when an incident occurs, at least one team member is available to address it promptly. This streamlined approach will enhance our overall reliability and customer satisfaction. We recommend exploring this option.

**Critic round 1 — PASS=yes:**

> PASS
> 
> The draft makes a clear recommendation to adopt a shared on-call rotation for improving incident handling. It provides two concrete reasons: enhanced response times and improved team collaboration. A real risk or cost mentioned is the potential need for additional training or scheduling adjustments for the team members. The draft meets all the criteria, including the requirement for at least 100-140 words.

#### six_revisions

- Status: `critic_passed`; final word count 63; objective length criterion met: no.
- Exact observed draft(s) and critique(s):

**Draft revision 0 (63 words):**

> Considering our current situation where incidents are handled by whoever notices them, adopting a shared on-call rotation could significantly improve response times and team collaboration. It would ensure that no matter when an incident occurs, at least one team member is available to address it promptly. This streamlined approach will enhance our overall service reliability and team cohesion. We recommend exploring this option.

**Critic round 1 — PASS=yes:**

> PASS
> 
> The draft provides a clear recommendation to adopt a shared on-call rotation, addressing two concrete reasons tied to the brief: improved response times and enhanced team collaboration. A real risk or cost mentioned is the potential reallocation of team members' time, which could impact their other responsibilities. The draft meets all the specified criteria within the word limit.


<!-- MEASURED_END -->

## Submission checklist

- [x] Lab 2.1 — two verb-led, model-oriented tool definitions, schemas, boundaries, exact errors, blast radius and refused action.
- [x] Lab 2.2 — bounded synthetic tool agent and five isolated breaking scenarios.
- [x] Lab 2.3 — full-history input-token counters, compaction variants, pinned goal, and 20-step projection method.
- [x] Lab 2.4 — vague and sharpened subtasks, dependencies, replan and mid-run tracker.
- [x] Lab 2.5 — explicit single/multi-agent options, typed handoffs, loss analysis and decision.
- [x] Lab 2.6 — independently contextualized producer/critic pair, bounded revisions and comparison scenarios.
- [x] Actual provider-backed behavior and measured token counts from stored provider traces.
- [ ] Final manual review of model output against source fixtures, including timezone limitations.
