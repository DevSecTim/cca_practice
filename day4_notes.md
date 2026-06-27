# Multi-Agent Orchestration (Hub-and-Spoke Pattern)

```mermaid
graph TD
    USER([USER]) -->|Request| COORDINATOR[COORDINATOR]
    
    COORDINATOR -->|Task tool| SEARCH[SEARCH SUBAGENT]
    SEARCH -.->|Returns results| COORDINATOR
    
    COORDINATOR -->|Task tool| ANALYSIS[ANALYSIS SUBAGENT]
    ANALYSIS -.->|Returns results| COORDINATOR
    
    COORDINATOR -->|Explicitly passes collected results| SYNTHESIS[SYNTHESIS SUBAGENT]
    SYNTHESIS -.->|Returns final summary| COORDINATOR
    
    COORDINATOR -->|Final Response| USER
```

> **Critical Rule:** Subagents do NOT share memory. They do NOT see each other's results. Only the coordinator sees all results and must pass context explicitly.

# Coordinator prompt

### CORRECT: Coordinator explicitly passes ALL context:
COORDINATOR PROMPT TO SYNTHESIS SUBAGENT:
"Combine the following findings:
SEARCH RESULTS: {paste search agent output here}
DOCUMENT ANALYSIS: {paste analysis agent output here}
Preserve source URLs and dates. Report conflicts."

# WRONG — subagent has no memory of 'earlier':
"Synthesise the research that was done earlier."