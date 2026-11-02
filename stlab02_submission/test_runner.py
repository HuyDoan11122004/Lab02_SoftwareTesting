"""Data-driven EduCommerce tests. Run: python test_runner.py (Python >= 3.10)."""
from __future__ import annotations

import sys
sys.dont_write_bytecode = True
import argparse
import base64
import copy
import csv
import dataclasses
import hashlib
import html
import io
import json
import os
from pathlib import Path
import platform
import random
import re
import shutil
import tempfile
import textwrap
import time
import traceback
import unittest
from collections import Counter
from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from unittest.mock import patch
import pandas as pd

ROOT = Path(__file__).resolve().parent
REPORTS = ROOT / "reports"
LOCAL_TZ = timezone(timedelta(hours=7))
SOURCE_SHA256 = "51a5bd940307df21a67352b69551c041dbbfb542cfb8fe26d29b8d09ae221b03"
DESIGN_SHA256 = "78588938e04be88dc600b6949fc62a2814ff8689daa2cfc131ee31f3cda1df69"
ORDER_SEED = 20261102
COLUMNS = "test_case_id requirement_id condition_id scenario_id title priority precondition fixture_key input_json expected_type expected_json execution_status actual_result error_message evidence_reference".split()
REQUIREMENTS = {"REQ-02", "REQ-03", "REQ-05", "REQ-09", "REQ-10", "REQ-15", "REQ-16"}
CONDITIONS = {"CART-TYPE", "CART-MERGE", "PRI-SUM", "PRI-ZERO", "PRO-ELIGIBLE", "PRO-REJECT", "PRO-INPUT", "SHP-INNER", "SHP-OUTER", "PAY-COD", "PAY-ONLINE", "INV-ENOUGH", "INV-REJECT", "SAFE-DIRECT", "SAFE-CHECKOUT"}
SCENARIOS = {"CART-QUANTITY", "CART-MERGE", "CART-REJECT", "PRI-SUM", "PRI-EMPTY", "PRI-DECIMAL", "PRO-ELIGIBILITY", "PRO-USED", "PRO-QUANTITY", "PRO-CHECKOUT", "PRO-RETRY-AFTER-DECLINE", "SHP-INNER", "SHP-OUTER", "PAY-COLLECT", "PAY-CHECKOUT", "INV-RESERVE", "INV-CHECKOUT", "SAFE-COLLECT", "SAFE-CHECKOUT"}
OPERATIONS = {
    "REQ-02": {"cart_add"}, "REQ-03": {"subtotal"},
    "REQ-05": {"promotion", "cart_promotion", "checkout", "promotion_sequence"},
    "REQ-09": {"shipping"}, "REQ-10": {"payment", "checkout"},
    "REQ-15": {"reserve", "checkout"}, "REQ-16": {"payment", "checkout"},
}
TARGETS = {
    "cart_add": "Cart.add", "subtotal": "Cart.subtotal",
    "promotion": "Promotions.discount", "cart_promotion": "Cart.add → Cart.subtotal → Promotions.discount",
    "shipping": "Shipping.calculate", "payment": "Payments.collect",
    "reserve": "Inventory.reserve", "checkout": "Checkout.place",
    "promotion_sequence": "Checkout.place (declined → approved)",
}
FIXTURES = {
    "empty": [], "one_a": [("A", 1)], "one_b": [("B", 1)],
    "600k": [("A", 3)], "mixed": [("A", 2), ("B", 1), ("C", 1)],
    "decimal": [("A", 3), ("B", 1)], "unauthenticated": [("A", 3)],
    "used": [("A", 3)], "inactive": [],
    "short_b": [("A", 2), ("B", 100)], "short_first": [("B", 100), ("A", 2)],
}


