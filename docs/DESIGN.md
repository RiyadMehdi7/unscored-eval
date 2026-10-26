# Unscored: design and product brief

Research and design date: 2026-10-26. Status: implementation specification.

## Job and evidence

When an AI engineer compares two systems after an interrupted or partially graded evaluation, they need to know whether unresolved cases could reverse the ranking, so they do not select a model on a misleading denominator. Today's workaround is to inspect logs, join case IDs by hand, and decide whether to discard failures or score them as zero. Public evidence of denominator defects and nearby tools is recorded in [RESEARCH.md](RESEARCH.md). Frequency and willingness to adopt this tool remain unknown; no user interviews have been conducted.

The observable outcome is a reproducible comparison on a declared finite case set: either a strict winner under every allowed completion, an exact tie, or an inconclusive comparison with hypothetical endpoint completions. The leading usability signal is whether an engineer can produce and understand that report using an existing score export without rerunning a model.

## Chosen boundary

A dependency-free Python 3.10+ CLI and library. Exactly two named systems, the same intended cases and positive case weights, one higher-is-better score bounded by [0, 1]. Observed scores are fixed. Missing, error and unscored cells remain in the denominator with unknown scores in [0, 1]. Operational failures that a benchmark defines as zero must be supplied explicitly as scored zero by the caller.

No model calls, telemetry, network access, database, hosted service, judge, estimator, automatic retries, universal harness adapters, statistical confidence interval, or novel-statistics claim. Reports include supplied case/system IDs and scores; users control whether those are shareable. No prompt or response text is required.

## Input contract

`suite.json`: `{ "version": 1, "name": "Example", "systems": ["A", "B"], "cases": [{"id": "case-1", "weight": 1, "group": "reasoning"}] }`.

Weights default to 1; group defaults to `all`. Cases must be nonempty. Identifiers are nonempty strings; case IDs and system names are unique. Exactly two systems. Unknown suite/case/result keys are rejected to catch misspellings. JSON object duplicate keys and non-finite numbers are rejected. Version must be integer 1, not boolean.

`results.jsonl`: one JSON object per line: `{ "system": "A", "case_id": "case-1", "status": "scored", "score": 0.75 }`. Status is `scored`, `error`, or `unscored`. Scored rows require a finite numeric score from 0 through 1; booleans and strings are not numbers. Other statuses forbid a score. An absent pair is `missing`. An unknown case/system or duplicate pair is an input error, including duplicate retries; the caller must choose and document its attempt policy before export. Blank lines are ignored.

Numeric decimals are parsed exactly; Python API inputs also accept finite int/float/Decimal, not booleans. Use Fraction internally and serialize exact quantities as rational strings (`1/3`, `1`). Input files are bounded at 32 MiB each; at most 100,000 cases. Names, groups and IDs are at most 200 characters and reject control characters/lone surrogates. Numbers have at most 100 coefficient digits and adjusted decimal exponent in [-100,100]; JSON decimal tokens have at most 128 characters. Deep nesting fails clearly. No input is executed.

## Arithmetic and claims

For total case weight W, observed weighted score S, and unresolved weight U, report [S/W, (S+U)/W]. Observed-only mean S/(W-U) is a clearly labeled diagnostic, null when no score is observed. Weighted coverage is (W-U)/W. Pair margin A-B is [lower_A-upper_B, upper_A-lower_B]. Only a strictly positive lower margin establishes A as winner, only a strictly negative upper margin establishes B; an exactly [0,0] margin is a tie, all others are inconclusive. The certificate concerns this finite set only, not unseen samples or stochastic reruns.

For each favored system, construct an endpoint completion: all its unknown cells become 1, the other system's unknown cells become 0, and every observed value stays fixed. These are explicitly hypothetical, not predictions or recovered observations. Record their exact scores and winner. This supplies a concrete ranking reversal when mathematically possible, and a tie witness when strict reversal is impossible.

