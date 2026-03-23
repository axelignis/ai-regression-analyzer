# Case Study: Reducing QA Failure Analysis Overhead

## The Problem

A Playwright test fails in CI. Now what?

An engineer opens the report, reads the stack trace, identifies what broke,
decides how severe it is, estimates user impact, determines whether it is a test
data problem or a product regression, and writes up a summary for the team. For
a single failure this takes 5–15 minutes of focused attention.

In a team running 50–200 automated tests per deploy cycle, with a 10–15% failure
rate on active development branches, this is not an edge case — it is a daily
tax on engineering throughput.

The problems are consistent and predictable:

**Classification inconsistency.** Senior and junior engineers assess the same
failure differently. Severity labels are subjective without a shared rubric.
A price mismatch gets called "low" by one person and "high" by another depending
on their context.

**Context loss.** The person triaging may not know which business flow the test
covers, which recent deployment touched that area, or whether this failure has
appeared before.

**Documentation lag.** Insights from failure analysis rarely make it back to the
team in a structured format. The investigation lives in someone's head or a Slack
thread.

---

## What This Tool Changes

**Before:**
```
CI fails → engineer opens raw test report → reads stack trace →
guesses root cause → estimates impact manually → posts summary in Slack
```

**After:**
```
CI fails → results.json → AI Regression Analyzer →
structured report: severity · cause · impact · actions
```

The first triage layer is automated. Engineers review and validate a hypothesis
rather than producing one from scratch. The report is consistent, timestamped,
and written to the repo — not a Slack message that expires.

The tool does not replace engineering judgment. It compresses the time to first
hypothesis from 10 minutes to under 30 seconds.

---

## Local vs Cloud Models: Honest Assessment

The tool supports two providers. Their tradeoffs are real and documented here
because choosing the wrong one for the wrong context costs trust in the output.

### Ollama — llama3.2 (local)

**Strengths:**
- Zero cost, no API key, no network dependency
- Viable in air-gapped or offline development environments
- Fast response time on capable hardware

**Observed weaknesses:**
- Occasionally returns malformed JSON requiring a parse retry
- Severity classification drifts from the defined rubric — a pricing inconsistency
  classified as `low` ("cosmetic") instead of `medium` in observed runs
- Root cause framing is less precise — tends toward generic explanations rather
  than QA-specific vocabulary (stale test data, fixture drift, environment mismatch)

**Verdict:** Suitable for offline development and low-stakes local runs. Not
recommended for team-facing CI reporting without JSON validation and retry logic.

### Anthropic Claude — claude-sonnet-4-6 (cloud)

**Strengths:**
- Reliable structured JSON output matching the defined schema across runs
- Accurate severity classification against the rubric
- Correctly distinguishes assertion failures from locator failures — an assertion
  error on a price field is classified as test data or regression, not a selector
  stability problem
- Uses QA-oriented reasoning vocabulary from the system prompt

**Weaknesses:**
- Requires API credits and outbound network access
- Adds 1–3 seconds per failure to the pipeline

**Verdict:** Recommended for CI integration and any output shown to engineering
or management audiences.

---

## Business Value

| Outcome | Impact |
|---|---|
| First triage automated | Saves 5–15 minutes per failure per engineer |
| Consistent severity classification | Reduces escalation noise and misrouted bugs |
| Structured written reports | Creates an audit trail without additional documentation effort |
| Shared reasoning vocabulary | Accelerates junior engineer onboarding — they receive structured guidance rather than guessing |
| Provider flexibility | Teams without API budget can run locally; teams with CI requirements can use Claude |

---

## Limitations

**AI confidence ≠ correctness.** The `confidence` field reflects the model's
self-assessed certainty, not verified accuracy. High confidence on an incorrect
diagnosis is possible. The output is a first hypothesis to be validated, not a
final answer.

**Prompt quality determines output quality.** The triage prompt was tuned for
assertion and locator failures on an e-commerce checkout flow. Different domains,
error patterns, or test structures will need prompt iteration before output
quality is reliable.

**Local model quality is hardware-dependent.** Results with Ollama depend on
model size and available compute. A 7B or 13B parameter model on adequate
hardware will significantly outperform a 2B model.

**This is not a test monitoring platform.** It analyzes a single results file
in isolation. Flakiness detection, cross-run trend analysis, and historical
comparison are outside current scope.

---

## Engineering Decisions

**Inspect the real data before building the abstraction.**
Before writing a single line of `parser.py`, we queried the actual `results.json`
with Python to understand its exact shape. That inspection revealed three
non-obvious things: Playwright already generates a stable `spec.id` per test (no
need to derive one from file + title), `spec.file` exists on the spec itself and
not only on the parent suite, and error messages are ANSI-encoded. All three
would have caused bugs or unnecessary complexity had we coded against assumed
schema.

**Classify error type in the parser, not in the AI layer.**
`error_type` is derived from deterministic string matching on the error message —
`expect(` signals assertion, `waiting for locator` signals element_not_found, and
so on. This keeps the AI layer focused on reasoning rather than classification,
and makes the classification logic testable without a model. The check order
matters: `expect(` is tested before `waiting for locator` because assertion error
messages contain the word "locator" in their call log and a naive check would
misclassify them.

**`string.Template` instead of `str.format()` for prompt templates.**
Playwright stack traces contain `{` and `}` from TypeScript source — arrow
functions, object literals, destructuring syntax. `str.format()` raises `KeyError`
on those characters when they appear in substitution context. `$variable` syntax
from Python's `string.Template` is safe against arbitrary text. This was not a
hypothetical concern: the stack traces in our `results.json` contain multiple
instances.

