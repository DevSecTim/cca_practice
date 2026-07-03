"""
Day 9 — Scenario 3: Multi-agent research system deep dive

Covers study plan points 2, 3, and 4:
  2. Coordinator prompt that assigns distinct subtopics to subagents in PARALLEL
  3. Structured subagent output schema (subtopic / findings / source_url / publication_date)
  4. Error propagation — a subagent that fails returns structured context, not a bare status string
"""

import concurrent.futures
import random

import anthropic

client = anthropic.Anthropic()

# ---------------------------------------------------------
# POINT 3 — Structured output tool every subagent is forced to call
# ---------------------------------------------------------
research_tool = {
    "name": "report_findings",
    "description": "Report structured research findings for one subtopic.",
    "input_schema": {
        "type": "object",
        "properties": {
            "subtopic": {"type": "string"},
            "findings": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "claim": {"type": "string"},
                        "source_url": {"type": "string"},
                        "publication_date": {"type": "string"},
                        "evidence_excerpt": {"type": "string"},
                    },
                    "required": ["claim", "source_url", "publication_date"],
                },
            },
        },
        "required": ["subtopic", "findings"],
    },
}


def run_search_subagent(subtopic, task, simulate_timeout=False):
    """A research subagent. Forced to return structured findings via tool_choice.

    POINT 4 — If the subagent fails (here simulated with simulate_timeout), it
    returns a structured error object instead of a bare status string, so the
    coordinator can decide whether to retry, proceed with partial results, or
    flag a coverage gap.
    """
    if simulate_timeout:
        return {
            "error": True,
            "failure_type": "timeout",
            "attempted_query": task,
            "partial_results": [],
            "alternatives": ["retry with a narrower query", "use a document analysis agent instead"],
            "is_retryable": True,
        }

    response = client.messages.create(
        model="claude-haiku-4-5",
        system=(
            f"You are a research subagent covering the subtopic '{subtopic}'. "
            "Use the report_findings tool. Every claim needs a source_url and "
            "publication_date — if you cannot find a real one, say so in the excerpt "
            "rather than inventing one."
        ),
        max_tokens=1024,
        tools=[research_tool],
        tool_choice={"type": "tool", "name": "report_findings"},
        messages=[{"role": "user", "content": task}],
    )

    for block in response.content:
        if block.type == "tool_use":
            return block.input

    # Defensive fallback — forced tool_choice should always produce a tool_use block
    return {
        "error": True,
        "failure_type": "no_tool_use",
        "attempted_query": task,
        "partial_results": [],
        "alternatives": ["retry"],
        "is_retryable": True,
    }


# ---------------------------------------------------------
# POINT 2 — Coordinator decomposes the topic itself and delegates in PARALLEL
#
# The exam concept: spawning multiple Task/delegate tool calls in a SINGLE
# coordinator response runs subagents in parallel. Separate turns = sequential.
# So the coordinator here is a real model call — the decomposition into
# subtopics is the model's decision, not a hardcoded Python list.
# ---------------------------------------------------------
delegate_tool = {
    "name": "delegate_research",
    "description": "Delegate one subtopic of the research to a search subagent.",
    "input_schema": {
        "type": "object",
        "properties": {
            "subtopic": {"type": "string", "description": "Short name for the subtopic, e.g. 'Music'."},
            "task": {"type": "string", "description": "Detailed research instructions for this subagent."},
        },
        "required": ["subtopic", "task"],
    },
}


