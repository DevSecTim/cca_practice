mkdir -p .claude/rules
# Create .claude/rules/testing.md with this content:
---
paths:
- "**/*.test.py"
- "**/*.spec.py"
---
# Testing conventions
- Always use pytest, never unittest
- Every test function starts with test_
- Mock all external API calls with pytest-mock