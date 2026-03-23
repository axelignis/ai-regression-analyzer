# AI Regression Analyzer

> Internal QA tooling that automates the first layer of test failure triage — parsing Playwright failures, classifying them with AI, and generating structured reports for engineering and management audiences.

---

## The Problem

In teams running continuous testing, automated failures are a daily reality. The manual investigation workflow is expensive and inconsistent:

- Engineers spend 5–15 minutes per failure reading raw stack traces and guessing root causes
- Severity is assessed subjectively — the same failure gets called `low` by one engineer and `high` by another
- Business impact is estimated from memory, not from structured context
- Investigation insights rarely make it into documentation — they live in a Slack thread or someone's head

At 50–200 tests per deploy cycle with a 10–15% failure rate on active branches, this is hours of repetitive analytical work per week with no audit trail.

---

## Why This Matters

| Without this tool | With this tool |
|---|---|
| Manual triage: 5–15 min per failure | Structured first hypothesis in under 30s |
| Severity is subjective per engineer | Calibrated against a shared explicit rubric |
| Root cause lives in someone's memory | Committed to the repo as a timestamped report |
| Junior engineers guess at impact | Consistent structured guidance from the AI layer |
| Investigation has no audit trail | Every run produces a versioned Markdown report |

This does not replace engineering judgment. It compresses the time to a first, structured hypothesis.

---

## How It Works

- Parses Playwright JSON reporter output into typed, normalized failure records
- Classifies error type deterministically: `assertion` · `timeout` · `element_not_found` · `network` · `unknown`
- Sends each failure to an LLM (Claude or Ollama) with a QA-calibrated triage prompt
- Returns structured analysis: probable cause, severity, business impact, confidence score
- Generates a professional Markdown report readable by QA, engineering, and management

### Pipeline

```
Playwright tests
      ↓  results.json
  parser.py    →  ParsedFailure[]     ← deterministic, no AI dependency
      ↓
  triage.py    →  AnalysisResult[]    ← LLM call happens here
      ↓
  reporter.py  →  reports/failure-report.md
```

Each layer has exactly one responsibility. The parser works offline and has zero AI dependency. Swap the LLM provider with one environment variable — no code changes required.

---

## Demo Flow

From clone to report in under 2 minutes:

```bash
# 1. Install
npm install && npx playwright install chromium
python -m venv .venv && .venv/bin/pip install -r requirements.txt

# 2. Run tests — produces test-results/results.json
npm test

# 3. Analyze with Ollama (local, free, no API key)
LLM_PROVIDER=ollama .venv/bin/python -m analyzer.reporter

# 4. Read the report
open reports/failure-report.md
```

To use Claude instead: set `ANTHROPIC_API_KEY` and remove `LLM_PROVIDER=ollama`.

---

## Output

```markdown
# AI Regression Analysis Report

Generated: 2026-03-21 21:45 UTC  |  Failures: 1  |  Browsers: chromium

---

## Executive Summary

**Total failures analyzed:** 1

| Severity     | Count |
|---|---|
| 🔴 Critical  | 0     |
| 🟠 High      | 0     |
| 🟡 Medium    | 1     |
| 🟢 Low       | 0     |

---

## 1. checkout: product price matches expected value

### Test Details

| Field      | Value                    |
|---|---|
| File       | `ui/checkout.spec.ts`    |
| Browser    | chromium                 |
| Duration   | 5.9s                     |
| Error type | `assertion`              |
| Timestamp  | 2026-03-21 19:55 UTC     |

### AI Triage

| Field            | Value                                                           |
|---|---|
| Probable cause   | Stale test expectation — expected $9.99, application returns $29.99 |
| Severity         | 🟡 MEDIUM                                                      |
| Confidence       | 85%                                                            |
| Business impact  | Users may see incorrect prices, risking checkout abandonment   |

### Recommended Actions

- [ ] Verify current product price in the application
- [ ] Update test expectation if price change was intentional
- [ ] Check recent deployments for pricing changes

### Raw Error Snapshot

    Error: expect(locator).toHaveText(expected) failed
    Expected: "$9.99"
    Received: "$29.99"
```

---

## Engineering Principles

**Deterministic before probabilistic.** Error type classification uses string matching rules before anything reaches the AI. The AI layer handles reasoning, not classification — keeping each concern testable and independently debuggable.

**AI as augmentation, not replacement.** The tool produces a first hypothesis with severity, cause, and impact. Engineers validate and act on it. The AI compresses time-to-insight; it does not own the decision.

**Provider abstraction without framework overhead.** Two LLM providers behind a single `complete(system, user) → str` function. No dependency injection, no abstract base classes. Adding a third provider is one function and one dict entry.

**Vertical slice over horizontal buildout.** One test → one parser → one AI call → one report before expanding any layer. The pipeline was end-to-end functional before it was complete.

**Simplicity over extensibility.** Every abstraction exists to serve a current need. The one deliberate exception is `_extract_specs()` — a named extension point for describe-block support that required zero extra code to establish.

---

## Engineering Decisions