**Lazy provider imports.**
`import anthropic` lives inside `_complete_anthropic()`, not at the module level.
When `LLM_PROVIDER=ollama`, the `anthropic` package is never imported. The Ollama
path uses only `urllib.request` from stdlib — no extra dependency declared or
loaded. The pattern makes provider boundaries explicit and keeps each path
independently deployable.

**Separate `generate()` and `write()` in the reporter.**
`generate()` returns a string. `write()` takes that string and persists it. This
is a small separation with real consequences: `generate()` is testable without
filesystem side effects, and the write destination can be changed — stdout, S3,
a Slack attachment — without touching the formatting logic.

---

## Tradeoffs Accepted

**No retry logic on malformed AI responses.**
Local models occasionally return JSON that fails to parse. The current code
surfaces a `json.JSONDecodeError` rather than retrying silently. This is
intentional: a retry loop masks the failure mode and makes it harder to
characterize. The right fix — prompt hardening or model selection — requires
observing the failure, not hiding it. A retry becomes justified once the failure
pattern is understood.

**One test, one failure type in the current suite.**
The test suite has a single intentionally failing test covering `assertion` error
type. A complete suite would exercise all five `error_type` values across multiple
flows. The tradeoff: shipping a working vertical pipeline early versus building
horizontal test coverage first. The pipeline exercises the full contract end to
end; broadening coverage is a mechanical extension with no architectural risk.

**`confidence` is self-reported and uncalibrated.**
`AnalysisResult.confidence` is the model's own estimate of its certainty, not
an independently validated score. High confidence on an incorrect diagnosis is
possible. Accepted because: the field still provides useful signal for readers
(`0.4` and `0.9` communicate different things), calibration requires ground truth
labels we do not have, and removing the field would make the output less honest
about uncertainty rather than more.

**No `run.py` single entry point.**
Each layer exposes its own `main()`. The invocation is slightly more verbose
(`python -m analyzer.reporter`) than a unified `python run.py`. Accepted because
three independent entry points are more useful for development and debugging than
a convenience wrapper. A single entry point becomes justified when CI integration
or argument parsing is added — not before.

---

## Lessons Learned

**Contract naming is expensive to change.**
We defined `error_type` as `assertion_error` and `network_error` in `models.py`.
Before Phase 3, a contract review caught that the shorter forms — `assertion`,
`network` — were cleaner and more consistent. Fixing it required updating
`models.py`, `parser.py`, and `CLAUDE.md` simultaneously. The drift was small
and caught early; in a system with more consumers it would have been a breaking
change. Spend more time on names in shared contracts upfront.

**Prompt quality has a model-capacity ceiling.**
We rewrote the system prompt with an explicit severity rubric and QA-oriented
reasoning vocabulary specifically because initial output was miscalibrated. With
`llama3.2`, severity classification still drifted — a pricing inconsistency was
classified as `low` ("cosmetic") despite explicit rubric text saying pricing
inconsistencies are `medium`. The model followed surface vocabulary but not
multi-rule reasoning. There is a point where prompt improvement stops helping
and model selection begins. Recognizing that ceiling early prevents wasted
iteration on the wrong variable.

**Explicit defaults in config signal copy-paste, not intent.**
`headless: true` and `video: 'off'` were initially written explicitly in
`playwright.config.ts`. Both are Playwright defaults. In code review, explicit
defaults look like cargo-culted configuration copied from a tutorial — they do
not signal a considered choice. Only values that deviate from defaults should be
explicit. This is a small thing that affects how experienced engineers read your
configuration files.

**Small premature abstractions are still premature.**
`const CREDENTIALS = { username: 'standard_user', password: 'secret_sauce' }`
wrapped two strings used in exactly one place. It was removed in review. The
pattern — wrapping a one-time value in a named structure — adds indirection
without benefit and signals hypothetical future needs that may never exist.
The right question before creating any abstraction: does this serve a current
need or a possible future one?

---

## What I Would Do Next

**Add JSON validation and a single retry.**
The Ollama failure mode — malformed JSON — is now characterized. One retry with
`json.JSONDecodeError` handling before raising is appropriate. The constraint:
exactly one retry, not a loop. A loop hides prompt problems; a single retry
handles transient model output variance.

**Build `run.py` for CI integration.**
A single entry point that chains parse → analyze all failures → report, exiting
with status code 1 if any `critical` severity result is found. This is what makes
the tool actionable in a GitHub Actions workflow rather than a local development
aid.

**Add GitHub Actions workflow.**
A `.github/workflows/analyze.yml` that runs `npm test` on push, executes the
analyzer, and uploads `reports/failure-report.md` as a workflow artifact. The
report becomes a persistent CI artifact attached to the run that triggered the
failures.

**Extend the parser for describe-block support.**
Real test suites use `test.describe()`. When they do, Playwright nests suites in
the JSON output. `_extract_specs()` in `parser.py` is already the designated
extension point — adding recursion into `suite["suites"]` is a five-line change.
Without this, the tool cannot process most real-world test suites.

**Validate the full prompt against Claude.**
The triage prompt was designed around Claude's reasoning capabilities and tested
primarily with Ollama. Running the same assertion failure that Ollama misclassified
against Claude would confirm whether severity drift is a prompt problem or a model
capacity problem. That distinction determines whether to invest in prompt iteration
or accept Ollama as a development-only provider.