def now():
    return datetime.now(LOCAL_TZ).isoformat(timespec="milliseconds")


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def encode(value):
    """Keep Decimal exact; never convert money to float."""
    if isinstance(value, Decimal):
        return str(value)
    if dataclasses.is_dataclass(value):
        return encode(dataclasses.asdict(value))
    if isinstance(value, dict):
        return {str(k): encode(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [encode(v) for v in value]
    if isinstance(value, set):
        return sorted(encode(v) for v in value)
    return value


def dumps(value):
    return json.dumps(encode(value), ensure_ascii=False, allow_nan=False)


def fixture(key, setup=None):
    """Fresh objects per call; prepare only preconditions, never oracle results."""
    from ecommerce_app import Checkout, Customer, Cart, D
    if key not in FIXTURES:
        raise ValueError(f"UNKNOWN_FIXTURE:{key}")
    app, user = Checkout(), Customer("U_NEW")
    cart = Cart(app.catalog)
    if key == "decimal":
        app.catalog.products["A"].price = D("0.1")
        app.catalog.products["B"].price = D("0.2")
    user.authenticated = key != "unauthenticated"
    if key == "used":
        user.used_codes.add("SAVE10")
    if key == "inactive":
        app.catalog.products["C"].active = False
    for sku, quantity in FIXTURES[key]:
        cart.add(sku, quantity)
    for name, values in (setup or {}).items():
        for sku, value in values.items():
            setattr(app.catalog.products[sku], "price" if name == "prices" else name,
                    D(value) if name == "prices" else value)
    return app, user, cart


def snapshot(app, user, cart):
    return encode({
        "stock": {sku: p.stock for sku, p in app.catalog.products.items()},
        "orders_count": len(app.orders), "orders": list(app.orders.values()),
        "charges": copy.deepcopy(app.payments.charges), "used_codes": user.used_codes,
        "lines": cart.lines, "prices": {sku: p.price for sku, p in app.catalog.products.items()},
        "customer_id": user.customer_id, "authenticated": user.authenticated,
        "by_key": dict(app.by_key), "counter": app.counter,
    })


def dispatch(app, user, cart, data, case_id):
    """Every branch invokes the real application, without monkeypatching it."""
    op = data["operation"]
    if op in {"cart_add", "cart_promotion"}:
        for sku, quantity in data["additions"]:
            cart.add(sku, quantity)
        if op == "cart_add":
            return None
        return app.promotions.discount(data["code"], cart.subtotal(), user)
    if op == "subtotal":
        return cart.subtotal()
    if op == "promotion":
        return app.promotions.discount(data["code"], cart.subtotal(), user)
    if op == "shipping":
        return app.shipping.calculate(Decimal(data["subtotal"]), data["area"])
    if op == "payment":
        return app.payments.collect(Decimal(data["amount"]), data["method"], data["approved"], case_id)
    if op == "reserve":
        return app.inventory.reserve(cart.lines)
    if op == "checkout":
        options = {key: data[key] for key in ("area", "voucher", "method", "approved") if key in data}
        return app.place(user, cart, key=case_id, **options)
    if op == "promotion_sequence":
        events = []
        try:
            result = app.place(user, cart, voucher="SAVE10", method="ONLINE", approved=False,
                               key=case_id + "-decline")
            event = {"return": encode(result)}
        except Exception as error:
            event = {"exception": {"type": type(error).__name__, "message": str(error)}}
        events.append({**event, "state": snapshot(app, user, cart)})
        result = app.place(user, cart, voucher="SAVE10", method="ONLINE", approved=True,
                           key=case_id + "-success")
        events.append({"return": encode(result), "state": snapshot(app, user, cart)})
        return events
    raise ValueError("UNKNOWN_OPERATION")


def strict_json(text):
    def invalid_constant(value):
        raise ValueError(f"NONFINITE_JSON:{value}")
    return json.loads(text, parse_constant=invalid_constant)


def read_cases(path):
    """Pandas primary reader. Preserve malformed records as BLOCKED on fallback."""
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        records = list(csv.reader(stream))
    structural_errors = []
    if records:
        if len(records[0]) != len(set(records[0])):
            structural_errors.append("DUPLICATE_CSV_HEADER")
        for index, record in enumerate(records[1:], 2):
            if len(record) != len(records[0]):
                structural_errors.append(f"CSV_FIELD_COUNT:row={index}:actual={len(record)}:expected={len(records[0])}")
    try:
        frame = pd.read_csv(path, dtype=str, keep_default_na=False, on_bad_lines="error", skip_blank_lines=False)
        if len(frame) != max(0, len(records) - 1):
            raise pd.errors.ParserError("CSV logical record count mismatch")
        return frame.fillna(""), structural_errors
    except (pd.errors.ParserError, pd.errors.EmptyDataError) as error:
        if not records:
            return pd.DataFrame(columns=COLUMNS), [f"CSV_PARSE_ERROR:{error}"]
        headers = records[0]
        # No row discarded; a parse problem invalidates all recovered records.
        rows = [{key: record[i] if i < len(record) else "" for i, key in enumerate(headers)}
                for record in records[1:]]
        return pd.DataFrame(rows, columns=headers), structural_errors + [f"CSV_PARSE_ERROR:{error}"]


def validate_row(row, columns, duplicate_ids):
    reasons = []
    if list(columns) != COLUMNS:
        reasons.append("INVALID_SCHEMA:expected exact ordered columns")
    for key in COLUMNS[:11]:
        if not str(row.get(key, "")).strip():
            reasons.append("MISSING_FIELD:" + key)
    if row.get("test_case_id") in duplicate_ids:
        reasons.append("DUPLICATE_TEST_ID")
    if row.get("execution_status") or row.get("actual_result"):
        reasons.append("SOURCE_EXECUTION_FIELDS_MUST_BE_EMPTY")
    if row.get("fixture_key") not in FIXTURES:
        reasons.append("UNKNOWN_FIXTURE")
    if row.get("requirement_id") not in REQUIREMENTS:
        reasons.append("UNSELECTED_REQUIREMENT")
    if row.get("condition_id") not in {"COND-" + x for x in CONDITIONS}:
        reasons.append("UNKNOWN_CONDITION")
    if row.get("scenario_id") not in {"TS-" + x for x in SCENARIOS}:
        reasons.append("UNKNOWN_SCENARIO")
    if row.get("expected_type") not in {"value", "exception", "state"}:
        reasons.append("UNKNOWN_EXPECTED_TYPE")
    parsed = {}
    for column in ("input_json", "expected_json"):
        try:
            parsed[column] = strict_json(row.get(column, ""))
            if not isinstance(parsed[column], dict):
                reasons.append("JSON_OBJECT_REQUIRED:" + column)
        except (TypeError, ValueError) as error:
            reasons.append(f"INVALID_JSON:{column}:{error}")
    data, expected = parsed.get("input_json"), parsed.get("expected_json")
    if isinstance(data, dict):
        op = data.get("operation")
        if op not in OPERATIONS.get(row.get("requirement_id"), set()):
            reasons.append("UNKNOWN_OPERATION_OR_REQUIREMENT_MAPPING")
        needed = {"cart_add": ["additions"], "cart_promotion": ["additions", "code"],
                  "promotion": ["code"], "shipping": ["subtotal", "area"],
                  "payment": ["amount", "method", "approved"]}.get(op, [])
        for name in needed:
            if name not in data:
                reasons.append("MISSING_OPERATION_INPUT:" + name)
        try:
            for name in ("amount", "subtotal"):
                if name in data and not Decimal(str(data[name])).is_finite():
                    raise ValueError("nonfinite money")
            if "additions" in data:
                if not isinstance(data["additions"], list):
                    raise ValueError("additions must be list")
                for line in data["additions"]:
                    if not isinstance(line, list) or len(line) != 2 or not isinstance(line[0], str):
                        raise ValueError("invalid addition structure")
                    # quantity is intentionally NOT coerced or prevalidated: it is SUT input.
            setup = data.get("setup", {})
            if not isinstance(setup, dict) or set(setup) - {"prices", "stock", "active"}:
                raise ValueError("invalid setup")
            for name, values in setup.items():
                if not isinstance(values, dict) or set(values) - {"A", "B", "C"}:
                    raise ValueError("invalid setup SKU")
                for value in values.values():
                    if name == "prices" and not Decimal(str(value)).is_finite():
                        raise ValueError("invalid setup price")
                    if name == "stock" and (type(value) is not int or value < 0):
                        raise ValueError("invalid setup stock")
                    if name == "active" and type(value) is not bool:
                        raise ValueError("invalid active flag")
        except (TypeError, ValueError, ArithmeticError) as error:
            reasons.append("INVALID_INPUT_STRUCTURE:" + str(error))
    if isinstance(expected, dict):
        if not isinstance(expected.get("state"), dict):
            reasons.append("MISSING_STATE_ORACLE")
        if row.get("expected_type") == "exception":
            ex = expected.get("exception", {})
            if not isinstance(ex, dict) or not all(isinstance(ex.get(k), str) and ex[k] for k in ("type", "message")):
                reasons.append("INVALID_EXCEPTION_ORACLE")
        elif "return" not in expected:
            reasons.append("MISSING_RETURN_ORACLE")
    return reasons, data, expected


def compare(expected, actual, path="actual"):
    """Exact scalars (including bool vs int), exact lists; dicts are projections."""
    errors = []
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return [f"{path}: expected object, actual={actual!r}"]
        for key, value in expected.items():
            if key not in actual:
                errors.append(f"{path}.{key}: missing")
            else:
                errors.extend(compare(value, actual[key], path + "." + key))
    elif isinstance(expected, list):
        if not isinstance(actual, list) or len(expected) != len(actual):
            return [f"{path}: expected {expected!r}, actual={actual!r}"]
        for index, (left, right) in enumerate(zip(expected, actual)):
            errors.extend(compare(left, right, f"{path}[{index}]"))
    elif type(expected) is not type(actual) or expected != actual:
        errors.append(f"{path}: expected={expected!r}, actual={actual!r}")
    return errors


def verify(expected_type, expected, actual):
    errors = []
    if expected_type == "exception":
        if "exception" not in actual:
            errors.append("EXPECTED_EXCEPTION_NOT_RAISED")
    elif "exception" in actual:
        errors.append("UNEXPECTED_EXCEPTION:" + dumps(actual["exception"]))
    errors.extend(compare({k: v for k, v in expected.items() if k != "order_id_nonempty"}, actual))
    if expected.get("order_id_nonempty"):
        order_id = actual.get("return", {}).get("order_id") if isinstance(actual.get("return"), dict) else None
        if not isinstance(order_id, str) or not order_id:
            errors.append("ORDER_ID_EMPTY")
        elif not any(o.get("order_id") == order_id for o in actual["state"]["orders"]):
            errors.append("ORDER_ID_NOT_PERSISTED")
    return errors


def execute_case(row, row_number, run_id, validation_errors=(), parsed=None):
    start = time.perf_counter()
    result = {**row, "run_id": run_id, "csv_row": row_number, "executed_at": now(),
              "execution_status": "BLOCKED", "actual_result": dumps({"not_executed": True}),
              "error_message": "", "observed_before": "", "observed_after": "",
              "defect_id": "", "execution_time_ms": 0.0}
    data, expected = parsed or (None, None)
    op = data.get("operation", "unknown") if isinstance(data, dict) else "unknown"
    result["evidence_reference"] = f"test_cases.csv:row={row_number}#{row.get('test_case_id', '')}; ecommerce_app.py::{TARGETS.get(op, 'validation')}; RUN={run_id}"
    try:
        if validation_errors:
            result["error_message"] = "; ".join(validation_errors)
            return result
        try:
            app, user, cart = fixture(row["fixture_key"], data.get("setup"))
            before = snapshot(app, user, cart)
        except Exception:
            result["error_message"] = "FIXTURE_ERROR (test infrastructure): " + traceback.format_exc(limit=5)
            return result
        actual = {}
        caught_trace = ""
        try:
            returned = dispatch(app, user, cart, data, row["test_case_id"])
            actual.update({"return": encode(returned), "return_type": type(returned).__name__})
        except Exception as error:
            actual["exception"] = {"type": type(error).__name__, "message": str(error)}
            caught_trace = traceback.format_exc(limit=5)
        actual["state"] = snapshot(app, user, cart)
        errors = verify(row["expected_type"], expected, actual)
        result.update({"execution_status": "FAIL" if errors else "PASS", "actual_result": dumps(actual),
                       "observed_before": dumps(before), "observed_after": dumps(actual["state"]),
                       "error_message": "\n".join(errors) + ("\n" + caught_trace if errors and caught_trace else "")})
        if errors:
            if row["test_case_id"] in {"TC-CART-005", "TC-PRO-008"}:
                result["defect_id"] = "DEF-001"
            elif row["requirement_id"] == "REQ-16" and before["stock"] != actual["state"]["stock"]:
                result["defect_id"] = "DEF-003"
            elif before["stock"] != actual["state"]["stock"] and op in {"checkout", "promotion_sequence"}:
                result["defect_id"] = "DEF-002"
            else:
                result["defect_id"] = "UNTRIAGED"
    except Exception:
        result["execution_status"] = "BLOCKED"
        result["error_message"] = "RUNNER_ERROR (test infrastructure): " + traceback.format_exc(limit=6)
    finally:
        result["execution_time_ms"] = round((time.perf_counter() - start) * 1000, 3)
    return result


def summarize(frame, csv_count, trace):
    counts = Counter(frame.execution_status)
    executed = counts["PASS"] + counts["FAIL"]
    assert executed + counts["BLOCKED"] == csv_count, "DATA_COMPLETENESS_FAILED"
    assert len(frame) == csv_count, "RESULT_ROW_COUNT_MISMATCH"
    complete = csv_count > 0 and counts["BLOCKED"] == 0 and executed == csv_count
    covered = set(frame.loc[frame.execution_status.isin(["PASS", "FAIL"]), "requirement_id"]) & REQUIREMENTS
    return {"total": csv_count, "executed": executed, "pass": counts["PASS"], "fail": counts["FAIL"],
            "blocked": counts["BLOCKED"], "pass_rate": round(100 * counts["PASS"] / csv_count, 2) if csv_count else None,
            "pass_rate_denominator": "all CSV rows, including BLOCKED", "data_complete": complete,
            "all_passed": complete and counts["FAIL"] == 0,
            "traceability_coverage": {"selected_requirements": len(REQUIREMENTS),
                "executed_requirements": len(covered), "requirement_execution_percent": round(100 * len(covered) / len(REQUIREMENTS), 2),
                "conditions": frame.condition_id.nunique(), "scenarios": frame.scenario_id.nunique(),
                "mapped_cases": len(trace), "case_mapping_percent": round(100 * len(trace) / csv_count, 2) if csv_count else 0,
                "orphans": trace.attrs.get("orphans", [])},
            "test_cases_sha256": DESIGN_SHA256, "application_sha256": SOURCE_SHA256,
            "executed_at": now(), "run_id": frame.run_id.iloc[0] if len(frame) else "",
            "python": platform.python_version()}


def build_trace(frame, baseline):
    keys = ["requirement_id", "condition_id", "scenario_id", "test_case_id"]
    expected_set = set(map(tuple, baseline[keys].values.tolist()))
    observed_set = set(map(tuple, frame[keys].values.tolist()))
    orphans = [list(x) for x in sorted(expected_set ^ observed_set)]
    trace = frame[keys + ["run_id", "execution_status", "evidence_reference"]].copy()
    trace.attrs["orphans"] = orphans
    return trace


def compare_order_results(baseline, current, order_name, seed=None):
    """Compare complete semantic evidence by unique TC ID, including failed cases."""
    baseline_rows = baseline.to_dict("records")
    current_rows = current.to_dict("records")
    baseline_counts = Counter(row["test_case_id"] for row in baseline_rows)
    current_counts = Counter(row["test_case_id"] for row in current_rows)
    reference = {row["test_case_id"]: row for row in baseline_rows}
    observed = {row["test_case_id"]: row for row in current_rows}
    positions = {row["test_case_id"]: index for index, row in enumerate(current_rows, 1)}
    case_ids = list(dict.fromkeys([row["test_case_id"] for row in current_rows + baseline_rows]))
    fields = {"actual_matches": "actual_result", "before_matches": "observed_before", "after_matches": "observed_after"}
    comparisons = []
    for case_id in case_ids:
        before, after = reference.get(case_id, {}), observed.get(case_id, {})
        errors = []
        if baseline_counts[case_id] != 1 or current_counts[case_id] != 1:
            errors.append(f"CASE_ID_CARDINALITY:baseline={baseline_counts[case_id]},current={current_counts[case_id]}")
        if after.get("execution_status") not in {"PASS", "FAIL"}:
            errors.append("CASE_NOT_EXECUTED")
        row = {"order_name": order_name, "shuffle_seed": seed if seed is not None else "",
               "execution_index": positions.get(case_id, ""), "test_case_id": case_id,
               "baseline_run_id": before.get("run_id", ""), "run_id": after.get("run_id", ""),
               "baseline_status": before.get("execution_status", ""),
               "execution_status": after.get("execution_status", ""),
               "status_matches": before.get("execution_status") == after.get("execution_status"),
               "evidence_reference": after.get("evidence_reference", "")}
        for label, field in fields.items():
            try:
                # Canonical JSON preserves bool/int distinctions and compares every state field.
                left = json.dumps(strict_json(before[field]), sort_keys=True, ensure_ascii=False, allow_nan=False)
                right = json.dumps(strict_json(after[field]), sort_keys=True, ensure_ascii=False, allow_nan=False)
                row[label] = left == right
            except (KeyError, ValueError, TypeError) as error:
                row[label] = False
                errors.append(f"INVALID_COMPARISON_EVIDENCE:{field}:{error}")
        row["matches_baseline"] = not errors and row["status_matches"] and all(row[key] for key in fields)
        row["comparison_error"] = "; ".join(errors + [key for key in ["status_matches", *fields] if not row[key]])
        comparisons.append(row)
    return pd.DataFrame(comparisons)


def run_runner_checks(frame, run_id):
    """Repeatable stdlib unittest checks; synthetic bad data never edits the design."""
    class RunnerRegressionTests(unittest.TestCase):
        def setUp(self):
            self.row = frame.loc[frame.test_case_id == "TC-CART-001"].iloc[0].to_dict()
            self.expected = strict_json(self.row["expected_json"])

        def blocked(self, changes=None, reason="", columns=None, duplicates=()):
            row = {**self.row, **(changes or {})}
            reasons, data, expected = validate_row(row, COLUMNS if columns is None else columns, set(duplicates))
            self.assertTrue(any(reason in item for item in reasons), reasons)
            # No fixture or business dispatch may run for an invalid record.
            with patch.object(sys.modules[__name__], "fixture") as make_fixture:
                result = execute_case(row, 2, run_id + "-RUNNER", reasons, (data, expected))
                make_fixture.assert_not_called()
            self.assertEqual(result["execution_status"], "BLOCKED")
            self.assertTrue(strict_json(result["actual_result"])["not_executed"])
            for key in ("evidence_reference", "error_message", "executed_at"):
                self.assertTrue(result[key])
            self.assertGreaterEqual(result["execution_time_ms"], 0)

        def csv_sample(self, content):
            with tempfile.TemporaryDirectory(dir=REPORTS, prefix="runner-check-") as directory:
                path = Path(directory) / "synthetic.csv"
                path.write_text(content, encoding="utf-8")
                return read_cases(path)

        def order_sample(self):
            return pd.DataFrame([{"test_case_id": "QA-ORDER-001", "execution_status": "PASS",
                                  "run_id": "QA-BASE", "actual_result": '{"return": 1}',
                                  "observed_before": '{"stock": {"A": 20}}',
                                  "observed_after": '{"stock": {"A": 19}}'}])

        def dispatched_result(self, side_effect=None, return_value=None, case_id="TC-CART-001"):
            row = frame.loc[frame.test_case_id == case_id].iloc[0].to_dict()
            reasons, data, expected = validate_row(row, COLUMNS, set())
            with patch.object(sys.modules[__name__], "dispatch", side_effect=side_effect, return_value=return_value):
                return execute_case(row, 2, run_id + "-RUNNER", reasons, (data, expected))

        def test_01_valid_row(self):
            self.assertEqual(validate_row(self.row, COLUMNS, set())[0], [])

        def test_02_invalid_input_json_blocked(self):
            self.blocked({"input_json": "{bad"}, "INVALID_JSON:input_json")

        def test_03_invalid_synthetic_expected_json_blocked(self):
            self.blocked({"test_case_id": "QA-BAD-EXPECTED", "expected_json": "{"}, "INVALID_JSON:expected_json")

        def test_04_missing_schema_column_blocked(self):
            self.blocked(reason="INVALID_SCHEMA", columns=[key for key in COLUMNS if key != "priority"])

        def test_05_both_duplicate_ids_blocked(self):
            for _ in range(2):
                self.blocked(reason="DUPLICATE_TEST_ID", duplicates=[self.row["test_case_id"]])

        def test_06_unknown_operation_blocked(self):
            self.blocked({"input_json": dumps({"operation": "not_supported"})}, "UNKNOWN_OPERATION")

        def test_07_missing_operation_input_blocked(self):
            self.blocked({"input_json": dumps({"operation": "cart_add"})}, "MISSING_OPERATION_INPUT")

        def test_08_unknown_fixture_blocked(self):
            self.blocked({"fixture_key": "not_supported"}, "UNKNOWN_FIXTURE")

        def test_09_nonfinite_json_blocked(self):
            self.blocked({"input_json": '{"operation":"cart_add","additions":NaN}'}, "INVALID_JSON")

        def test_10_missing_synthetic_state_oracle_blocked(self):
            self.blocked({"test_case_id": "QA-MISSING-STATE", "expected_type": "value",
                          "expected_json": '{"return":null}'}, "MISSING_STATE_ORACLE")

        def test_11_malformed_csv_keeps_records(self):
            recovered, reasons = self.csv_sample("a,b\n1,2\n3,4,5\n")
            self.assertEqual(len(recovered), 2)
            self.assertTrue(any("CSV_FIELD_COUNT" in reason for reason in reasons))

        def test_12_blank_csv_record_not_skipped(self):
            recovered, reasons = self.csv_sample("a,b\n1,2\n\n3,4\n")
            self.assertEqual(len(recovered), 3)
            self.assertTrue(reasons)

        def test_13_duplicate_csv_header_detected(self):
            recovered, reasons = self.csv_sample("a,a\n1,2\n")
            self.assertEqual(len(recovered), 1)
            self.assertIn("DUPLICATE_CSV_HEADER", reasons)

        def test_14_expected_exception_and_state_pass(self):
            reasons, data, expected = validate_row(self.row, COLUMNS, set())
            result = execute_case(self.row, 2, run_id + "-RUNNER", reasons, (data, expected))
            self.assertEqual(result["execution_status"], "PASS", result["error_message"])

        def test_15_wrong_exception_message_rejected(self):
            actual = copy.deepcopy(self.expected)
            actual["exception"]["message"] = "OTHER_ERROR"
            self.assertTrue(verify("exception", self.expected, actual))
            result = self.dispatched_result(side_effect=ValueError("OTHER_ERROR"))
            self.assertEqual(result["execution_status"], "FAIL")
            self.assertIn("Traceback", result["error_message"])

        def test_16_wrong_exception_type_rejected(self):
            actual = copy.deepcopy(self.expected)
            actual["exception"]["type"] = "TypeError"
            self.assertTrue(verify("exception", self.expected, actual))
            self.assertEqual(self.dispatched_result(side_effect=TypeError("INVALID_QUANTITY"))["execution_status"], "FAIL")

        def test_17_missing_exception_rejected(self):
            actual = {"return": None, "state": copy.deepcopy(self.expected["state"])}
            self.assertIn("EXPECTED_EXCEPTION_NOT_RAISED", verify("exception", self.expected, actual))
            result = self.dispatched_result(return_value=None)
            self.assertEqual(result["execution_status"], "FAIL")
            self.assertIn("EXPECTED_EXCEPTION_NOT_RAISED", result["error_message"])

        def test_18_unexpected_exception_rejected(self):
            errors = verify("value", {"return": None, "state": {}},
                            {"exception": {"type": "ValueError", "message": "UNEXPECTED"}, "state": {}})
            self.assertTrue(any("UNEXPECTED_EXCEPTION" in error for error in errors))
            result = self.dispatched_result(side_effect=ValueError("UNEXPECTED"), case_id="TC-CART-003")
            self.assertEqual(result["execution_status"], "FAIL")
            self.assertIn("UNEXPECTED_EXCEPTION", result["error_message"])

        def test_19_correct_exception_wrong_state_rejected(self):
            actual = copy.deepcopy(self.expected)
            actual["state"]["stock"]["A"] = 19
            self.assertTrue(verify("exception", self.expected, actual))
            def incorrect_rejection(app, user, cart, data, case_id):
                app.catalog.products["A"].stock = 19
                raise ValueError("INVALID_QUANTITY")
            result = self.dispatched_result(side_effect=incorrect_rejection)
            self.assertEqual(result["execution_status"], "FAIL")
            self.assertIn("state.stock.A", result["error_message"])

        def test_20_bool_not_equal_to_integer(self):
            self.assertTrue(compare(1, True))
            self.assertTrue(compare(True, 1))

        def test_21_fixture_error_is_blocked(self):
            reasons, data, expected = validate_row(self.row, COLUMNS, set())
            with patch.object(sys.modules[__name__], "fixture", side_effect=RuntimeError("QA_SETUP_FAILURE")):
                result = execute_case(self.row, 2, run_id + "-RUNNER", reasons, (data, expected))
            self.assertEqual(result["execution_status"], "BLOCKED")
            self.assertIn("FIXTURE_ERROR", result["error_message"])

        def test_22_fixture_objects_and_state_are_isolated(self):
            first = fixture("mixed")
            second = fixture("mixed")
            for left, right in zip(first, second):
                self.assertIsNot(left, right)
            self.assertIsNot(first[0].catalog, second[0].catalog)
            untouched = snapshot(*second)
            first[0].catalog.products["A"].stock = 0
            first[0].catalog.products["B"].price = Decimal("1")
            first[1].used_codes.add("SAVE10")
            self.assertEqual(snapshot(*second), untouched)

        def test_23_completeness_17_pass_3_blocked_is_85_percent(self):
            sample = pd.DataFrame([{"execution_status": "PASS" if i < 17 else "BLOCKED",
                                    "requirement_id": "REQ-02", "condition_id": "COND-CART-TYPE",
                                    "scenario_id": "TS-CART-QUANTITY", "run_id": "QA-COMP"} for i in range(20)])
            summary = summarize(sample, 20, sample)
            self.assertEqual((summary["total"], summary["executed"], summary["blocked"], summary["pass_rate"]), (20, 17, 3, 85.0))
            self.assertFalse(summary["data_complete"])
            self.assertFalse(summary["all_passed"])

        def test_24_completeness_missing_result_rejected(self):
            sample = pd.DataFrame({"execution_status": ["PASS"] * 19})
            with self.assertRaisesRegex(AssertionError, "DATA_COMPLETENESS_FAILED"):
                summarize(sample, 20, sample)

        def test_25_order_comparison_ignores_runtime_metadata(self):
            baseline = self.order_sample()
            current = baseline.copy()
            current["run_id"] = "QA-OTHER"; current["execution_time_ms"] = 123.0
            current["executed_at"] = "different time"; current["evidence_reference"] = "different RUN"
            self.assertTrue(compare_order_results(baseline, current, "reverse").matches_baseline.all())

        def test_26_order_comparison_detects_status_change(self):
            baseline = self.order_sample(); current = baseline.copy()
            current["execution_status"] = "FAIL"
            self.assertFalse(compare_order_results(baseline, current, "reverse").matches_baseline.all())

        def test_27_order_comparison_detects_actual_or_state_change(self):
            baseline = self.order_sample()
            for field in ("actual_result", "observed_before", "observed_after"):
                current = baseline.copy(); current[field] = '{"changed": true}'
                self.assertFalse(compare_order_results(baseline, current, "reverse").matches_baseline.all())
            current = baseline.copy(); current["actual_result"] = '{"return": true}'
            self.assertFalse(compare_order_results(baseline, current, "reverse").matches_baseline.all())

        def test_28_order_comparison_detects_missing_extra_and_duplicate_ids(self):
            baseline = self.order_sample()
            for current in (baseline.iloc[:0], pd.concat([baseline, baseline], ignore_index=True),
                            baseline.assign(test_case_id="QA-EXTRA")):
                self.assertFalse(compare_order_results(baseline, current, "reverse").matches_baseline.all())

        def test_29_order_comparison_does_not_accept_blocked(self):
            blocked = self.order_sample().assign(execution_status="BLOCKED")
            self.assertFalse(compare_order_results(blocked, blocked, "original").matches_baseline.all())

        def test_30_code_interview_examples(self):
            text = (ROOT / "docs" / "part4_interview.md").read_text(encoding="utf-8")
            snippets = re.findall(r"```python\n(.*?)```", text, re.S)
            self.assertEqual(len(snippets), 3)
            for code, name in zip(snippets, ["check_invalid_quantity", "check_paid_order", "check_fresh_fixture"]):
                namespace = {}
                exec(compile(code, "part4_interview.md", "exec"), namespace)
                self.assertEqual(namespace[name](), "PASS")

        def test_31_application_and_design_locks(self):
            self.assertEqual(digest(ROOT / "ecommerce_app.py"), SOURCE_SHA256)
            self.assertEqual(digest(ROOT / "test_cases.csv"), DESIGN_SHA256)

    class RecordingResult(unittest.TextTestResult):
        def startTest(self, test):
            super().startTest(test)
            self.started = time.perf_counter()
            self.started_at = now()

        def stopTest(self, test):
            problems = dict(self.failures + self.errors)
            skipped = dict(self.skipped)
            check_rows.append({"check_id": test._testMethodName, "execution_status": "FAIL" if test in problems else ("SKIP" if test in skipped else "PASS"),
                               "execution_time_ms": round((time.perf_counter() - self.started) * 1000, 3),
                               "executed_at": self.started_at, "run_id": run_id,
                               "error_message": problems.get(test, skipped.get(test, ""))})
            super().stopTest(test)

    check_rows = []
    buffer = io.StringIO()
    result = unittest.TextTestRunner(stream=buffer, verbosity=2, resultclass=RecordingResult).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(RunnerRegressionTests))
    details = buffer.getvalue()
    info = {"tests_run": result.testsRun, "passed": sum(row["execution_status"] == "PASS" for row in check_rows),
            "failures": len(result.failures), "errors": len(result.errors), "skipped": len(result.skipped),
            "successful": result.wasSuccessful() and not result.skipped and result.testsRun == len(check_rows),
            "evidence_reference": "reports/runner_validation.csv; reports/runner_validation.txt"}
    pd.DataFrame(check_rows).to_csv(REPORTS / "runner_validation.csv", index=False, encoding="utf-8-sig")
    (REPORTS / "runner_validation.txt").write_text(f"RUN={run_id}\nTimestamp={now()}\n{details}\n{dumps(info)}\n", encoding="utf-8")
    print(details, end="")
    print(f"[{now()}] RUNNER CHECKS: {info['passed']}/{info['tests_run']} PASS; successful={info['successful']}")
    return info


def run_order_checks(baseline, prepared, run_id, seed=ORDER_SEED):
    """Reuse the original run, then independently execute reverse and seeded shuffle."""
    original_order = list(prepared)
    shuffled_order = original_order.copy()
    random.Random(seed).shuffle(shuffled_order)
    executions, comparisons, groups = [], [], []
    for name, positions in [("original", original_order), ("reverse", list(reversed(original_order))), ("shuffled", shuffled_order)]:
        if name == "original":
            results = baseline.to_dict("records")
        else:
            results = []
            for position in positions:
                row, data, expected, reasons = prepared[position]
                results.append(execute_case(row, position, run_id + "-ORDER-" + name.upper(), reasons, (data, expected)))
        current = pd.DataFrame(results, columns=baseline.columns)
        check = compare_order_results(baseline, current, name, seed if name == "shuffled" else None)
        comparisons.append(check)
        for index, row in enumerate(results, 1):
            executions.append({**row, "order_name": name, "execution_index": index,
                               "shuffle_seed": seed if name == "shuffled" else ""})
        counts = Counter(current.execution_status)
        group = {"order_name": name, "shuffle_seed": seed if name == "shuffled" else None,
                 "total": len(current), "pass": counts["PASS"], "fail": counts["FAIL"], "blocked": counts["BLOCKED"],
                 "matching_cases": int(check.matches_baseline.sum()),
                 "all_consistent": len(check) == len(baseline) == len(current) and bool(check.matches_baseline.all()) and len(current) > 0,
                 "case_sequence": current.test_case_id.tolist()}
        groups.append(group)
        print(f"[{now()}] ORDER {name}: {len(current)} cases | PASS={counts['PASS']} FAIL={counts['FAIL']} BLOCKED={counts['BLOCKED']} | matches={group['matching_cases']}/{len(baseline)}")
    comparison = pd.concat(comparisons, ignore_index=True)
    pd.DataFrame(executions).to_csv(REPORTS / "order_execution.csv", index=False, encoding="utf-8-sig")
    comparison.to_csv(REPORTS / "order_independence.csv", index=False, encoding="utf-8-sig")
    info = {"baseline_run_id": run_id, "shuffle_seed": seed, "unique_cases": len(baseline),
            "total_executions": len(executions), "reordered_comparisons": int((comparison.order_name != "original").sum()),
            "mismatched_comparisons": int((~comparison.matches_baseline).sum()),
            "all_consistent": all(group["all_consistent"] for group in groups), "orders": groups,
            "comparison_fields": ["execution_status", "actual_result", "observed_before", "observed_after"],
            "evidence_reference": "reports/order_execution.csv; reports/order_independence.csv; reports/order_independence.json"}
    (REPORTS / "order_independence.json").write_text(dumps(info), encoding="utf-8")
    return info


def build_chart(frame):
    os.environ.setdefault("MPLCONFIGDIR", str(REPORTS / ".matplotlib"))
    import matplotlib
    matplotlib.use("Agg")
    from matplotlib.figure import Figure
    grouped = pd.crosstab(frame.requirement_id, frame.execution_status).reindex(columns=["PASS", "FAIL", "BLOCKED"], fill_value=0)
    fig = Figure(figsize=(10, 4.6), layout="constrained")
    ax = fig.subplots()
    bottoms = [0] * len(grouped)
    for status, color in [("PASS", "#15803d"), ("FAIL", "#dc2626"), ("BLOCKED", "#b45309")]:
        values = grouped[status].tolist()
        bars = ax.bar(grouped.index, values, bottom=bottoms, label=status, color=color)
        ax.bar_label(bars, labels=[str(v) if v else "" for v in values], label_type="center", color="white")
        bottoms = [a + b for a, b in zip(bottoms, values)]
    ax.set_ylabel("Test cases"); ax.set_title("EduCommerce: kết quả theo requirement"); ax.legend()
    buffer = io.BytesIO(); fig.savefig(buffer, format="png", dpi=130)
    return buffer.getvalue()


def export_reports(frame, trace, summary, rechecks):
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter
    from openpyxl.chart import BarChart, Reference
    from openpyxl.chart.series import SeriesLabel
    frame.to_csv(REPORTS / "test_execution.csv", index=False, encoding="utf-8-sig")
    rechecks.to_csv(REPORTS / "failure_rechecks.csv", index=False, encoding="utf-8-sig")
    grouped = pd.crosstab(frame.requirement_id, frame.execution_status).reindex(index=sorted(REQUIREMENTS), columns=["PASS", "FAIL", "BLOCKED"], fill_value=0).reset_index()
    grouped["total"] = grouped[["PASS", "FAIL", "BLOCKED"]].sum(axis=1)
    grouped["pass_rate"] = grouped.PASS / grouped.total.replace(0, float("nan"))
    defects = frame.loc[frame.execution_status == "FAIL", ["defect_id", "test_case_id", "requirement_id", "error_message", "evidence_reference"]].copy()
    defects["reproduced"] = defects.test_case_id.map(dict(zip(rechecks.test_case_id, rechecks.reproduced)))
    defects["review_status"] = defects.defect_id.map({"DEF-001": "Cần BA xác nhận bool; lệch quy ước integer nghiêm ngặt", "DEF-002": "Đối chiếu Instruction §2.5: thiếu rollback", "DEF-003": "Đối chiếu REQ-16: reject để lại side effect"}).fillna("Cần triage")
    with pd.ExcelWriter(REPORTS / "test_report.xlsx", engine="openpyxl") as writer:
        frame.to_excel(writer, sheet_name="Execution", index=False)
        trace.to_excel(writer, sheet_name="Traceability", index=False)
        grouped.to_excel(writer, sheet_name="Summary", index=False)
        defects.to_excel(writer, sheet_name="Defects", index=False)
        colors = {"PASS": "DCFCE7", "FAIL": "FEE2E2", "BLOCKED": "FEF3C7"}
        for sheet in writer.book:
            sheet.freeze_panes = "C2"; sheet.auto_filter.ref = sheet.dimensions
            sheet.sheet_view.showGridLines = False
            for cell in sheet[1]:
                cell.fill = PatternFill("solid", fgColor="17385F")
                cell.font = Font(color="FFFFFF", bold=True)
                cell.alignment = Alignment(wrap_text=True, vertical="center")
            sheet.row_dimensions[1].height = 34
            for index, header in enumerate(sheet[1], 1):
                width = 20
                if header.value in {"expected_json", "actual_result", "observed_before", "observed_after", "error_message", "evidence_reference", "input_json", "review_status"}:
                    width = 68
                elif header.value in {"title", "precondition"}:
                    width = 48
                sheet.column_dimensions[get_column_letter(index)].width = width
            for cells in sheet.iter_rows(min_row=2):
                line_count = 1
                for cell in cells:
                    cell.alignment = Alignment(vertical="top", wrap_text=True)
                    cell.font = Font(name="Arial", size=11)
                    width = max(8, int(sheet.column_dimensions[cell.column_letter].width) - 4)
                    # Fit wrapped JSON/traceback without omitting the raw cell value.
                    lines = sum(max(1, len(textwrap.wrap(part, width=width))) for part in str(cell.value or "").split("\n"))
                    line_count = max(line_count, lines)
                    if isinstance(cell.value, str) and cell.value in colors:
                        cell.fill = PatternFill("solid", fgColor=colors[cell.value])
                sheet.row_dimensions[cells[0].row].height = min(409, max(34, line_count * 15 + 8))
            if sheet.title == "Summary":
                sheet.freeze_panes = None
                for cell in sheet["F"][1:]: cell.number_format = "0.0%"
        sheet = writer.book["Summary"]
        chart = BarChart(); chart.type = "col"; chart.grouping = "stacked"; chart.overlap = 100
        chart.title = "Kết quả theo requirement"; chart.y_axis.title = "Test cases"
        chart.add_data(Reference(sheet, min_col=2, max_col=4, min_row=1, max_row=8), titles_from_data=True)
        chart.set_categories(Reference(sheet, min_col=1, min_row=2, max_row=8))
        for series, status, color in zip(chart.series, ["PASS", "FAIL", "BLOCKED"], ["15803D", "DC2626", "B45309"]):
            series.tx = SeriesLabel(v=status)
            series.graphicalProperties.solidFill = color
            series.graphicalProperties.line.solidFill = color
        chart.width = 23; chart.height = 12; sheet.add_chart(chart, "H2")
    chart_bytes = build_chart(frame)
    (REPORTS / "requirement_status.png").write_bytes(chart_bytes)
    chart_b64 = base64.b64encode(chart_bytes).decode("ascii")
    display_cols = ["test_case_id", "requirement_id", "execution_status", "expected_json", "actual_result", "execution_time_ms", "defect_id"]
    records = frame[display_cols].to_dict("records")
    payload = json.dumps(records, ensure_ascii=False).replace("<", "\\u003c")
    page = '''<!doctype html><html lang="vi"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>EduCommerce Test Dashboard</title>
<style>body{font:15px system-ui;margin:28px;color:#17304c}h1{font-size:28px}.metrics{display:flex;gap:14px;flex-wrap:wrap}.metric{background:#edf3fa;padding:18px;border-radius:8px}img{max-width:100%}table{border-collapse:collapse;width:100%;font-size:13px}td,th{border:1px solid #ccd5df;padding:10px;text-align:left;vertical-align:top}th{background:#17385f;color:white}pre{white-space:pre-wrap;overflow-wrap:anywhere;max-width:480px;margin:0}.table{overflow:auto}select{padding:8px;margin:12px}.FAIL{color:#b91c1c}.PASS{color:#166534}.BLOCKED{color:#92400e}</style>
<h1>EduCommerce — Kết quả kiểm thử</h1>'''
    page += '<p>' + html.escape(summary["run_id"] + " | " + summary["executed_at"]) + '</p><div class="metrics">'
    for label, key in [("Tổng", "total"), ("PASS", "pass"), ("FAIL", "fail"), ("BLOCKED", "blocked"), ("Pass rate (%)", "pass_rate")]:
        page += f'<div class="metric">{label}: <strong>{summary[key]}</strong></div>'
    page += '</div><p>Pass rate dùng toàn bộ dòng CSV làm mẫu số. BLOCKED không được tính là PASS. Coverage là phạm vi đã chạy, không chứng minh mọi hành vi đều đúng.</p>'
    if "runner_validation" in summary and "order_independence" in summary:
        runner = summary["runner_validation"]
        orders = summary["order_independence"]
        page += '<h2>Kiểm tra độ tin cậy của runner</h2>'
        page += f'<p>Runner regression: {runner["passed"]}/{runner["tests_run"]} PASS; failures={runner["failures"]}, errors={runner["errors"]}, skipped={runner["skipped"]}. '
        page += '<a href="runner_validation.txt">Log kiểm runner</a> · <a href="runner_validation.csv">Chi tiết CSV</a></p>'
        page += '<h2>Kiểm tra độc lập với thứ tự chạy</h2>'
        order_table = pd.DataFrame(orders["orders"])[["order_name", "shuffle_seed", "total", "pass", "fail", "blocked", "matching_cases", "all_consistent"]]
        # Use text for seed display only; the JSON artifact retains a typed integer.
        order_table["shuffle_seed"] = [str(row["shuffle_seed"]) if row["shuffle_seed"] is not None else "" for row in orders["orders"]]
        page += order_table.to_html(index=False, border=0)
        page += f'<p>Seed={orders["shuffle_seed"]}; {orders["reordered_comparisons"]} đối chiếu từ hai thứ tự bổ sung; sai lệch={orders["mismatched_comparisons"]}. '
        page += 'So status, actual và toàn bộ state trước/sau theo TC ID; không so timestamp, thời gian chạy hoặc traceback. Đây vẫn là 52 ca nghiệp vụ, mỗi ca có ba lượt thực thi; kết quả FAIL ổn định không có nghĩa sản phẩm đã hết lỗi. '
        page += '<a href="order_independence.csv">Bảng so sánh</a> · <a href="order_execution.csv">Raw execution ba thứ tự</a> · <a href="order_independence.json">Tổng hợp JSON</a></p>'
        page += f'<p>Xác minh đầy đủ: {summary["verification_complete"]}. Các bộ kiểm này không thay đổi mẫu số PASS rate nghiệp vụ.</p>'
    page += grouped.to_html(index=False, border=0)
    page += f'<img alt="Biểu đồ PASS FAIL BLOCKED theo requirement" src="data:image/png;base64,{chart_b64}">'
    page += '<p><label>Requirement <select id="req"><option>ALL</option>' + ''.join(f'<option>{r}</option>' for r in sorted(REQUIREMENTS)) + '</select></label><label>Status <select id="status"><option>ALL</option><option>PASS</option><option>FAIL</option><option>BLOCKED</option></select></label></p><p id="count"></p><div class="table"><table><thead><tr>'
    page += ''.join('<th>' + html.escape(c) + '</th>' for c in display_cols) + '</tr></thead><tbody id="rows"></tbody></table></div>'
    page += '<script>const records=' + payload + ';const columns=' + json.dumps(display_cols) + ''';
function draw(){const req=document.querySelector('#req').value,status=document.querySelector('#status').value;
const filtered=records.filter(r=>(req==='ALL'||r.requirement_id===req)&&(status==='ALL'||r.execution_status===status));
const body=document.querySelector('#rows');body.replaceChildren();filtered.forEach(r=>{const tr=document.createElement('tr');columns.forEach(c=>{const td=document.createElement('td'),pre=document.createElement('pre');pre.textContent=String(r[c]);td.append(pre);if(c==='execution_status')td.className=r[c];tr.append(td)});body.append(tr)});document.querySelector('#count').textContent='Hiển thị '+filtered.length+' / '+records.length+' dòng';}
document.querySelector('#req').onchange=draw;document.querySelector('#status').onchange=draw;draw();</script></html>'''
    (REPORTS / "test_dashboard.html").write_text(page, encoding="utf-8")
    (REPORTS / "summary.json").write_text(dumps(summary), encoding="utf-8")


def run_suite():
    """Clean only our generated reports; never modify the design CSV or application."""
    if REPORTS.is_symlink():
        raise ValueError("REPORTS_SYMLINK_REJECTED")
    if REPORTS.exists():
        shutil.rmtree(REPORTS)
    REPORTS.mkdir()
    os.environ["MPLCONFIGDIR"] = str(REPORTS / ".matplotlib")
    source = ROOT / "test_cases.csv"
    source_before = digest(source)
    frame, read_errors = read_cases(source)
    baseline = pd.read_csv(ROOT / "traceability_matrix.csv", dtype=str, keep_default_na=False)
    frame = frame.reindex(columns=list(dict.fromkeys(list(frame.columns) + COLUMNS)), fill_value="")
    original_columns = list(pd.read_csv(source, nrows=0, keep_default_na=False).columns) if not read_errors else list(frame.columns)
    global_errors = list(read_errors)
    if digest(ROOT / "ecommerce_app.py") != SOURCE_SHA256:
        global_errors.append("APPLICATION_IMMUTABILITY_VIOLATION")
    if source_before != DESIGN_SHA256:
        global_errors.append("EXPECTED_DESIGN_LOCK_CHANGED:approval required")
    keys = ["requirement_id", "condition_id", "scenario_id", "test_case_id"]
    if list(baseline.columns) != keys + ["run_id", "execution_status", "evidence_reference"]:
        global_errors.append("TRACEABILITY_SCHEMA_ERROR")
    elif Counter(map(tuple, baseline[keys].values.tolist())) != Counter(map(tuple, frame[keys].values.tolist())):
        global_errors.append("TRACEABILITY_ORPHAN_OR_DUPLICATE")
    if set(frame.requirement_id) != REQUIREMENTS or set(frame.condition_id) != {"COND-" + c for c in CONDITIONS} or set(frame.scenario_id) != {"TS-" + s for s in SCENARIOS}:
        global_errors.append("INCOMPLETE_DESIGN_REGISTRY")
    duplicates = set(frame.loc[frame.test_case_id.duplicated(keep=False), "test_case_id"])
    run_id = "RUN-" + datetime.now(LOCAL_TZ).strftime("%Y%m%dT%H%M%S%f%z")
    print(f"[{now()}] {run_id} | Python {platform.python_version()}")
    print(f"[{now()}] Expected locked SHA256={source_before}; application SHA256={digest(ROOT / 'ecommerce_app.py')}")
    print(f"[{now()}] Clean reports; read {len(frame)} CSV records; fresh fixture for every case.")
    runner_checks = run_runner_checks(frame, run_id)
    results, prepared = [], {}
    for index, row in enumerate(frame.to_dict("records"), 2):
        reasons, data, expected = validate_row(row, original_columns, duplicates)
        result = execute_case(row, index, run_id, global_errors + reasons, (data, expected))
        results.append(result); prepared[index] = (row, data, expected, global_errors + reasons)
        print(f"[{now()}] {result['test_case_id']} {result['execution_status']} {result['execution_time_ms']:.3f}ms | {result['error_message'].splitlines()[0] if result['error_message'] else 'oracle + state matched'}")
    output = pd.DataFrame(results, columns=list(frame.columns) + [c for c in ["run_id", "csv_row", "executed_at", "observed_before", "observed_after", "defect_id", "execution_time_ms"] if c not in frame.columns])
    rechecks = []
    for result in results:
        if result["execution_status"] != "FAIL":
            continue
        row, data, expected, reasons = prepared[result["csv_row"]]
        repeat = execute_case(row, result["csv_row"], run_id + "-RECHECK-" + row["test_case_id"], reasons, (data, expected))
        repeat["original_run_id"] = run_id
        repeat["reproduced"] = repeat["execution_status"] == "FAIL" and repeat["actual_result"] == result["actual_result"]
        rechecks.append(repeat)
        print(f"[{now()}] RECHECK {row['test_case_id']} {repeat['execution_status']} reproduced={repeat['reproduced']} fixture=new")
    recheck_frame = pd.DataFrame(rechecks, columns=list(output.columns) + ["original_run_id", "reproduced"])
    trace = build_trace(output, baseline)
    summary = summarize(output, len(frame), trace)
    summary["failure_rechecks"] = len(rechecks)
    summary["all_failures_reproduced"] = all(x["reproduced"] for x in rechecks)
    summary["runner_validation"] = runner_checks
    summary["order_independence"] = run_order_checks(output, prepared, run_id)
    summary["verification_complete"] = (summary["data_complete"] and summary["all_failures_reproduced"]
                                        and runner_checks["successful"] and summary["order_independence"]["all_consistent"])
    summary["all_passed"] = summary["all_passed"] and summary["verification_complete"]
    export_reports(output, trace, summary, recheck_frame)
    trace.to_csv(ROOT / "traceability_matrix.csv", index=False, encoding="utf-8-sig")
    assert digest(source) == source_before == DESIGN_SHA256, "EXPECTED_CHANGED_DURING_RUN"
    assert digest(ROOT / "ecommerce_app.py") == SOURCE_SHA256, "APPLICATION_CHANGED_DURING_RUN"
    if not summary["data_complete"]:
        print(f"[{now()}] WARNING: thiếu dữ liệu hoặc có BLOCKED; từ chối kết luận 100% PASS.")
    if not summary["verification_complete"]:
        print(f"[{now()}] WARNING: runner regression hoặc order isolation chưa đạt; không xác nhận kết quả kiểm thử đầy đủ.")
    print(f"[{now()}] TOTAL={summary['total']} PASS={summary['pass']} FAIL={summary['fail']} BLOCKED={summary['blocked']} executed={summary['executed']} pass_rate={summary['pass_rate']}%")
    print(f"[{now()}] Completeness: executed + blocked = CSV rows. Reproduced={summary['all_failures_reproduced']}.")
    print(f"[{now()}] Verification complete={summary['verification_complete']} | runner checks={runner_checks['passed']}/{runner_checks['tests_run']} | order independence={summary['order_independence']['all_consistent']}")
    return output, summary


class TimestampTee:
    def __init__(self, terminal, log):
        self.terminal, self.log = terminal, log
        self.line_start = True

    def write(self, text):
        self.terminal.write(text)
        for part in text.splitlines(keepends=True):
            if self.line_start and part:
                self.log.write(f"[{now()}] ")
            self.log.write(part)
            self.line_start = part.endswith("\n")
        self.log.flush()
        return len(text)

    def flush(self):
        self.terminal.flush(); self.log.flush()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", help="Reproduce one case on fresh fixture; no report files overwritten")
    args = parser.parse_args()
    with (ROOT / "run_log.txt").open("a", encoding="utf-8") as log:
        with redirect_stdout(TimestampTee(sys.stdout, log)), redirect_stderr(TimestampTee(sys.stderr, log)):
            if args.case:
                frame, errors = read_cases(ROOT / "test_cases.csv")
                matched = frame.index[frame.test_case_id == args.case].tolist()
                if len(matched) != 1:
                    raise ValueError("CASE_ID_NOT_UNIQUE_OR_NOT_FOUND")
                index = matched[0]; row = frame.iloc[index].to_dict()
                reasons, data, expected = validate_row(row, frame.columns, set())
                if digest(ROOT / "ecommerce_app.py") != SOURCE_SHA256 or digest(ROOT / "test_cases.csv") != DESIGN_SHA256:
                    reasons.append("IMMUTABILITY_LOCK_CHANGED")
                print(dumps(execute_case(row, index + 2, "MANUAL-" + now(), errors + reasons, (data, expected))))
                return 0
            try:
                _, summary = run_suite()
                return 0 if summary["verification_complete"] else 2
            except Exception:
                traceback.print_exc()
                print(f"[{now()}] SUITE_ERROR: report completion not confirmed; do not claim 100% PASS.")
                return 3


if __name__ == "__main__":
    raise SystemExit(main())
