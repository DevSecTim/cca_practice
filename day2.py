import anthropic

client = anthropic.Anthropic()

# A mock tool function so the code actually runs
def run_tool(name, input_data):
    print(f"\n[Tool Execution] Running '{name}' with {input_data}")
    return "The weather in that location is 72°F and sunny."

# Tool definition for Claude
tools = [{
    "name": "get_weather",
    "description": "Returns weather for a city. Input: city name.",
    "input_schema": {
        "type": "object",
        "properties": {"city": {"type": "string"}},
        "required": ["city"]
    }
}]

# Initialize conversation history with a prompt
messages = [{"role": "user", "content": "What is the weather in San Francisco?"}]

print("Starting agentic loop...")
while True:
    print("\nCalling Claude...")
    response = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=1024,
        messages=messages,
        tools=tools
    )
    
    # 1. Always append the assistant's response to the conversation history
    messages.append({
        "role": "assistant",
        "content": response.content
    })
    
    # 2. Check if Claude is finished
    if response.stop_reason == "end_turn":
        print("\n[Final Answer]")
        # Find the text block and print it
        for block in response.content:
            if block.type == "text":
                print(block.text)
        break
        
    # 3. Check if Claude wants to use a tool
    if response.stop_reason == "tool_use":
        tool_results = []
        
        for block in response.content:
            if block.type == "tool_use":
                # Execute the tool
                result = run_tool(block.name, block.input)
                
                # Format the result correctly for Claude
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result
                })
                
        # Append the tool results back as a new user message
        messages.append({
            "role": "user",
            "content": tool_results
        })