The measurement queue contains every unresolved system/case pair, ordered by descending weight then case ID then system ID. Measuring any listed cell shrinks the pair-margin interval width by weight/W regardless of its eventual score. This ordering maximizes width removed for a fixed number of equal-cost measurements. It does not guarantee that the next measurement settles the ranking or optimize unequal runtime costs.

## Engine/report API

`unscored.audit(suite: dict, results: list[dict]) -> dict`; invalid inputs raise `InputError(ValueError)`. `load_suite(path)` and `load_results(path)` perform bounded exact JSON parsing. `render_html(report)` returns a complete UTF-8 HTML document.

Report format:

```json
{
  "schema_version": 1,
  "name": "Example",
  "system_ids": ["A", "B"],
  "summary": {"verdict": "inconclusive", "winner": null, "case_count": 1, "total_weight": "1", "margin": {"lower": "-1", "upper": "1"}},
  "systems": [{"id": "A", "scored": 0, "missing": 1, "error": 0, "unscored": 0, "coverage": "0", "observed_mean": null, "lower": "0", "upper": "1", "scored_weight": "0", "unresolved_weight": "1"}],
  "cases": [{"id": "case-1", "group": "all", "weight": "1", "a": {"status": "missing", "score": null}, "b": {"status": "missing", "score": null}, "uncertainty": "2"}],
  "completion_witnesses": [{"favored": "A", "hypothetical": true, "scores": {"A": "1", "B": "0"}, "margin": "1", "winner": "A", "assignments": [{"system": "A", "case_id": "case-1", "score": 1}, {"system": "B", "case_id": "case-1", "score": 0}]}],
  "rerun_plan": [{"system": "A", "case_id": "case-1", "status": "missing", "weight": "1", "interval_reduction": "1"}]
}
```

The example abbreviates the second system and second witness; real reports always include both. `summary.verdict` is `a_wins`, `b_wins`, `tie`, or `inconclusive`.

## CLI and files

`unscored audit suite.json results.jsonl --out audit` prints a terminal summary and writes `report.json`, `report.html`, `rerun.csv`. Output is optional; refuse an existing output directory, never modify inputs. Stage files in a temporary directory under the destination parent, then rename only on success. Avoid partial or overwritten reports. `--require-winner SYSTEM` returns 1 unless that named system is certified; 0 means successful audit unless that gate was requested; malformed input returns 2. Validate the gate's system name before writing. `unscored demo --out demo` uses bundled synthetic fixtures and the same audit path. `python -m unscored` works.

## Interactive report

A restrained editorial report: cream background, dark ink, teal observed evidence, hatched unresolved ranges, rust for cautions. One clear verdict followed by two score ranges, the coverage comparison, a hypothetical-completion switch, an accessible case table and the measurement queue. All values come from the exact engine report; browser arithmetic is only for rounded display and positioning. Buttons switch between evidence and the two precomputed scenarios, with explicit hypothetical labels. Group/status filters and downloads are optional only if they materially improve the 24-case demo. Use native HTML controls, visible focus, textual labels alongside color, responsive layout, no external fonts/scripts/network. Escape untrusted text and script-embedded JSON. Avoid pretending a rounded endpoint is a proof.

## Validation and risks

Test known denominator inflation, all-missing systems, weighted scores, exact ties, strict boundary ties, fractional decimals, missing vs error, malformed/duplicate/out-of-scope inputs, CLI gates, output preservation, and hostile HTML names. Exhaustively enumerate binary missing outcomes for small suites and compare extrema against the engine. Replaying each constructed witness must match its advertised exact endpoints and preserve observations. Test package install and demo from a clean environment. Browser-check both scenario transitions and reset, downloads if present, keyboard behavior, and mobile/desktop overflow.

Risks in priority order: false certainty from bad arithmetic (exact comparisons + exhaustive oracle), wrong manifest or scoring policy (explicit contract + rejection), confusion between scenarios and measurements (prominent labels), adoption friction (two simple export files), and unknown demand (open issue templates and honest alpha status). Ship only with passing invariant tests and a usable report. The product is differentiated, not proven globally unique; statistical bounds are established prior art.
