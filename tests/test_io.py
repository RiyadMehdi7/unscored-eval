import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from unscored import InputError, audit, load_results, load_suite


VALID_SUITE = '{"version":1,"name":"Exact","systems":["A","B"],"cases":[{"id":"x","weight":0.1}]}'
VALID_ROW = '{"system":"A","case_id":"x","status":"scored","score":0.1}'


class ParsingTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "input.json"

    def write(self, content):
        self.path.write_text(content, encoding="utf-8")
        return self.path

    def test_exact_decimals_and_integer_version(self):
        manifest = load_suite(self.write(VALID_SUITE))
        self.assertIs(type(manifest["version"]), int)
        self.assertEqual(manifest["cases"][0]["weight"], Decimal("0.1"))
        rows = load_results(self.write(VALID_ROW))
        self.assertEqual(rows[0]["score"], Decimal("0.1"))
        self.assertEqual(audit(manifest, rows)["systems"][0]["lower"], "1/10")

    def test_decimal_and_scientific_forms_match_at_smallest_exponent(self):
        reports = []
        for token in ["0." + "0" * 99 + "1", "1e-100"]:
            manifest = load_suite(self.write(VALID_SUITE.replace('"weight":0.1', '"weight":' + token)))
            rows = load_results(self.write(VALID_ROW.replace('"score":0.1', '"score":' + token)))
            self.assertEqual(manifest["cases"][0]["weight"], Decimal("1e-100"))
            self.assertEqual(rows[0]["score"], Decimal("1e-100"))
            reports.append(audit(manifest, rows))
        self.assertEqual(reports[0], reports[1])
        self.assertEqual(reports[0]["systems"][0]["lower"], "1/" + str(10**100))

    def test_blank_lines_and_crlf_are_allowed(self):
        rows = load_results(self.write("\n  \n" + VALID_ROW + "\r\n\t\r\n"))
        self.assertEqual(len(rows), 1)
        self.assertEqual(load_results(self.write("\n\t\r\n")), [])

    def test_unicode_line_separator_inside_identifier_is_not_jsonl_separator(self):
        row = VALID_ROW.replace('"A"', '"A\u2028B"')
        self.assertEqual(load_results(self.write(row))[0]["system"], "A\u2028B")

    def test_duplicate_keys_at_every_object_level(self):
        values = [VALID_SUITE.replace('"version":1', '"version":1,"version":1'),
                  VALID_SUITE.replace('"id":"x"', '"id":"x","id":"y"')]
        for content in values:
            with self.subTest(content=content), self.assertRaisesRegex(InputError, "duplicate"):
                load_suite(self.write(content))
        with self.assertRaisesRegex(InputError, "duplicate"):
            load_results(self.write(VALID_ROW.replace('"score":0.1', '"score":0.1,"score":0.2')))

    def test_duplicate_result_pairs(self):
        with self.assertRaisesRegex(InputError, "duplicate"):
            load_results(self.write(VALID_ROW + "\n" + VALID_ROW))

    def test_nonfinite_and_huge_numeric_encodings(self):
        for token in ["NaN", "Infinity", "-Infinity", "1e1000000", "1e-1000000", "1" * 101,
                      "0." + "1" * 101, "1e" + "0" * 1000]:
            with self.subTest(token=token):
                with self.assertRaises(InputError):
                    load_suite(self.write(VALID_SUITE.replace('"weight":0.1', '"weight":' + token)))
                with self.assertRaises(InputError):
                    load_results(self.write(VALID_ROW.replace('"score":0.1', '"score":' + token)))

    def test_malformed_json_suite(self):
        for content in ["", "{", VALID_SUITE + " trailing", "[]", "null", VALID_SUITE.replace('"version":1', '"version":1.0')]:
            with self.subTest(content=content), self.assertRaises(InputError):
                load_suite(self.write(content))

    def test_malformed_jsonl_rows_report_line_number(self):
        for content in ["{", "[]", "null", VALID_ROW + " trailing", '{"system":"A"}']:
            with self.subTest(content=content), self.assertRaisesRegex(InputError, "line 3"):
                load_results(self.write("\n\n" + content))

    def test_unknown_fields_and_invalid_scores_are_rejected_by_loaders(self):
        with self.assertRaises(InputError):
            load_suite(self.write(VALID_SUITE.replace('"name":"Exact"', '"name":"Exact","typo":1')))
        for token in ["true", '"0.1"', "null", "-1", "2"]:
            with self.subTest(token=token), self.assertRaises(InputError):
                load_results(self.write(VALID_ROW.replace('"score":0.1', '"score":' + token)))

    def test_deep_nesting_is_a_helpful_input_error(self):
        with self.assertRaises(InputError):
            load_suite(self.write("[" * 2000 + "0" + "]" * 2000))

    def test_invalid_utf8_and_io_errors(self):
        self.path.write_bytes(b"\xff")
        for loader in [load_suite, load_results]:
            with self.subTest(loader=loader.__name__), self.assertRaises(InputError):
                loader(self.path)
            with self.assertRaises(InputError):
                loader(self.path.parent / "not-present")
            with self.assertRaises(InputError):
                loader(self.path.parent)

    def test_escaped_lone_surrogates_cannot_enter_utf8_reports(self):
        with self.assertRaises(InputError):
            load_suite(self.write(VALID_SUITE.replace('"Exact"', '"\\ud800"')))

    def test_32_mib_file_limit(self):
        from unscored.io import MAX_FILE_BYTES
        self.assertEqual(MAX_FILE_BYTES, 32 * 1024 * 1024)
        with self.path.open("wb") as handle:
            handle.seek(MAX_FILE_BYTES)
            handle.write(b"x")
        for loader in [load_suite, load_results]:
            with self.subTest(loader=loader.__name__), self.assertRaisesRegex(InputError, "32 MiB"):
                loader(self.path)

    def test_errors_do_not_echo_input_bodies(self):
        sensitive = "PRIVATE_CONTENT_" * 100
        with self.assertRaises(InputError) as caught:
            load_results(self.write('{"' + sensitive))
        self.assertNotIn("PRIVATE_CONTENT", str(caught.exception))
        self.assertLess(len(str(caught.exception)), 300)


if __name__ == "__main__":
    unittest.main()
