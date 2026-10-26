"""Local file interface. All evaluation arithmetic lives in core.audit."""

import argparse
import csv
from fractions import Fraction
from importlib.resources import files
import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

from . import InputError, __version__, audit, load_results, load_suite


def _percent(value):
    return 'not measured' if value is None else f'{float(Fraction(value)) * 100:.2f}%'


def _bound_percent(value, upper=False):
    scaled = Fraction(value) * 10000
    units = -(-scaled.numerator // scaled.denominator) if upper else scaled.numerator // scaled.denominator
    return f'{units / 100:.2f}%'


def _csv_text(value):
    # Spreadsheet apps evaluate formula-like identifiers even inside quoted CSV cells.
    return "'" + value if value.startswith(('=', '+', '-', '@')) else value


def _write_bundle(report, destination):
    from .report import render_html

    out = Path(destination).absolute()
    if os.path.lexists(out):
        raise InputError(f'output already exists: {out}; choose a new directory')
    html = render_html(report)
    out.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix='.unscored-', dir=out.parent) as temporary:
        bundle = Path(temporary) / 'bundle'
        bundle.mkdir()
        (bundle / 'report.json').write_text(
            json.dumps(report, ensure_ascii=True, indent=2) + '\n', encoding='utf-8',
        )
        (bundle / 'report.html').write_text(html, encoding='utf-8')
        with (bundle / 'rerun.csv').open('w', encoding='utf-8', newline='') as target:
            writer = csv.writer(target)
            writer.writerow(['system', 'case_id', 'status', 'weight', 'interval_reduction'])
            for row in report['rerun_plan']:
                writer.writerow([_csv_text(row['system']), _csv_text(row['case_id']),
                                 row['status'], row['weight'], row['interval_reduction']])
        if os.path.lexists(out):
            raise InputError(f'output already exists: {out}; choose a new directory')
        # shortcut: rename can replace a concurrently created empty directory; use OS no-replace support for strict concurrent publication.
        bundle.rename(out)
    return out


def _print_report(report):
    summary = report['summary']
    print(f"Unscored {__version__} | {report['name']}")
    if summary['winner'] is not None:
        print(f"CERTIFIED ON THIS SUITE: {summary['winner']}")
    elif summary['verdict'] == 'tie':
        print('EXACT TIE ON THIS SUITE')
    else:
        print('INCONCLUSIVE: unresolved results can prevent a strict winner.')
    print(f"{summary['case_count']} intended cases; total weight {summary['total_weight']}")
    for system in report['systems']:
        possible = (f"{_percent(system['lower'])} (exact {system['lower']})"
                    if system['lower'] == system['upper'] else
                    f"[{_bound_percent(system['lower'])}, {_bound_percent(system['upper'], upper=True)}]")
        print(f"  {system['id']}: observed-only {_percent(system['observed_mean'])}; "
              f"possible {possible}; "
              f"weighted coverage {_percent(system['coverage'])}")
        print(f"    {system['scored']} scored, {system['missing']} missing, "
              f"{system['error']} error, {system['unscored']} unscored")
    margin = summary['margin']
    print(f"Exact margin ({report['system_ids'][0]} minus {report['system_ids'][1]}): "
          f"[{margin['lower']}, {margin['upper']}]")
    print('Completion bounds, not confidence intervals or predictions.')


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog='unscored', description='Can missing evaluation results change your winner?',
    )
    parser.add_argument('--version', action='version', version=f'Unscored {__version__}')
    commands = parser.add_subparsers(dest='command', required=True)
    check = commands.add_parser('audit', help='compare two systems against a declared case set')
    check.add_argument('suite', type=Path, help='suite JSON with two systems and intended cases')
    check.add_argument('results', type=Path, help='one canonical result per system/case, as JSONL')
    check.add_argument('--out', type=Path, help='new directory for HTML, JSON and measurement CSV')
    check.add_argument('--require-winner', metavar='SYSTEM', help='exit 1 unless this system is certified')
    demo = commands.add_parser('demo', help='audit a bundled synthetic incomplete evaluation')
    demo.add_argument('--out', type=Path, required=True, help='new directory for demo reports')
    args = parser.parse_args(argv)
    try:
        if args.command == 'demo':
            examples = files('unscored').joinpath('examples')
            suite = load_suite(examples.joinpath('suite.json'))
            results = load_results(examples.joinpath('results.jsonl'))
            required = None
        else:
            suite, results = load_suite(args.suite), load_results(args.results)
            required = args.require_winner
        report = audit(suite, results)
        if required is not None and required not in report['system_ids']:
            raise InputError('--require-winner must name one of the two declared systems')
        out = _write_bundle(report, args.out) if args.out is not None else None
        _print_report(report)
        if out is not None:
            print(f'Report: {out / "report.html"}')
        if required is not None and report['summary']['winner'] != required:
            print(f'Gate failed: a strict win for {required} is not established.')
            return 1
        return 0
    except (InputError, OSError, UnicodeError) as error:
        print(f'unscored: {error}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
