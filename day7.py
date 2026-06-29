import anthropic

# Initialize the Anthropic client
client = anthropic.Anthropic()

extraction_tool = {
    "name": "extract_invoice",
    "description": "Extract data from any invoice document.",
    "input_schema": {
        "type": "object",
        "properties": {
            "vendor_name": {"type": "string"},
            "total_amount": {"type": "number"},
            "currency": {
                "type": "string",
                "enum": ["USD","EUR","GBP","INR","other"]},
            "currency_detail": {"type": ["string","null"]},
            "due_date": {"type": ["string","null"]}
        },
        "required": [
            "vendor_name",
            "total_amount",
            "currency"
        ]
    }
}

# tool_choice forces this specific tool to be called:
tool_choice = {"type": "tool", "name": "extract_invoice"}

if __name__ == "__main__":
    # Test with a document missing the due_date (as per the study guide)
    document_text = "Invoice from TechCorp, INV-001, $500 USD"
    
    print(f"Document text: '{document_text}'\n")
    print("Calling Claude with forced tool extraction...")
    
    response = client.messages.create(
        model="claude-3-5-haiku-20241022", # Haiku is excellent for fast extraction tasks
        max_tokens=1024,
        messages=[
            {
                "role": "user", 
                "content": f"Extract the data from this document:\n<document>{document_text}</document>"
            }
        ],
        tools=[extraction_tool],
        tool_choice=tool_choice
    )
    
    # Because we forced the tool, the response will be a tool_use block
    # containing the exact extracted JSON matching our schema
    extracted_data = response.content[0].input
    
    print("\n[Extracted JSON Data]")
    import json
    print(json.dumps(extracted_data, indent=2))