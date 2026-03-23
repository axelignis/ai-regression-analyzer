# Lessons Learned

Engineering observations from building AI Regression Analyzer.
Written as a post-build retrospective — not prescriptive rules, but real friction points and decisions encountered during development.

---

## 1. Small local LLMs have a severity calibration ceiling

**What happened:** We wrote an explicit severity rubric in the system prompt — pricing inconsistencies map to `medium`, cosmetic issues map to `low`. With `llama3.2`, a price mismatch (expected `$9.99`, received `$29.99`) was classified as `low` ("cosmetic") across multiple runs, despite the rubric being clearly stated.

**What it means:** There is a point where prompt improvement stops helping and model selection begins. A 2B parameter model will follow surface vocabulary patterns but not apply multi-rule reasoning. Spending additional iteration on the prompt when the model lacks the capacity to apply it is wasted effort — the ceiling is the model, not the prompt.

**Practical implication:** Test prompt changes against the exact model you intend to deploy. Results do not transfer reliably between model sizes or families.

---

## 2. Inspect real data before designing the abstraction

**What happened:** Before writing a single line of `parser.py`, we queried the actual `results.json` with Python to understand its exact structure. Three things would have caused bugs or unnecessary complexity had we coded against an assumed schema:

- Playwright already generates a stable `spec.id` per test — no need to derive one from file + title
- `spec.file` exists on the spec itself, not only on the parent suite
- Error messages and stack traces are ANSI-encoded — invisible until you print `repr()` on the raw string

**What it means:** The schema the documentation describes and the schema the system actually emits are often different. Assumptions about data shape are among the most expensive bugs in pipeline code — they may not surface until a specific edge case is hit in production.

**Practical implication:** Always read a real sample of the data before designing the consuming model. `python3 -c "import json; print(json.load(open('output.json')))"` before writing a single dataclass.

---

## 3. Contract naming decisions are expensive to change

**What happened:** `error_type` was initially defined as `assertion_error` and `network_error` in `models.py`. A contract review before Phase 3 identified that shorter forms — `assertion`, `network` — were cleaner and more consistent with the other values. Fixing this required simultaneous changes to `models.py`, `parser.py`, and `CLAUDE.md`.

**What it means:** In a system with more consumers — multiple parsers, stored failure records, external integrations — renaming a contract field is a breaking change with migration cost proportional to the number of consumers. The earlier a contract is stabilized, the cheaper it is.

**Practical implication:** Spend more time on names in shared contracts before the first consumer is written. Apply the test: "if I changed this name in six months, what would break?" If the answer is "a lot," slow down on the naming decision now.

---

## 4. Structured input anchors LLM reasoning

**What happened:** An earlier iteration of the user prompt sent a relatively unstructured error message block. Adding clearly labeled fields — `Error type: assertion`, `Browser: chromium`, `Duration: 5.9s`, `File: ui/checkout.spec.ts` — reduced root cause hallucination more than adding any additional instruction text did.

**What it means:** When an LLM sees `error_type: assertion`, it is constrained to reason about assertion failures. When it sees unstructured text, it fills context gaps with assumptions — and those assumptions are often wrong. Structured context is a form of prompt engineering that operates at the data layer, before any instruction text is written.

**Practical implication:** Label your input data explicitly. The model's first reasoning step is understanding what it is looking at — make that step trivially easy and the rest of the reasoning improves.

---

## 5. Vertical slice development eliminates integration lag

**What happened:** Rather than building all tests first, then all parsing, then all AI analysis, we built one test → one parser → one AI call → one report in sequence. The pipeline was end-to-end functional before any individual layer was feature-complete.

**What it means:** When layers are built horizontally across the whole system, integration bugs surface late and are difficult to locate — the failure could be in any layer. When the thinnest vertical path is proven first, integration bugs surface immediately and the blast radius is small.

**Practical implication:** Always identify the thinnest possible end-to-end path through your system and build that first. Expand horizontally only after the vertical path is stable.

---

## 6. Explicit configuration defaults signal copy-paste, not intent

**What happened:** `playwright.config.ts` initially included `headless: true` and `video: 'off'` — both Playwright defaults. These were caught and removed during a code review.

**What it means:** Configuration files are read by engineers trying to understand what is deliberately different about this system. Explicit defaults add noise — they suggest the value was consciously considered, but they don't communicate *why*. Experienced engineers reading the file will question whether those lines represent intentional decisions or were copied from a tutorial.

**Practical implication:** Configuration should read like a list of decisions, not a list of settings. If a line would have the same effect deleted, delete it.

---

## 7. Prompt examples outperform prompt instructions

**What happened:** The initial system prompt used abstract severity guidance: "assess severity based on user-facing impact." The improved version added concrete examples: "critical = checkout broken, medium = assertion mismatch or pricing inconsistency." The examples produced more consistent output than additional instruction text did.

**What it means:** LLMs calibrate better on examples than on abstract rules. A rubric with one concrete example per category outperforms a paragraph of guidance. Longer prompts with vague instructions frequently perform worse than shorter prompts with sharp examples.

**Practical implication:** For classification or rubric tasks, include at least one concrete example per category. Remove instruction text that is redundant with an example — it adds tokens without adding signal.

---

## 8. Omissions deserve the same documentation as decisions

**What happened:** Several features were considered and explicitly rejected during development: retry logic on AI failures, a CLI framework, a database, HTML output, an agent framework. Documenting *why* each was omitted changed how the project reads — from "incomplete" to "deliberately scoped."

**What it means:** Engineering maturity is demonstrated as much by what you choose not to build as by what you build. In the absence of documentation, omissions look like gaps. Documented omissions look like judgment.

**Practical implication:** For every significant feature you decide not to implement, write one sentence explaining the reasoning. Collect those sentences somewhere visible — a README section, an ADR log, or a comment in the relevant code.