def run_coordinator(research_topic):
    print(f"Coordinator: decomposing '{research_topic}' into parallel subtopics...\n")

    response = client.messages.create(
        model="claude-sonnet-4-5",
        system=(
            "You are a research coordinator. Decompose the user's topic into 3 distinct, "
            "non-overlapping subtopics. Delegate ALL of them by calling the delegate_research "
            "tool once per subtopic — make every call in this SAME response so the subagents "
            "run in parallel, not one subtopic per turn."
        ),
        max_tokens=1024,
        tools=[delegate_tool],
        tool_choice={"type": "any"},
        messages=[{"role": "user", "content": f"Research topic: {research_topic}"}],
    )

    assignments = [block.input for block in response.content if block.type == "tool_use"]
    print(f"Coordinator emitted {len(assignments)} delegate_research call(s) in a single turn "
          "-> these run in parallel.\n")

    # Simulate one subagent timing out, to exercise the error-propagation path
    timeout_index = random.Random(0).randrange(len(assignments))

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(assignments)) as pool:
        futures = {
            pool.submit(
                run_search_subagent,
                assignment["subtopic"],
                assignment["task"],
                simulate_timeout=(i == timeout_index),
            ): assignment["subtopic"]
            for i, assignment in enumerate(assignments)
        }
        for future in concurrent.futures.as_completed(futures):
            subtopic = futures[future]
            result = future.result()
            result.setdefault("subtopic", subtopic)
            results.append(result)

    # Coordinator inspects each result and decides how to handle errors
    successful, failed = [], []
    for result in results:
        if result.get("error"):
            failed.append(result)
        else:
            successful.append(result)

    print("=== Successful subagent results ===")
    for result in successful:
        print(f"- {result['subtopic']}: {len(result.get('findings', []))} finding(s)")

    print("\n=== Failed subagents (structured error context) ===")
    for result in failed:
        print(f"- {result['subtopic']}: failure_type={result['failure_type']}, "
              f"is_retryable={result.get('is_retryable')}, "
              f"alternatives={result.get('alternatives')}")

    if failed:
        print("\nCoordinator decision: proceed with partial results and annotate the "
              "final report with a coverage gap for the failed subtopic(s).")

    synthesis = run_synthesis_subagent(research_topic, successful, failed)
    print("\n=== Synthesis ===")
    print(synthesis)

    return successful, failed, synthesis


# ---------------------------------------------------------
# Synthesis subagent — explicit context passing over the FULLY COLLECTED
# (post-barrier) results, never a live/streamed order.
#
# Concurrency was already resolved before this function runs: the
# ThreadPoolExecutor `with` block above only exits once every subagent has
# completed, so `successful`/`failed` are plain, order-irrelevant lists by
# the time they get here. Each entry is still labeled by subtopic (not by
# position), so the synthesis prompt can name each subtopic explicitly
# instead of relying on "the first result" / "the earlier research".
# ---------------------------------------------------------
def run_synthesis_subagent(research_topic, successful, failed):
    # Sort by subtopic for a stable, readable prompt — purely cosmetic, since
    # correctness already comes from explicit labeling, not from this order.
    successful_sorted = sorted(successful, key=lambda r: r["subtopic"])
    failed_sorted = sorted(failed, key=lambda r: r["subtopic"])

    findings_block = "\n\n".join(
        f"SUBTOPIC: {result['subtopic']}\n"
        + "\n".join(
            f"- {finding['claim']} (source: {finding.get('source_url', 'n/a')}, "
            f"date: {finding.get('publication_date', 'n/a')})"
            for finding in result.get("findings", [])
        )
        for result in successful_sorted
    ) or "None."

    coverage_gaps_block = "\n".join(
        f"- {result['subtopic']}: {result['failure_type']} "
        f"(retryable={result.get('is_retryable')})"
        for result in failed_sorted
    ) or "None."

    context = (
        f"FINDINGS BY SUBTOPIC:\n{findings_block}\n\n"
        f"COVERAGE GAPS (subtopics that failed and are NOT reflected above):\n{coverage_gaps_block}"
    )

    response = client.messages.create(
        model="claude-sonnet-4-5",
        system=(
            "You are a synthesis agent. Combine the findings below into a short report on "
            f"'{research_topic}'. Preserve source URLs and dates. Explicitly call out any "
            "coverage gaps instead of silently ignoring the missing subtopics. Do not assume "
            "any subtopic beyond what is listed."
        ),
        max_tokens=1024,
        messages=[{"role": "user", "content": context}],
    )

    return "".join(block.text for block in response.content if block.type == "text")


if __name__ == "__main__":
    run_coordinator("AI's impact on creative industries")