Key decisions made during development, with the reasoning behind them:

- **Used Playwright's `spec.id` as the test identifier** — Playwright generates a stable hash per test. Deriving our own would have added fragile logic and diverged from Playwright's own internal identifier.
- **`string.Template` over `str.format()` for prompt templates** — Playwright stack traces contain `{` and `}` from TypeScript source. `str.format()` raises `KeyError` on those. A non-obvious failure mode eliminated by choosing the right template mechanism.
- **Lazy `import anthropic` inside the provider function** — When `LLM_PROVIDER=ollama`, the Anthropic package is never imported. Keeps dependencies honest; each provider path is independently deployable.
- **ANSI stripping in the parser, not the reporter** — Error messages are cleaned once at parse time. All downstream consumers receive clean text without knowing ANSI encoding ever existed.
- **Separate `generate()` and `write()` in the reporter** — `generate()` returns a string with no filesystem side effects. Independently testable, and the write destination is replaceable without touching formatting logic.

Full detail: [Architecture](docs/architecture.md)

---

## What Was Not Built

| Decision | Reasoning |
|---|---|
| No retry logic on AI failures | Retrying masks the failure mode. Understand the pattern first, then add the retry. |
| No unified `run.py` entry point | Three independent `main()` functions are more useful for debugging each layer separately. |
| No dashboard or HTML output | Markdown renders natively in GitHub, Confluence, and CI. No build step, no viewer dependency. |
| No agent framework | A four-function pipeline with typed contracts does not need an orchestration layer. |
| No database | Files are auditable, diffable, and require no infrastructure. A database is justified at trend analysis scale. |
| No describe-block parser support yet | The extension point exists. It was not built because the current test suite doesn't use `test.describe()`. |

---

## Lessons Learned

Observations from building this system — not rules, but real friction points encountered:

- **Local LLMs have a severity calibration ceiling.** Prompt improvements helped vocabulary but not multi-rule rubric adherence. Model capacity, not prompt length, was the limiting factor.
- **Inspect real data before designing the abstraction.** Reading `results.json` before writing the parser revealed Playwright's native `spec.id`, ANSI encoding, and exact field locations. All three would have caused bugs had we assumed.
- **Contract naming decisions compound.** Renaming `assertion_error` → `assertion` before Phase 3 required changes in three files simultaneously. In a system with more consumers, it would have been a breaking change.
- **Structured input anchors LLM reasoning.** Labeling fields (`error_type: assertion`) reduced root cause hallucination more than longer prompt descriptions did.
- **Vertical slice development eliminates integration lag.** Having a working pipeline in session one meant every subsequent phase had something real to test against.

Full retrospective: [Lessons Learned](docs/lessons-learned.md)

---

## Future Improvements

Ordered by impact, not scope:

1. **JSON validation + single retry** — Characterize and handle Ollama's malformed JSON without masking it with a loop
2. **`run.py` with CI exit codes** — Exit 1 on critical severity; usable in GitHub Actions without extra scripting
3. **GitHub Actions workflow** — Run analyzer post-test, upload `failure-report.md` as a workflow artifact
4. **Describe-block parser support** — Extend `_extract_specs()` for `test.describe()` suites (5-line change, extension point already exists)
5. **Cross-run trend analysis** — Track severity distribution across commits to surface flakiness and regressions

---

## Capabilities Demonstrated

| Domain | Applied Skills |
|---|---|
| Test Automation | Playwright, TypeScript, intentional failure design, dual-reporter configuration |
| AI Integration | LLM prompt engineering, provider abstraction, structured output parsing, local vs cloud model evaluation |
| Python Engineering | Typed dataclass contracts, modular pipeline design, stdlib-first development, lazy imports |
| QA Thinking | Failure classification, severity calibration, business impact framing, triage workflow design |
| Tooling Design | Internal CLI architecture, layer separation, unidirectional data flow, extensibility by design |
| Engineering Judgment | Explicit tradeoff documentation, "not built" reasoning, vertical slice methodology |
| Technical Writing | Architecture decision records, case studies, engineering retrospectives |

---

## Provider Support

| Provider | Model | Setup | Reliability |
|---|---|---|---|
| Ollama (local) | `llama3.2` | `ollama pull llama3.2` | Good — occasional JSON drift on structured output |
| Anthropic Claude | `claude-sonnet-4-6` | API key required | Excellent — consistent schema adherence |

Honest comparison of observed behavior: [Case Study → Local vs Cloud Models](docs/case-study.md)

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `LLM_PROVIDER` | `anthropic` | `anthropic` or `ollama` |
| `ANTHROPIC_API_KEY` | — | Required when provider is `anthropic` |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_MODEL` | `llama3.2` | Local model to use |

---

## Documentation

| Document | Contents |
|---|---|
| [Architecture](docs/architecture.md) | Layer design, data contracts, tradeoffs, extension points |
| [Case Study](docs/case-study.md) | Problem framing, business value, provider comparison, engineering decisions |
| [Lessons Learned](docs/lessons-learned.md) | Post-build retrospective: what worked, what didn't, what was discovered |
