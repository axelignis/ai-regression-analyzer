# Architecture

## Design Philosophy

Four independent layers with unidirectional data flow. Each layer communicates
through typed contracts defined in `analyzer/models.py`. No layer knows about
layers beyond its immediate neighbor.

The hard constraint: **the parser has zero AI dependency and must work offline.**
A parser that calls an LLM is not a parser — it is a coupled system that fails
for two unrelated reasons and cannot be tested in isolation.

---

## Pipeline

```
Test Execution  →  Parser  →  AI Analysis  →  Reporter
(Playwright/TS)    (Python)    (Python)         (Python)
```

### Layer Responsibilities

| Layer | Input | Output | Dependency |
|---|---|---|---|
| Test Execution | test suite | `results.json` | Playwright |
| Parser | `results.json` | `ParsedFailure[]` | stdlib only |
| AI Analysis | `ParsedFailure[]` | `AnalysisResult[]` | LLM provider |
| Reporter | `AnalysisResult[]` | `failure-report.md` | stdlib only |

---

## Data Contracts

Both contracts live in `analyzer/models.py`. This file is the only shared
dependency across layers — if it changes, every layer is affected.

**ParsedFailure** — produced by the parser, consumed by AI analysis:

```python
@dataclass
class ParsedFailure:
    test_id: str        # Playwright-native stable ID (file + title hash)
    test_title: str
    file: str
    error_type: ErrorType   # assertion | timeout | element_not_found | network | unknown
    error_message: str      # ANSI-stripped
    stack_trace: str        # ANSI-stripped
    duration_ms: int
    browser: str
    timestamp: str
```

**AnalysisResult** — produced by AI analysis, consumed by the reporter:

```python
@dataclass
class AnalysisResult:
    failure: ParsedFailure
    probable_cause: str
    severity: Severity      # critical | high | medium | low
    business_impact: str
    confidence: float       # 0.0 – 1.0
    suggested_steps: list[str]
```

---

## Key Design Decisions

### Parser independence from AI

`parser.py` uses only stdlib (`json`, `re`). It performs ANSI stripping and
error-type classification through deterministic string matching — no model call.
This means the parser can be tested without mocking AI, and parsing failures
indicate a shape change in Playwright's output, not a model issue.

### LLM provider as a one-file abstraction

`ai_client.py` exposes one function: `complete(system, user) → str`. All provider
logic is internal. `triage.py` calls `complete()` and never imports `anthropic`
or constructs HTTP requests. Adding a provider is one function + one dict entry.

Provider is selected via `LLM_PROVIDER` environment variable. Defaults to
`anthropic`. Supported: `anthropic`, `ollama`.

### Prompt externalization

System and user prompt templates live in `prompts/`, not in Python source.
Prompt iteration is a separate concern from code changes. The system prompt
defines the triage rubric (severity definitions, reasoning vocabulary). The user
prompt template is filled with `string.Template` — not `str.format()`.

**Why not `str.format()`:** Playwright error messages and stack traces contain
`{` and `}` (TypeScript arrow functions, object destructuring). `str.format()`
raises `KeyError` on those. `$variable` syntax is safe against arbitrary text.

### Dataclasses over Pydantic

No validation framework at this stage. Dataclasses give typed contracts with zero
runtime overhead and no external dependency. Pydantic makes sense when models
become an API boundary or require coercion — they are not one yet.

### Lazy provider imports

`import anthropic` is inside `_complete_anthropic()`, not at module level.
When `LLM_PROVIDER=ollama`, the `anthropic` package is never imported. The Ollama
path uses only `urllib.request` from stdlib — no extra dependency.

---

## Extension Points

**Adding a new LLM provider (e.g., OpenAI, Gemini):**
Add one function to `ai_client.py` following the `_complete_*` pattern.
Add one entry to `_PROVIDERS`. No other files change.

**Adding describe-block test support:**
When Playwright tests use `test.describe()`, the JSON output nests suites.
`_extract_specs()` in `parser.py` is the single extension point — add recursion
into `suite["suites"]` there. No other files change.

**Batch analysis across multiple failures:**
`reporter.generate()` already accepts `list[AnalysisResult]`. The loop that
calls `triage.analyze()` per failure belongs in a future `run.py` entry point.
Both `triage.py` and `reporter.py` are already batch-ready.

---

## What Was Not Built

**No CLI framework (argparse, click, typer):**
A single `sys.argv[1]` path argument is sufficient at this scope. Frameworks add
dependency weight and documentation overhead for marginal ergonomic gain.

**No retry logic on AI calls:**
Local models occasionally return malformed JSON. A retry loop masks the failure
mode. The right fix is prompt hardening or model selection. Retries belong in a
later phase after failure patterns are characterized.

**No database:**
Failures and reports are files. Files are auditable, diffable, and require no
infrastructure. A database is justified when cross-run trend analysis is needed.

**No HTML or PDF output:**
Markdown renders natively in GitHub, Notion, Confluence, and most CI dashboards.
It requires no build step and no viewer dependency.
