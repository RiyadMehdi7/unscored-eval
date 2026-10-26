# Contributing

Keep Unscored small: a finite-set audit that can be inspected without an AI model or a running service.

1. Create a Python 3.10+ virtual environment and install the checkout with `python -m pip install -e .`.
2. Run `python -m unittest discover -s tests -v`.
3. For a bug, first add a small failing example. Prefer synthetic scores and IDs; never attach private prompts, transcripts or credentials.
4. Preserve the distinction between observed results and hypothetical completions. A display change must not introduce a second decision engine with floating-point comparisons.
5. Explain the behavior change and the test that demonstrates it. Input/report format changes need a documented migration or version change.

The most useful early contributions are real export examples, clearer error messages, independent arithmetic checks, and report accessibility fixes. A harness adapter should follow a demonstrated user need and an explicit attempt/metric policy.

To report an ordinary bug, include the version, Python version, sanitized suite/results and exact command. For a security issue, use the repository's private vulnerability-reporting channel if available; otherwise report only that a private report is needed, without publishing exploit details or sensitive input.
