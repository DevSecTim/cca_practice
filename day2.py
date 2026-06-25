import anthropic
client = anthropic.Anthropic()


while True:
    response = client.messages.create(...)
    