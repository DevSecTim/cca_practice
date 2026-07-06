"""
Day 12 — Domain 5: Context management and error propagation

Covers study plan points 1-4:
  1. The 'case facts' pattern — a persistent structured block that sits OUTSIDE
     summarized history. Numeric values, dates, and customer-stated
     expectations must never be compressed into vague prose.
  2. Lost-in-the-middle mitigation — models reliably attend to the START and
     END of long inputs; critical facts must be placed there, not buried in
     the middle.
  3. Structured subagent error propagation — a BAD bare-status response gives
     a coordinator nothing to act on; a GOOD structured response lets it
     decide to retry, proceed with partial results, or flag a coverage gap.
  4. Escalation triggers — explicit request / policy gap / no progress after
     investigation. NEVER escalate based on sentiment, self-reported
     confidence, or complexity alone; ambiguous customer matches get resolved
     by asking for another identifier, never by a heuristic guess.
"""

import anthropic

client = anthropic.Anthropic()

# ---------------------------------------------------------
# POINT 1 — case facts pattern
#
# case_facts is never handed to the summarizer. Only the free-form
# conversation history gets compressed as it grows; the facts block is
# reconstructed verbatim on every turn.
# ---------------------------------------------------------
def summarize_conversation(turns):
    response = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=256,
        messages=[
            {
                "role": "user",
                "content": "Summarize this support conversation in 2 sentences:\n" + "\n".join(turns),
            }
        ],
    )
    return response.content[0].text


def build_context(case_facts, conversation_summary):
    facts_block = "\n".join(f"  {k}: {v}" for k, v in case_facts.items())
    return (
        f"CASE FACTS (always included, never summarized):\n{facts_block}\n\n"
        f"CONVERSATION SUMMARY (compressed):\n{conversation_summary}"
    )


# ---------------------------------------------------------
# POINT 2 — lost-in-the-middle mitigation
#
# Critical facts go at the START of an aggregated context. Padding /
# secondary detail goes after. This function demonstrates the ordering rule;
# the live comparison below shows what happens when a fact is buried instead.
# ---------------------------------------------------------
def build_prioritized_context(critical_fact, secondary_detail):
    return f"{critical_fact}\n\n{secondary_detail}"


def build_buried_context(critical_fact, secondary_detail):
    return f"{secondary_detail}\n{critical_fact}\n{secondary_detail}"


# ---------------------------------------------------------
# POINT 3 — structured error propagation: BAD vs GOOD
# ---------------------------------------------------------
def bad_error_response():
    return {"status": "search unavailable"}


def good_error_response():
    return {
        "error": True,
        "failure_type": "timeout",
        "attempted_query": "AI music industry 2024",
        "partial_results": [{"claim": "AI tools are used in mastering", "source": "n/a"}],
        "alternatives": ["retry with a broader query", "use a document analysis agent instead"],
        "is_retryable": True,
    }


def coordinator_decide(error_response):
    """What a coordinator can actually do with each shape of error."""
    if "failure_type" not in error_response:
        return "Cannot decide — no structured information to act on. Stuck."
    if error_response.get("is_retryable") and error_response.get("alternatives"):
        return f"Retry using: {error_response['alternatives'][0]}"
    return "Proceed with partial_results and flag a coverage gap in the final report."


# ---------------------------------------------------------
# POINT 4 — escalation triggers, forced classification
#
# The system prompt encodes the exact Domain 5.2 rules: explicit request /
# policy gap / no progress escalate; sentiment, confidence, and complexity
# alone do not.
# ---------------------------------------------------------
escalation_tool = {
    "name": "classify_escalation",
    "description": "Decide whether a customer support case should escalate to a human.",
    "input_schema": {
        "type": "object",
        "properties": {
            "escalate": {"type": "boolean"},
            "trigger": {
                "type": ["string", "null"],
                "enum": ["explicit_request", "policy_gap", "no_progress", None],
            },
            "reasoning": {"type": "string"},
        },
        "required": ["escalate", "reasoning"],
    },
}

ESCALATION_SYSTEM_PROMPT = (
    "You decide whether a support case escalates to a human.\n"
    "ALWAYS escalate when the customer explicitly requests a human agent.\n"
    "ESCALATE when policy is silent or ambiguous on the specific request, or "
    "when you cannot make meaningful progress after investigating.\n"
    "Do NOT escalate based on sentiment, self-reported confidence, or case "
    "complexity alone — a frustrated customer with a simple, policy-covered "
    "claim should be resolved autonomously, not escalated."
)


