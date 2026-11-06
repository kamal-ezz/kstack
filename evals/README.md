# Behavioral skill evaluations

This suite tests what Codex does with the skills, not whether their wording matches
an expected string. Each run starts in a fresh Docker container with a small
fixture project and no previous conversation. The initial suite covers:

- An ambiguous Snake brief: scope/platform decisions before implementation.
- A basket bug: reproduction, a correct fix, readable code, and verification.
- A substantial Snake-session refactor: readable state transitions while preserving
  movement, queued turns, pause, restart, timing, collisions, and win behavior.
- Reviews of buggy and clean code: useful findings without edits or false positives.
- A real Snake UI review: browser evidence for focus-sensitive keyboard behavior.
- A commit with unrelated staged work: commit scope and index preservation.
- A PR-text request: drafting without committing or publishing.
- An explanation request: correct, proportional explanation without ceremony or changes.
- A mastery request from a tired user: a reusable mental model, the hard step, and edge cases, still easy to follow without unrequested quizzing.
- A multi-file architecture and turn-queue walkthrough: tracing input flow across files and explaining why queued state matters.
- A crash explanation across modules: connecting a symptom to a confirmed code path while separating unconfirmed runtime causes.
- An existing frontend: preserve its identity, improve layout, and inspect screenshots.

## Requirements

Python 3.11+, Git, and a working Docker daemon. The image contains Codex CLI
0.165.0, Node, Python, Git, and Chromium. The base image is pinned by digest;
run manifests also record the built image ID and actual CLI version. No Python
packages or API keys are needed for harness tests.

## Build and check the environment

From the repository root:

```sh
python3 evals/run.py list
python3 evals/run.py build
python3 -B -m unittest discover -s tests -v
SKILL_EVAL_DOCKER=1 python3 -B -m unittest discover -s tests -v
```

The Docker tests exercise fixture setup, artifact capture, a checker that rejects
the seeded bug and accepts its fix, preservation of staged Git changes, Chromium screenshots, and a refactor checker
that rejects growth, turn-queue, and timing regressions. They do not call a model or consume Codex usage.

## Run Codex

Choose an exact model you have access to. For example, to use `gpt-6.1-sol`:

```sh
python3 evals/run.py run --case snake-brief --model gpt-6.1-sol
python3 evals/run.py run --case ramsay-browser-review --model gpt-6.1-sol --repeat 2 --timeout 300
python3 evals/run.py run --case hamilton-bug --model gpt-6.1-sol --repeat 3
python3 evals/run.py run --case all --model gpt-6.1-sol
```

Live runs consume your Codex allowance. They reuse only the file-based credential
at `$CODEX_HOME/auth.json` (default `~/.codex/auth.json`), copied into disposable
container memory. Use `--auth-file /path/to/auth.json` for a dedicated test login.
Keyring-only authentication is not supported; no host keyring or home directory
is mounted. Credentials are not retained in results or synced back to the host.
Treat the fixtures as trusted code: the agent necessarily has its own Codex
credential during a run, and Docker is not a defense against credential abuse by
malicious tasks. Existing known credential values are redacted from captured files.

Each run has a 180-second limit (`--timeout` overrides it), two CPUs, 2GB RAM, a
process limit, a read-only root filesystem, and disposable bounded workspaces.
No Docker socket, project bind mount, GitHub login, cloud credentials, or host
configuration is provided. Model runs have network access for Codex; independent
checkers and screenshot capture run in fresh containers with no network or auth.
Containers are removed on success, failure, timeout, or Ctrl+C. A host crash may
leave a `skill-eval-*` container; inspect `docker ps -a --filter name=skill-eval-`
and remove that container explicitly if needed.

## Skill activation and comparison

Default runs install a frozen copy of the entire collection and use a natural
prompt, testing implicit skill selection. `--invocation explicit` prefixes the
prompt with the intended `$skill` names to test adherence separately from routing.
Every prompt includes the same factual runtime manifest: detected tools and
versions, working directory, and configured integrations. It contains no product
requirements or evaluation expectations. The manifest is probed from the image,
saved in the run, and is identical across the control and skill conditions.
The prompt never includes the grading rubric, hidden checks, or desired findings.

The baseline omits this collection; Codex built-in skills remain available in
both conditions. Use the same model, effort, image, scenario, and sample count:

