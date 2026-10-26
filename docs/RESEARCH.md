# Idea selection and prior art

Research date: 2026-10-26. This is a bounded search, not a patent, trademark, or exhaustive novelty investigation. No customer interviews or adoption measurements were performed.

## Decision

Build **Unscored**: an offline two-system evaluation comparator that retains the declared denominator, computes exact completion bounds, exports concrete hypothetical ranking witnesses, and orders unresolved measurements by the uncertainty they remove. The contribution is the small, portable workflow. The underlying bounds are not new mathematics.

The pain has direct public evidence. [EleutherAI/lm-evaluation-harness issue 4062](https://github.com/EleutherAI/lm-evaluation-harness/issues/4062) describes unscorable samples leaving metric denominators. [Inspect Evals release notes](https://github.com/UKGovernmentBEIS/inspect_evals/releases) describe several changes in failure and unscored handling. These are evidence of a failure class; this project does not claim to have reproduced those repositories or measured its prevalence.

## Directions examined

| Direction | Existing work found | Decision |
|---|---|---|
| MCP recording/replay and chaos | [mcp-recorder](https://github.com/devhelmhq/mcp-recorder), [Reprise](https://github.com/itsshreyasbhardwaj-design/reprise), [Agent-Chaos-Monkey](https://github.com/charles2ke/Agent-Chaos-Monkey) | Too much direct overlap. |
| Mutation testing for LLM evaluations | [muteval](https://github.com/AshwinUgale/muteval), [acyclic-eval](https://github.com/shiki-yusuke/acyclic-eval) | Already explicitly addressed. |
| Small SQL disagreement fixtures | [sqleq](https://github.com/datadog-labs/sqleq), [Explaining Wrong Queries Using Small Examples](https://pmc.ncbi.nlm.nih.gov/articles/PMC6705612/), [isitright](https://pypi.org/project/isitright/) | Useful, but strong research and product overlap. |
| Tool-schema compatibility witnesses | [ArgWitness](https://pypi.org/project/argwitness/0.1.0/), [jsoncompat](https://pypi.org/project/jsoncompat/0.5.0/) | Direct overlap. |
| RAG evidence/context audits | [ContextAudit](https://github.com/armanzareian/contextaudit), [rag-trace-auditor](https://github.com/jsdnaasd/rag-trace-auditor) | Crowded and semantic claims risk heuristic overreach. |
| Missing-evaluation decision audit | Adjacent work below | Strongest narrow opportunity: no reruns, interpretable exact output, small integration surface. |

## Closest alternatives and the actual difference

- [evallint](https://github.com/BhagyasriUddandam/evallint) audits datasets for issues such as duplication, class imbalance and discrimination. Unscored reconciles completed results against intended cases and checks the ranking under every allowed missing-result completion. Neither substitutes for the other.
- [BenchLM's missing-benchmark analysis](https://benchlm.ai/blog/posts/missing-benchmark-problem) documents selective-reporting problems and describes its later uncertainty-aware leaderboard method. Unscored uses a fixed user-declared finite case set and bounds, without estimating unobserved capability or combining public benchmark scales.
- [Efficient Evaluation of LLM Performance with Statistical Guarantees](https://github.com/skbwu/efficiently-evaluating-llms) provides research code for efficient statistical evaluation. Unscored does not fit a model or require a sampling/missingness model. Its intervals are deterministic completion bounds, not statistical confidence intervals.
- [smevals](https://github.com/prime-radiant-inc/smevals) already reports failure counts and supports repeated evaluations. Unscored consumes exports rather than running models, and produces hypothetical counterexamples to an otherwise unsupported ranking.

Bounds for bounded outcomes with missing data are established partial-identification methodology. See [Manski, Econometrics for Decision Making (2021), section 4.2.1](https://economics.yale.edu/sites/default/files/econometrica_-_2021_-_manski_-_econometrics_for_decision_making_building_foundations_sketched_by_haavelmo_and_wald.pdf). Our finite weighted sum follows directly by placing each unresolved score at 0 or 1. We do not claim to invent this method.

## Why this one

The tool can produce useful evidence before asking a team to adopt a new framework: two local files produce a readable report, an explicit adverse scenario, and a measurement queue. It can also be independently tested by enumerating every completion of small examples. Its value is falsifiable: if all intended results are complete, bounds collapse; if missing data cannot overturn the margin, it says so; if they can, it shows how.

The search did not identify a directly matching standalone workflow across the sources inspected. That supports building a differentiated alpha, not claiming global uniqueness. A simple spreadsheet can reproduce the basic bounds; the reason to use the package is validated reconciliation, exact comparisons, CI integration, and inspectable artifacts.

## Next validation after release

Ask maintainers with incomplete evaluation exports to attempt the two-file workflow. Record time to first correct report, interpretation errors, and whether the report changes a rerun or selection decision. A small number of successful real workflows would establish usefulness; stars and synthetic examples alone do not. No outreach has been sent.
