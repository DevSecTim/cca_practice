import anthropic
client = anthropic.Anthropic()

response = client.messages.create(
    model="claude-sonnet-4-5",
    max_tokens=256,
    tools=[{
        "name": "get_weather",
        "description": "Returns weather for a city. Input: city name.",
        "input_schema": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string"
                }
            },
            "required": ["city"]
        }
    }],
    messages=[{
        "role": "user",
        "content": "The weather in the capital of France"
    }]
)

print("stop_reason", response.stop_reason)
#print("text:", response.content[0].text)
