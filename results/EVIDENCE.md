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


