import json
from decimal import Decimal
from html.parser import HTMLParser
from pathlib import Path
import shutil
import subprocess
import unittest

from unscored import audit, load_results, load_suite
from unscored.report import render_html


class Document(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.tags = []
        self.scripts = []
        self.current_script = None
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self.tags.append((tag, attrs))
        if tag == 'script':
            self.current_script = {'attrs': attrs, 'text': ''}
            self.scripts.append(self.current_script)

    def handle_endtag(self, tag):
        if tag == 'script':
            self.current_script = None

    def handle_data(self, data):
        if self.current_script is not None:
            self.current_script['text'] += data


class ReportTests(unittest.TestCase):
    def demo_report(self):
        examples = Path(__file__).resolve().parents[1] / 'src/unscored/examples'
        return audit(load_suite(examples / 'suite.json'), load_results(examples / 'results.jsonl'))

    def test_standalone_document_preserves_exact_report(self):
        report = self.demo_report()
        html = render_html(report)
        document = Document(html)
        self.assertTrue(html.lower().startswith('<!doctype html>'))
        payload = next(s for s in document.scripts if s['attrs'].get('id') == 'report-data')
        self.assertEqual(payload['attrs']['type'], 'application/json')
        self.assertEqual(json.loads(payload['text']), report)
        self.assertEqual(report['systems'][0]['lower'], '5/8')
        self.assertEqual(report['systems'][0]['upper'], '23/24')
        self.assertEqual(len(document.scripts), 2)
        self.assertNotIn('__REPORT_JSON__', html)

    def test_hostile_identifiers_cannot_escape_payload(self):
        hostile = '</script><img src=x onerror=alert(1)>&\u2028\u2029 __REPORT_JSON__'
        report = audit({
            'version': 1, 'name': hostile, 'systems': [hostile, '__proto__'],
            'cases': [{'id': hostile, 'group': hostile}],
        }, [])
        html = render_html(report)
        document = Document(html)
        payload = next(s for s in document.scripts if s['attrs'].get('id') == 'report-data')
        self.assertEqual(json.loads(payload['text']), report)
        self.assertFalse(any(tag == 'img' for tag, _ in document.tags))
        for unsafe in '<>&\u2028\u2029':
            self.assertNotIn(unsafe, payload['text'])
        self.assertEqual(len(document.scripts), 2)
        self.assertNotIn('.innerHTML', html)
        self.assertNotIn('insertAdjacentHTML', html)
        self.assertIn('.textContent', html)

    def test_no_external_resources_or_requests(self):
        html = render_html(self.demo_report())
        for _, attrs in Document(html).tags:
            for key in ('src', 'href', 'action'):
                if key in attrs:
                    self.assertTrue(attrs[key].startswith('#'), attrs[key])
        for external in ('@import', 'fetch(', 'XMLHttpRequest', 'https://', 'http://'):
            self.assertNotIn(external, html)

    def test_native_controls_have_labels_and_states(self):
        html = render_html(self.demo_report())
        document = Document(html)
        by_id = {attrs['id']: (tag, attrs) for tag, attrs in document.tags if 'id' in attrs}
        for control in ('evidence', 'favor-a', 'favor-b', 'download-json', 'reset-filters',
                        'cases-prev', 'cases-next', 'queue-prev', 'queue-next'):
            self.assertEqual(by_id[control][0], 'button')
        for control in ('evidence', 'favor-a', 'favor-b'):
            self.assertIn('aria-pressed', by_id[control][1])
        self.assertEqual(by_id['case-search'][0], 'input')
        self.assertEqual(by_id['status-filter'][0], 'select')
        labels = {attrs.get('for') for tag, attrs in document.tags if tag == 'label'}
        self.assertTrue({'case-search', 'status-filter'} <= labels)
        self.assertEqual(by_id['scenario-banner'][1]['role'], 'status')
        self.assertIn('Hypothetical completion', html)
        self.assertIn('not measured', html)
        self.assertIn('prefers-reduced-motion', html)
        self.assertIn('BigInt', html)

    def test_large_exact_fraction_is_not_converted_to_a_float(self):
        tiny = Decimal('1.' + '1' * 99 + 'e-100')
        report = audit({
            'version': 1, 'name': 'Tiny contribution', 'systems': ['A', 'B'],
            'cases': [{'id': 'small', 'weight': tiny}, {'id': 'large', 'weight': Decimal('1e100')}],
        }, [{'system': 'A', 'case_id': 'small', 'status': 'scored', 'score': tiny}])
        self.assertGreater(len(report['systems'][0]['lower'].split('/')[1]), 308)
        html = render_html(report)
        payload = next(s for s in Document(html).scripts if s['attrs'].get('id') == 'report-data')
        self.assertEqual(json.loads(payload['text']), report)
        self.assertNotIn('Infinity', payload['text'])

    @unittest.skipUnless(shutil.which('node'), 'Optional JavaScript interaction check requires Node')
    def test_script_witnesses_preserve_evidence_filter_and_paginate(self):
        report = self.demo_report()
        script = next(s['text'] for s in Document(render_html(report)).scripts
                      if s['attrs'].get('type') != 'application/json')
        # A small DOM stand-in checks the shipped script without a browser dependency.
        harness = r'''
const assert = require('node:assert/strict');
class Element {
  constructor(tag) {
    this.tag = tag; this.children = []; this.dataset = {}; this.style = {};
    this.listeners = {}; this.attrs = {}; this.textContent = ''; this.value = '';
    this.hidden = false; this.classList = {toggle(){}};
  }
  append(...children) { this.children.push(...children); }
  replaceChildren(...children) { this.children = children; }
  setAttribute(key, value) { this.attrs[key] = value; }
  addEventListener(event, fn) { this.listeners[event] = fn; }
}
const elements = new Map();
const document = {
  getElementById(id) { if (!elements.has(id)) elements.set(id, new Element(id)); return elements.get(id); },
  createElement(tag) { return new Element(tag); }
};
const text = el => el.textContent + el.children.map(text).join(' ');
'''
        harness += "\ndocument.getElementById('report-data').textContent = " + json.dumps(json.dumps(report)) + ';\n'
        checks = r'''
  assert.equal(percent('5/8', 'down'), '62.5%');
  assert.equal(percent('23/24', 'up'), '95.9%');
  assert.equal(percent('5/6'), '83.3%');
  assert.equal(position('1/' + '1' + '0'.repeat(500)), 0);
  assert.equal(percent('1/' + '1' + '0'.repeat(500), 'up'), '0.1%');
  assert.equal($('case-rows').children.length, 24);
  const baseline = text($('case-rows'));
  selectScenario(0);
  assert.match(text($('scenario-result')), /Atlas wins/);
  assert.match(text($('case-rows')), /Imputed/);
  const observed = report.cases.find(c => c.a.status === 'scored');
  assert.equal(scoreCell(observed, 'a', a).children[0].textContent, observed.a.score);
  assert.equal($('favor-a').attrs['aria-pressed'], 'true');
  selectScenario(1);
  assert.match(text($('scenario-result')), /Beacon wins/);
  selectScenario(null);
  assert.equal(text($('case-rows')), baseline);
  assert.equal($('scenario-banner').hidden, true);
  $('case-search').value = 'long-context'; $('status-filter').value = 'unresolved';
  filterRows();
  assert.equal($('case-rows').children.length, 8);
  assert.equal($('queue-rows').children.length, 8);
  $('reset-filters').listeners.click();
  assert.equal($('case-rows').children.length, 24);
  filteredCases = Array(51).fill(report.cases[0]); renderCases();
  assert.equal($('case-rows').children.length, 50);
  $('cases-next').listeners.click();
  assert.equal($('case-rows').children.length, 1);
  assert.equal($('cases-next').disabled, true);
  filteredQueue = Array(51).fill(report.rerun_plan[0]); renderQueue();
  assert.equal($('queue-rows').children.length, 50);
  $('queue-next').listeners.click();
  assert.equal($('queue-rows').children.length, 1);
  assert.equal($('queue-next').disabled, true);
'''
        script = script.replace('} catch (error)', checks + '\n} catch (error)')
        script = script.replace("document.getElementById('load-error').hidden = false;", 'throw error;')
        result = subprocess.run(['node'], input=harness + script, text=True, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