```sh
python3 evals/run.py run --case hamilton-bug --model gpt-6.1-sol --repeat 3 --baseline
python3 evals/run.py run --case hamilton-bug --model gpt-6.1-sol --repeat 3
python3 evals/run.py compare .eval-runs/BASELINE_BATCH .eval-runs/SKILLS_BATCH
```

Use `--skills-root /path/to/another/collection` to evaluate a saved revision. Every
run captures exact skill files and hashes, prompt, scenario, model, reasoning
effort (default `high`), CLI version, and image ID. Do not change model/settings
between a baseline and candidate and attribute the difference only to the skill.
The comparison command rejects differences in those settings, scenario, timeout,
runtime manifest, or evaluator code hashes.
Repeat trials: one stochastic response is evidence, not a reliable success rate.

This suite tests the installed Codex CLI, not all T3-specific tools and injected
instructions. Passing here does not establish identical behavior in T3. The
Snake case evaluates the first response; it does not simulate a user's answers
or prove the game would be built correctly after clarification.

## Evidence and grading

Results go under `.eval-runs/BATCH/CASE-N/` (Git-ignored, private batch permissions):

- `manifest.json` and `inputs/`: exact scenario, prompt, runtime capabilities,
  fixtures, skill snapshot, and evaluator code hashes.
- `events.jsonl`, `stderr.log`, `response.md`: tool activity and agent responses.
- `before.json`, `after.json`, `workspace/`: Git state, file hashes, and final files.
- `viewport-375.png`, `viewport-1280.png`: frontend captures when requested by a case.
- `result.json`, `report.md`: automatic checks and the human rubric.

Automatic checks cover behavioral outcomes and boundaries. For example, the
independent basket checks test quantities and empty baskets in a separate
container; they do not trust the agent's tests. The session-refactor checker compares
observable behavior with the original module, including edge cases and 1,200
seeded actions. It checks in-place mutation, return values, state, and errors;
readability remains a separate review judgment. Readability, evidence quality,
review accuracy, and visual quality require inspection. Screenshots alone do
not prove that interactions work, nor does a passing test prove readable code.

An evaluation remains `needs-review` until its rubric has been assessed. Open the
report, inspect the trace and artifacts, then record each judgment with evidence:

```sh
python3 evals/run.py review .eval-runs/BATCH/hamilton-bug-1 \
  --criterion readability --verdict pass \
  --evidence 'workspace/basket.py: conventional formatting, explicit quantity multiplication, no unnecessary abstraction.'
```

Use `fail` for a demonstrated violation and `not-applicable` only with a reason.
An automatic failure or failed rubric criterion fails the case. Authentication,
container, capture, and timeout failures are `infrastructure-error`, not skill
failures. A zero process exit code never makes a behavioral evaluation pass.

## Add a case

Add an entry to `cases.json` with a unique ID, natural prompt, intended skill
names, initial `files` (or a `fixture` folder under `evals/fixtures/`), optional
working-tree `changes` and `staged` paths, check
IDs, and an evidence-oriented rubric. Fixtures contain only what a real user
would provide. Put hidden assertions in the host runner, never in the agent's
workspace or prompt. Add positive and negative tests for a new automatic checker.
The checks here are intentionally small; add scenarios from demonstrated failures
rather than making a single oversized task or grading superficial wording.

The runtime follows OpenAI's [non-interactive CLI guidance](https://learn.chatgpt.com/docs/non-interactive-mode)
and [file-based authentication guidance](https://learn.chatgpt.com/docs/auth).

## Browser-review case

`ramsay-browser-review` snapshots the existing Pocket Arcade Snake project and
uses only the natural request "review the code". Chromium and Node are available
in the factual runtime manifest, with no preconfigured browser integration. This
tests whether Ramsay independently uses available CLI browser automation; it does
not reproduce T3's tool surface. The expected finding and rubric stay off the
agent's filesystem. Review the trace for successful browser input and observed
state, not just an intent to test or a screenshot.

`checks/snake_browser.mjs` is an independent preflight, never exposed to the agent.
It uses Chromium DevTools pointer and keyboard input, verifies trusted events,
and checks both page-focus pausing and native speed-button reactivation. Its
Docker test includes a negative control that removes the focus guard; that probe
mutation is not a recommended product fix. A review can correctly recognize the
native-button accessibility tradeoff without recommending a global Space override.
