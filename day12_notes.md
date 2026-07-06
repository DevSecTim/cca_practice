# Day 12 — Domain 5: Context management and error propagation

Notes on the *why* behind `day12.py`, for review before the exam.

## 1. Case facts pattern ([day12.py:24-45](day12.py#L24-L45))

Summarization is lossy compression applied to language — it has no concept of
"this value must survive exactly." It optimizes for gist, not fidelity. So the
fix isn't "summarize more carefully," it's **structural exclusion**: `case_facts`
never enters `summarize_conversation()`'s input at all. Only free-form
conversation turns get compressed; the facts block is reconstructed verbatim
on every turn.

Rule of thumb: if a value would be a bug to get subtly wrong (an ID, an
amount, a date, an explicit customer commitment), it doesn't go through a
summarization step, full stop — not even once.

## 2. Lost-in-the-middle ([day12.py:47-61](day12.py#L47-L61))

Models attend more reliably to the start and end of long inputs than the
middle. The demo in `day12.py` (a fact buried in ~60 filler sentences) did
**not** reproduce a failure — `claude-haiku-4-5` retrieved it correctly either
way. That's not evidence the effect doesn't exist; it just means the test
wasn't adversarial enough (short context, low decoy density). The real
failure mode shows up at much larger scale: tens of thousands of tokens,
several similar-looking decoy values competing for attention.

Design for this defensively, the same way you force `tool_choice` instead of
trusting `auto` most of the time works: put critical facts and key summaries
at the **start** of aggregated context, use explicit section headers, and put
supporting detail after — regardless of whether a given test happens to catch
the model failing.

## 3. Structured error propagation ([day12.py:76-96](day12.py#L76-L96))

```
BAD:  {"status": "search unavailable"}
GOOD: {"error": true, "failure_type": "timeout", "attempted_query": "...",
       "partial_results": [...], "alternatives": [...], "is_retryable": true}
```

This is the same underlying problem as case facts and lost-in-the-middle:
**what survives into the next context window.** With the BAD response, the
richer failure state (what was attempted, whether retry would help, partial
progress) is thrown away *before* it ever reaches the coordinator's context.
No amount of clever handling downstream can recover detail that was already
discarded at the source.

## 4. Escalation triggers ([day12.py:99-152](day12.py#L99-L152))

Domain 5.2 rules, encoded directly in the system prompt:

- **ALWAYS** escalate: explicit human request.
- **ESCALATE**: policy is silent/ambiguous on the specific request, or no
  progress after investigating.
- **NEVER** escalate based on: sentiment, self-reported confidence, or
  complexity alone.

The exam tests this by pairing cases that decouple sentiment from complexity
— confirmed live against the API:

| | Simple / policy-covered | Policy gap |
|---|---|---|
| **Calm** | resolve | escalate |
| **Angry** | resolve (frustration ≠ reason to escalate) | escalate (anger doesn't block a legitimate escalation either) |

If a system wired escalation to sentiment, it would get the angry+simple
quadrant wrong (escalating something it should resolve) or risk missing the
calm+policy-gap quadrant (failing to escalate a genuinely hard case because
the customer "seemed fine").

**Ambiguous customer match** ([day12.py:143-152](day12.py#L143-L152)): when
multiple records match, ask for another identifier — never guess with a
heuristic (most recent order, first alphabetically). A wrong guess here
corrupts every "fact" loaded afterward, since it's now the wrong customer's
context entirely — tying back to point 1: garbage case facts are worse than
no case facts, because nothing downstream flags them as wrong.

## The one-line summary

Every point in Day 12 is a variant of the same question: **what information
survives into the next context window, and who — or what mechanism —
decides that?** Summarization decides it for conversation history. Attention
position decides it within a single long input. A subagent's return value
decides it for a coordinator. A system prompt's stated criteria decides it
for escalation.
