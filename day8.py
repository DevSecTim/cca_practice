import anthropic

client = anthropic.Anthropic()

# ---------------------------------------------------------
# Mock Tool Functions
# ---------------------------------------------------------
def process_refund(amount):
    print(f"[SYSTEM] -> Actually processing refund for ${amount}...")
    return f"Successfully processed refund for ${amount}"

def escalate_to_human(reason):
    print(f"[SYSTEM] -> Escalating to human manager! Reason: {reason}")
    return f"Escalated to human queue due to: {reason}"

# ---------------------------------------------------------
# PostToolUse Hook (Day 8 Scenario 1 Pattern)
# ---------------------------------------------------------
def post_tool_use_hook(tool_name, tool_input):
    """
    Programmatic enforcement hook: guarantees compliance by intercepting 
    the tool call BEFORE it executes and routing it elsewhere if needed.
    """
    if tool_name == "process_refund":
        amount = tool_input.get("amount", 0)
        if amount > 500:
            print(f"\n[HOOK INTERCEPT] Refund for ${amount} exceeds $500 limit. Blocking `process_refund`.")
            # We override the tool execution and call the escalation function instead
            return escalate_to_human(f"Amount ${amount} exceeds $500 autonomous limit")
            
    # If no rules are broken, proceed with normal execution
    if tool_name == "process_refund":
        return process_refund(tool_input.get("amount"))
    elif tool_name == "escalate_to_human":
        return escalate_to_human(tool_input.get("reason"))

# ---------------------------------------------------------
# Tools Definition
# ---------------------------------------------------------
tools = [
    {
        "name": "process_refund",
        "description": "Process a refund for a customer. Use only for amounts <= $500.",
        "input_schema": {
            "type": "object",
            "properties": {"amount": {"type": "number"}},
            "required": ["amount"]
        }
    },
    {
        "name": "escalate_to_human",
        "description": "Escalate the ticket to a human manager.",
        "input_schema": {
            "type": "object",
            "properties": {"reason": {"type": "string"}},
            "required": ["reason"]
        }
    }
]

if __name__ == "__main__":
    print("Scenario: Customer requests an $800 refund for a broken laptop.\n")
    
    # Notice we don't put the $500 limit in the system prompt!
    # The exam teaches that prompt-based enforcement has a non-zero failure rate,
    # so we use programmatic enforcement (the hook) instead.
    system_prompt = """
    You are a customer support agent. 
    Escalate when:
    - Customer explicitly requests a human agent
    - Policy is silent on the customer's specific request
    - You cannot make meaningful progress
    
    Otherwise, if the customer wants a refund, try to process it.
    """
    
    messages = [{"role": "user", "content": "My laptop arrived shattered. It cost $800. I want a refund right now."}]
    
    response = client.messages.create(
        model="claude-3-5-haiku-20241022",
        system=system_prompt,
        max_tokens=1024,
        messages=messages,
        tools=tools
    )
    
    for block in response.content:
        if block.type == "tool_use":
            print(f"Claude attempted to call: `{block.name}` with {block.input}")
            
            # The hook intercepts the call
            final_result = post_tool_use_hook(block.name, block.input)
            
            print(f"\nFinal Result returned to Claude: {final_result}")
