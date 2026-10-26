# Verification record

Date: 2026-10-26. This record separates synthetic software checks from real-world adoption. No live model/provider calls or production evaluations were performed.

## Engine and parser

The initial engine/parser tests failed before the implementation existed. Unicode and oversized-number regression tests also failed before their fixes. The final engine/parser run passed 32 tests on Python 3.11.15/macOS.

The committed exhaustive oracle enumerates 256 observation configurations and 1,296 binary completions, independently calculates full scores, and checks bound endpoints, exact verdicts, and preservation of observed scores in each witness. A fresh specification reviewer additionally checked 250 randomized weighted suites against exhaustive completions and confirmed each unresolved measurement's interval-width reduction.

The parser tests include duplicate JSON keys, duplicate system/case pairs, unknown fields, NaN/Infinity, invalid UTF-8, lone surrogates, CRLF/blank lines, deep nesting, numeric resource limits and the 32 MiB input cap. Independent quality review found one valid-decimal representation being rejected; a failing regression was added, the redundant raw-digit check removed, and the fix re-reviewed.

## Measured synthetic scale

One local engine-only run: 10,000 cases, 18,000 result records, 2,000 unresolved cells, approximately **0.2144 seconds** on Python 3.11.15/macOS. This is a single illustrative timing, not a controlled benchmark. It excludes parsing, report rendering, disk I/O and browser work. Maximum-size end-to-end throughput has not been measured. A reviewer separately exercised the report JavaScript with 100,000 all-missing cases (54.3 MiB serialized JSON) in a Node DOM stand-in; parsing, scenarios and filtering completed without an error. This is not browser memory or latency evidence.

## Independent CLI/package review

A fresh reviewer checked CLI gate exit codes, validation before output, malformed input, input preservation, existing/broken-symlink output refusal and CSV formula escaping. The reviewer built a wheel from a temporary source copy with `pip wheel --no-deps --no-build-isolation`, installed it with `pip install --no-index` into a new virtual environment, then ran the installed `unscored demo` and `python -m unscored --version` outside the checkout with `PYTHONPATH` removed. All three report artifacts were produced; the wheel included its template and examples. Environment: Python 3.11.15, setuptools 82.0.1, macOS.

Known narrow publication limit: a POSIX rename can replace an empty destination directory created concurrently between the final existence check and rename. It does not overwrite a nonempty directory's files. The design and code document this limit; use a unique output path per concurrent invocation.

## Integrated tests and browser checks

The final local suite passed **51 tests** on Python 3.11.15, including the shipped JavaScript exercised with Node. The first interactive browser pass found a mismatch between displayed system labels and witness lookup keys; the fix is covered by the JavaScript regression test.

The report was exercised in the Codex in-app browser at 1280 × 720 and 390 × 844. Both hypothetical scenarios, evidence reset, case/group search, status filtering, empty results, reset, exact-arithmetic disclosure, pagination (61 cases / 122 unresolved cells), keyboard activation and tab order were checked. Downloaded JSON matched the original artifact exactly. All-missing, exact-tie, strict-winner, hostile text and large-rational fixtures rendered without a load error. No horizontal page overflow remained at the checked widths. A reviewer found long-number/name wrapping gaps; they were reproduced in the browser and fixed before release.

Fresh browser console checks contained no warnings or errors. Source/template tests verify there are no external resources or request APIs; the report also carries a restrictive resource policy. A network interception trace and screen-reader session were not performed. Browser checks used one browser engine, not a cross-browser compatibility matrix.

Independent read-only reviews covered the engine specification, engine quality, CLI/package integration and report specification/quality. Material findings were fixed and verified. The synthetic report and screenshot in this repository are reproducible release examples, not results from a real model evaluation.

## Claims deliberately not made

- No statistical confidence, generalization, judge accuracy or model-quality validation.
- No reproduction claim for the upstream issues linked in the research.
- No real-team adoption or time-saving claim.
- No claim that the product or its established mathematical method is globally unique.
- No package-registry release unless a release is explicitly recorded later.
