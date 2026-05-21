# Changelog

## 3.0.0 (2026-05-21)

Fundamental rethink. Trust the agent's intelligence.

**Philosophy change**: Stop writing rules for the agent to follow. Instead, give the agent the *knowledge* it needs and let it *think*.

- SKILL.md is now a compact knowledge document, not a decision tree
- Removed all "if X then Y" classification tables
- Removed fixed R1 defaults — agent reasons from first principles each time
- Added thinking framework: predict → counter → survive → meta-game
- Added behavioral economics perspective (entropy, signals, adaptation)
- Cron prompt is minimal: just the execution skeleton + hard constraints
- Agent does all reasoning fresh each invocation — no cached logic

**Key insight**: An LLM with a payoff matrix and opponent history data can reason better than any hardcoded decision tree. The skill's job is to frame the problem correctly, not to solve it.

## 2.0.0 (2026-05-21)

- Separated skill (knowledge) from cron (execution)
- Added Level-K thinking, mixed strategies, information warfare
- Removed script dependencies

## 1.0.0 (2026-05-21)

- Initial release (deprecated — too mechanical)
