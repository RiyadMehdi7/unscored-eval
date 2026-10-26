# Unscored Implementation Plan

> For agentic workers: use test-driven development and a fresh final code review. The human has delegated idea choice and implementation; proceed without intermediate approval gates.

**Goal:** Turn incomplete two-system evaluation exports into exact, inspectable decision bounds.

**Architecture:** A pure Python engine owns validation and arithmetic. A thin CLI writes portable artifacts. A standalone HTML template displays the same precomputed report.

**Tech stack:** Python standard library, setuptools for packaging, vanilla HTML/CSS/JavaScript, unittest; Playwright only for development verification.

## Scope and ownership

- Engine worker: `src/unscored/core.py`, `src/unscored/io.py`, `src/unscored/__init__.py`, `tests/test_core.py`, `tests/test_io.py`.
- Report worker (after engine): `src/unscored/report.py`, `src/unscored/report.html`, `tests/test_report.py`.
- Coordinator: CLI and tests, packaging, examples, documentation, CI, release artifact, browser checks and integration.
- Fresh reviewers: read-only specification review followed by code-quality review. Fix actionable findings and rerun relevant checks before release.

## Checklist

- [x] Research competing projects and concrete failure reports; compare alternatives.
- [x] Define the finite-set contract, claims, scope, trust boundaries and tests in DESIGN.md.
- [x] Write engine tests first; verify failure; implement exact bounds, witnesses and measurement queue; exhaustively compare against enumerated binary completions.
- [x] Write parser tests first; verify failure; implement strict bounded JSON/JSONL input, including duplicate JSON keys and numeric limits.
- [x] Write report tests first; verify failure; implement standalone escaped HTML with evidence/scenario switch and responsive case table.
- [x] Write CLI integration tests first; verify failure; implement `audit`, `demo`, `--out`, and `--require-winner`; verify errors never overwrite existing outputs or inputs.
- [x] Add MIT license, README with exact commands and boundaries, contributing guidance, packaged synthetic examples, and CI for Python 3.10–3.13.
- [x] Install a built wheel in an isolated environment, run demo and full tests, independently replay witnesses, and benchmark a larger synthetic input.
- [x] Browser-check desktop/mobile, each control and reset, keyboard interaction, no network requests, hostile text, and no horizontal overflow; save a screenshot.
- [x] Fresh spec review, then code-quality review; resolve material findings.
- [x] Commit reviewed source, publish a new public repository if the authorized account is available, and verify remote state/CI; never publish unrelated workspace files.

## Verification commands and expected outcomes

`PYTHONPATH=src python3 -m unittest discover -s tests -v`: all tests pass; exhaustive oracle agrees with exact extrema.

`python3 -m unscored demo --out /new/path`: terminal says comparison is inconclusive; all three artifact files exist.

`python3 -m unscored audit src/unscored/examples/suite.json src/unscored/examples/results.jsonl --require-winner Atlas`: exits 1 for the bundled unresolved comparison.

The JSON contract, arithmetic and error cases are fully specified in DESIGN.md. Do not add provider clients, a service layer, or a statistical estimator. Public claims must distinguish tested synthetic behavior, inspected prior art, and unverified real-world adoption.
