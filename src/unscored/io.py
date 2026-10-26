"""Bounded UTF-8 JSON/JSONL input with exact, finite decimal numbers."""

import json
from decimal import Decimal, InvalidOperation

from .core import InputError, MAX_DECIMAL_DIGITS, _number, _validate_result, _validate_suite


MAX_FILE_BYTES = 32 * 1024 * 1024
# Includes sign, decimal point, and exponent; blocks padded numeric encodings.
MAX_NUMBER_TOKEN_LENGTH = 128


def _read(path, context):
    try:
        with open(path, "rb") as handle:
            data = handle.read(MAX_FILE_BYTES + 1)
    except (OSError, ValueError, TypeError) as error:
        raise InputError(f"cannot read {context} file: {type(error).__name__}") from error
    if len(data) > MAX_FILE_BYTES:
        raise InputError(f"{context} file exceeds the 32 MiB limit")
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise InputError(f"{context} file must be UTF-8") from error


def _pairs(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise InputError("duplicate JSON object key")
        value[key] = item
    return value


def _integer(token):
    if len(token.lstrip("-")) > MAX_DECIMAL_DIGITS:
        raise InputError(f"JSON integer exceeds the {MAX_DECIMAL_DIGITS}-digit numeric limit")
    return int(token)


def _decimal(token):
    # Reject large encodings before Decimal allocates their coefficient tuple.
    if len(token) > MAX_NUMBER_TOKEN_LENGTH:
        raise InputError(f"JSON decimal exceeds the {MAX_NUMBER_TOKEN_LENGTH}-character encoding limit")
    try:
        value = Decimal(token)
    except InvalidOperation as error:
        raise InputError("invalid JSON decimal") from error
    _number(value, "JSON decimal")
    return value


def _constant(_token):
    raise InputError("JSON numbers must be finite")


def _parse(text, context):
    try:
        return json.loads(text, object_pairs_hook=_pairs, parse_float=_decimal,
                          parse_int=_integer, parse_constant=_constant)
    except InputError as error:
        raise InputError(f"{context}: {error}") from error
    except json.JSONDecodeError as error:
        raise InputError(f"{context}: invalid JSON at column {error.colno}: {error.msg}") from error
    except RecursionError as error:
        raise InputError(f"{context}: JSON nesting is too deep") from error


def load_suite(path):
    """Read and validate a suite; numeric decimals remain Decimal values."""
    suite = _parse(_read(path, "suite"), "suite")
    _validate_suite(suite)
    return suite


def load_results(path):
    """Read result rows; cross-file case/system references are checked by audit."""
    results = []
    seen = set()
    for line_number, line in enumerate(_read(path, "results").split("\n"), 1):
        if not line.strip():
            continue
        context = f"results line {line_number}"
        row = _parse(line, context)
        system, case_id, _, _ = _validate_result(row, context)
        if (system, case_id) in seen:
            raise InputError(f"{context}: duplicate system/case pair; choose one attempt before export")
        seen.add((system, case_id))
        results.append(row)
    return results
