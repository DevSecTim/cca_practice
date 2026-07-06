"""
Day 11 — Scenario 6: Structured data extraction deep dive

Covers study plan points 1, 2, and 3 (Domain 4, Task Statement 4.4):
  1. A validation-retry loop: extract, validate, and on failure feed the errors
     back to the model so it can self-correct.
  2. The distinction between errors retry CAN fix (format/structural) and
     errors retry CANNOT fix (information absent from the source document).
  3. Self-correction schema fields (line_items_total / stated_total /
     conflict_detected) that let validation catch semantic errors tool_use
     alone cannot — tool_use guarantees valid JSON, not a correct total.
"""

import json
import re

import anthropic

client = anthropic.Anthropic()

# ---------------------------------------------------------
# POINT 3 — extraction schema with self-correction fields added
# ---------------------------------------------------------
extraction_tool = {
    "name": "extract_invoice",
    "description": "Extract data from any invoice document.",
    "input_schema": {
        "type": "object",
        "properties": {
            "vendor_name": {"type": "string"},
            "total_amount": {"type": "number"},
            "currency": {"type": "string", "enum": ["USD", "EUR", "GBP", "INR", "other"]},
            "due_date": {
                "type": ["string", "null"],
                "description": "ISO 8601 format YYYY-MM-DD, or null if not stated in the document.",
            },
            "line_items_total": {
                "type": "number",
                "description": "Sum of all line item amounts on the invoice.",
            },
            "stated_total": {
                "type": "number",
                "description": "Total as explicitly stated in the document.",
            },
            "conflict_detected": {
                "type": "boolean",
                "description": "True if line_items_total != stated_total.",
            },
        },
        "required": [
            "vendor_name",
            "total_amount",
            "currency",
            "line_items_total",
            "stated_total",
            "conflict_detected",
        ],
    },
}

tool_choice = {"type": "tool", "name": "extract_invoice"}

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def get_tool_result(response):
    for block in response.content:
        if block.type == "tool_use":
            return block.input
    raise RuntimeError("Forced tool_choice did not produce a tool_use block")


def validate(result, require_due_date=False):
    """Semantic validation tool_use cannot do on its own. Returns a list of
    error strings, or an empty list if the extraction is acceptable."""
    errors = []

    due_date = result.get("due_date")
    if due_date is not None and not DATE_RE.match(due_date):
        errors.append(f"due_date '{due_date}' is not in YYYY-MM-DD format")
    if require_due_date and due_date is None:
        errors.append("due_date is required but missing")

    line_items_total = result.get("line_items_total")
    stated_total = result.get("stated_total")
    conflict_detected = result.get("conflict_detected")
    actual_conflict = line_items_total != stated_total
    if conflict_detected != actual_conflict:
        errors.append(
            f"conflict_detected={conflict_detected} but "
            f"line_items_total={line_items_total} vs stated_total={stated_total} "
            f"implies conflict_detected should be {actual_conflict}"
        )

    return errors


# ---------------------------------------------------------
# POINT 1 — validation-retry loop
# ---------------------------------------------------------
def extract_with_retry(document, max_retries=2, require_due_date=False):
    messages = [{"role": "user", "content": f"Extract from:\n{document}"}]

    for attempt in range(max_retries + 1):
        response = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=1024,
            tools=[extraction_tool],
            tool_choice=tool_choice,
            messages=messages,
        )
        result = get_tool_result(response)
        errors = validate(result, require_due_date=require_due_date)

        print(f"  attempt {attempt}: {json.dumps(result)}")
        if errors:
            print(f"    errors: {errors}")

        if not errors:
            return result, attempt

        tool_use_id = next(b.id for b in response.content if b.type == "tool_use")
        messages.append({"role": "assistant", "content": response.content})
        messages.append(
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_use_id,
                        "content": (
                            f"Extraction failed. Errors: {errors}\n"
                            f"Original doc: {document}\n"
                            f"Failed result: {json.dumps(result)}\n"
                            "Please correct and try again."
                        ),
                    }
                ],
            }
        )

    return None, max_retries


if __name__ == "__main__":
    # POINT 2a — RETRY WORKS: the due date is present but in the wrong format.
    # The model has the information; it just needs to reformat it.
    print("=== Case 1: fixable format error (retry should converge) ===")
    doc_bad_format = (
        "Invoice from TechCorp, INV-001. Line items: $300 + $200 = $500. "
        "Total due: $500 USD. Payment due 31-03-2024."
    )
    result, attempt = extract_with_retry(doc_bad_format)
    if result:
        print(f"Converged on attempt {attempt}: {json.dumps(result, indent=2)}\n")
    else:
        print("Did not converge within max_retries.\n")

    # POINT 2b — RETRY DOES NOT WORK: the due date is genuinely absent from the
    # source. No amount of retrying makes the model invent a correct date, so a
    # validator that wrongly *requires* due_date will exhaust every retry.
    print("=== Case 2: information absent from source (retry cannot fix this) ===")
    doc_no_due_date = (
        "Invoice from TechCorp, INV-002. Line items: $300 + $200 = $500. Total due: $500 USD."
    )
    result, attempt = extract_with_retry(doc_no_due_date, require_due_date=True)
    if result:
        print(f"Converged on attempt {attempt}: {json.dumps(result, indent=2)}")
    else:
        print(
            f"Exhausted all {attempt + 1} attempts without converging.\n"
            "Lesson: due_date is absent from the document, not malformed — "
            "retrying wastes API calls and never succeeds. The fix is to accept "
            "a null due_date, not to keep asking the model to retry."
        )
