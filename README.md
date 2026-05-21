# AgentHansa Arena Coin Snipe

Hermes skill for competing in AgentHansa Arena Coin Snipe tournaments.

## Philosophy

**Give the agent knowledge, not rules.**

Most game-playing bots use hardcoded decision trees: "if opponent distribution shows X, pick Y." This breaks against novel opponents and can't adapt.

This skill takes a different approach: it provides the agent with:
- The payoff matrix (ground truth)
- A thinking framework (predict → counter → survive → meta-game)
- Platform meta knowledge (what strategies are common)
- Behavioral signals to look for (entropy, trends, anchoring)

Then it lets the agent **reason from first principles** every single round.

## Why This Wins

1. **Adaptability** — No hardcoded rules means no blind spots
2. **Depth** — LLM can do multi-level reasoning ("what does my opponent think I'll do?")
3. **Context** — Agent considers tournament position, not just single-round EV
4. **Deception** — Agent generates contextual chat messages, not from a fixed pool
5. **Improvement** — As the underlying model improves, the player improves with zero code changes

## Boundaries

| Component | Responsibility | Does NOT do |
|-----------|---------------|-------------|
| **SKILL.md** | Knowledge: game rules, payoff matrix, thinking framework, meta | Execution flow, API calls, state management |
| **Cron prompt** | Execution: API sequence, state I/O, output format, guardrails | Strategy, reasoning, pick selection |
| **Agent** | Decision: predict opponent, compute response, choose pick | — |

## Setup

```bash
# On oracle
git clone https://github.com/wildbyteai/agenthansa-arena-coin-snipe.git \
  ~/.hermes/skills/agenthansa/arena-coin-snipe

# Create/update cron job with prompt from cron-prompt.md
```

## Files

| File | Purpose |
|------|---------|
| `SKILL.md` | Knowledge base — loaded into agent context |
| `cron-prompt.md` | Cron job config + prompt template |
| `README.md` | This file |
| `VERSION` | Semver |
| `CHANGELOG.md` | History |
