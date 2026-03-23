# AI Regression Analyzer — Project Constitution

## Purpose
Internal QA tooling that analyzes Playwright test failures using AI to classify
severity, identify probable causes, estimate business impact, and generate
actionable reports.

## Architecture
Four independent layers with unidirectional data flow:

```
Test Execution → Parser → AI Analysis → Reporting
```

- Each layer has exactly one responsibility
- Layers communicate only through contracts defined in `analyzer/models.py`
- Parser has zero AI dependency — it must work offline
- Prompts live in `/prompts/`, never hardcoded in Python modules

## Stack
- Tests: Playwright + TypeScript
- Analyzer: Python 3.11+
- AI: Anthropic Claude API (abstracted for LLM portability)
- Output: JSON intermediate + Markdown reports

## Contracts
| Field | Valid values |
|---|---|
| `error_type` | `assertion` · `timeout` · `element_not_found` · `network` · `unknown` |
| `severity` | `critical` · `high` · `medium` · `low` |
| `confidence` | `float` 0.0 – 1.0 |

## Quality Rules
- No business logic in the reporting layer
- No parsing logic in the AI layer
- No AI calls inside the parser
- Models are the single source of truth between all layers
