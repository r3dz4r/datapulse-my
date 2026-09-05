from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "scripts/tests/fixtures/st_energy"
MODULE_PATH = ROOT / "scripts/st_energy_adapter.py"
SPEC = importlib.util.spec_from_file_location("st_energy_adapter", MODULE_PATH)
assert SPEC and SPEC.loader
adapter = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = adapter
SPEC.loader.exec_module(adapter)


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_policy_accepts_st_energy_adapter_shape() -> None:
    policy = json.loads((ROOT / "scripts/probe-policy.json").read_text())
    schema = json.loads((ROOT / "scripts/probe-policy.schema.json").read_text())
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    assert not list(validator.iter_errors(policy))
    assert policy["datasets"]["st_installed_capacity_mw"]["adapter"] == "st-energy"
    invalid = {
        **policy,
        "datasets": {
            **policy["datasets"],
            "st_installed_capacity_mw": {
                **policy["datasets"]["st_installed_capacity_mw"],
                "url": "https://evil.invalid/statistics",
            },
        },
    }
    assert list(validator.iter_errors(invalid))


def test_form_fixture_replay_returns_latest_table_year_not_navigation_shell() -> None:
    detail = adapter.find_detail_url(fixture("base.html"), "ViewStatisticELC3", "38")
    assert detail and "flowId=38" in detail
    request = adapter.form_request(fixture("detail_elc3.html"), "region", "1", "products")
    assert request and request[0].endswith("searchStatistic.oas")
    assert "allProducts=1" in request[1] and "allProducts=2" in request[1]
    year, rows, columns = adapter.latest_table_year(fixture("report.html"))
    assert (year, rows, columns) == (2021, 2, 2)
    assert adapter.latest_table_year(fixture("base.html"))[0] is None


def test_pdf_fixture_selects_latest_document_year() -> None:
    assert adapter.latest_pdf_link(fixture("detail_elc1.html")) == (
        2023,
        "https://meih.st.gov.my/STOASPublicPortlet/energystatistic/downloadElcFile.oas?id=11&nonce=session",
    )


def test_missing_report_and_unapproved_destination_fail_closed() -> None:
    assert adapter.form_request("<form id='parameterForm' action='https://evil.invalid/post'></form>", None, None, None) is None
    assert adapter.latest_table_year("<html>navigation shell</html>")[0] is None
    assert not adapter.approved_url("https://evil.invalid/post", allow_report=True)


def test_fixture_parsing_is_deterministic() -> None:
    first = (adapter.find_detail_url(fixture("base.html"), "ViewStatisticELC3", "38"), adapter.latest_table_year(fixture("report.html")), adapter.latest_pdf_link(fixture("detail_elc1.html")))
    second = (adapter.find_detail_url(fixture("base.html"), "ViewStatisticELC3", "38"), adapter.latest_table_year(fixture("report.html")), adapter.latest_pdf_link(fixture("detail_elc1.html")))
    assert first == second