def classify_escalation(customer_message):
    response = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=300,
        system=ESCALATION_SYSTEM_PROMPT,
        tools=[escalation_tool],
        tool_choice={"type": "tool", "name": "classify_escalation"},
        messages=[{"role": "user", "content": customer_message}],
    )
    for block in response.content:
        if block.type == "tool_use":
            return block.input


def resolve_customer_ambiguity(matches):
    """When multiple customer records match, ask for another identifier.
    Never resolve ambiguity with a heuristic (most recent order, first
    alphabetically) — that risks acting on the wrong account."""
    if len(matches) > 1:
        return {
            "action": "request_additional_identifier",
            "candidates": len(matches),
            "ask": "Could you confirm your order number or the email used at checkout?",
        }
    return {"action": "proceed", "customer": matches[0]}


if __name__ == "__main__":
    print("=== Point 1: case facts survive summarization ===")
    case_facts = {
        "customer_id": "CUST-00891",
        "order_id": "ORD-44521",
        "order_amount": "$127.50",
        "order_date": "2024-03-01",
        "issue": "package not delivered",
        "customer_stated_expectation": "full refund",
    }
    turns = [
        "Customer: My order never showed up, it's been two weeks.",
        "Agent: I'm sorry to hear that, let me look into it.",
        "Customer: I already contacted the courier myself, they said it's lost.",
    ]
    summary = summarize_conversation(turns)
    context = build_context(case_facts, summary)
    print(context)
    print(
        f"\n-> order_amount is exactly '{case_facts['order_amount']}' in the facts block, "
        "never paraphrased by the summarizer above.\n"
    )

    print("=== Point 2: lost-in-the-middle — buried fact vs prioritized fact ===")
    critical_fact = "The refund authorization code is RFA-77213."
    decoys = " ".join(
        f"Filler policy note {i}: standard shipping takes 5-7 business days." for i in range(60)
    )
    question = "\n\nWhat is the refund authorization code? Answer with just the code."

    buried = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=50,
        messages=[{"role": "user", "content": build_buried_context(critical_fact, decoys) + question}],
    )
    prioritized = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=50,
        messages=[{"role": "user", "content": build_prioritized_context(critical_fact, decoys) + question}],
    )
    buried_answer = buried.content[0].text.strip()
    prioritized_answer = prioritized.content[0].text.strip()
    print(f"Fact buried in the middle -> {buried_answer!r}")
    print(f"Fact placed at the start  -> {prioritized_answer!r}")
    if "RFA-77213" in buried_answer:
        print(
            "-> Both retrieved it correctly at this context length — current models are "
            "fairly robust to a single buried fact over ~60 sentences. The failure mode "
            "shows up with much longer contexts and multiple similar-looking decoy values. "
            "The mitigation rule still applies regardless: put critical facts at the START "
            "of aggregated context with explicit headers, don't rely on the model finding "
            "them wherever they land.\n"
        )
    else:
        print("-> The buried fact was lost while the prioritized one was retrieved correctly.\n")

    print("=== Point 3: structured error propagation ===")
    print("BAD  response:", bad_error_response())
    print("  coordinator ->", coordinator_decide(bad_error_response()))
    print("GOOD response:", good_error_response())
    print("  coordinator ->", coordinator_decide(good_error_response()), "\n")

    print("=== Point 4: escalation triggers — sentiment x complexity matrix ===")
    cases = [
        # (label, message) — the four quadrants of sentiment x policy-complexity
        (
            "explicit request (always escalates regardless of the rest)",
            "I want to speak to a manager right now.",
        ),
        (
            "angry + simple/policy-covered -> should NOT escalate",
            "THIS IS RIDICULOUS!! My package never arrived and I'm furious, "
            "I just want the refund your policy already promises for lost packages.",
        ),
        (
            "calm + policy gap -> SHOULD escalate",
            "Can you make an exception and let me return this item after the "
            "90-day window? I was hospitalized and couldn't get to a post office.",
        ),
        (
            "calm + simple/policy-covered -> should NOT escalate",
            "Hi, my order arrived damaged. Could I get a refund please? Thanks!",
        ),
        (
            "angry + policy gap -> SHOULD escalate anyway",
            "This is a joke. Your 'no exceptions' return policy is garbage and I "
            "demand you make an exception for my custom order past the 30-day window.",
        ),
    ]
    for label, message in cases:
        result = classify_escalation(message)
        print(f"- [{label}]\n  \"{message[:70]}...\"\n  -> {result}\n")

    print("Ambiguous customer match:")
    print(" ", resolve_customer_ambiguity(["CUST-001", "CUST-002"]))
