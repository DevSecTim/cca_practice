import anthropic

# Initialize the Anthropic client
client = anthropic.Anthropic()

# ---------------------------------------------------------
# SUBAGENT LOGIC
# ---------------------------------------------------------
def run_subagent(role, task, context=""):
    """This function is the actual subagent. It's a standard API call."""
    system = f"You are a {role}. Be concise."
    
    # Properly format the content string based on context availability
    content = task if not context else f"{task}\n\nContext:\n{context}"
    
    response = client.messages.create(
        model="claude-haiku-4-5", # Haiku is great/cheap for subagents
        system=system,
        max_tokens=1024,
        messages=[{"role": "user", "content": content}]
    )
    return response.content[0].text

# ---------------------------------------------------------
# COORDINATOR AGENTIC LOOP LOGIC
# ---------------------------------------------------------

# The Coordinator has ONE tool: the ability to delegate tasks to subagents
tools = [{
    "name": "delegate_task",
    "description": "Delegate a specialized task to a subagent.",
    "input_schema": {
        "type": "object",
        "properties": {
            "subagent_role": {
                "type": "string", 
                "enum": ["search agent", "analysis agent"],
                "description": "The persona/role of the subagent."
            },
            "task": {
                "type": "string",
                "description": "Highly detailed instructions for what the subagent must accomplish."
            }
        },
        "required": ["subagent_role", "task"]
    }
}]

if __name__ == "__main__":
    print("Starting dynamic Coordinator agentic loop...\n")
    
    # The user gives a high-level goal to the Coordinator
    user_prompt = (
        "Research AI's impact on music. "
        "Use the search agent to find 2 facts. "
        "Use the analysis agent to identify 1 risk and 1 opportunity based on those facts. "
        "Finally, synthesize everything into a 3-sentence summary for me."
    )
    
    messages = [{"role": "user", "content": user_prompt}]
    
    while True:
        print("Coordinator is thinking...")
        response = client.messages.create(
            model="claude-sonnet-4-5", # Coordinator is usually a larger model
            system="You are an Orchestration Coordinator. You do not do research yourself. You MUST use the `delegate_task` tool to spawn subagents to do the work. Once you have gathered all necessary context from your subagents, synthesize their findings and answer the user.",
            max_tokens=1024,
            messages=messages,
            tools=tools
        )
        
        # 1. Always append the Coordinator's response
        messages.append({
            "role": "assistant",
            "content": response.content
        })
        
        # 2. Did the Coordinator finish the task?
        if response.stop_reason == "end_turn":
            print("\n=================================")
            print("[Final Synthesis from Coordinator]")
            print("=================================")
            for block in response.content:
                if block.type == "text":
                    print(block.text)
            break
            
        # 3. Did the Coordinator decide to delegate to a subagent?
        if response.stop_reason == "tool_use":
            tool_results = []
            
            for block in response.content:
                if block.type == "tool_use":
                    role = block.input['subagent_role']
                    task = block.input['task']
                    
                    print(f"\n---> [Delegating] Spawning a '{role}'")
                    print(f"---> [Instructions] {task}")
                    
                    # Actually run the subagent function!
                    result = run_subagent(role, task)
                    print(f"<--- [Subagent Result] {result}\n")
                    
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result
                    })
            
            # Send the subagent's results back to the Coordinator
            messages.append({
                "role": "user",
                "content": tool_results
            })