import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = ROOT / "scripts/probe-policy.json"
SCHEMA_PATH = ROOT / "scripts/probe-policy.schema.json"


@pytest.fixture(scope="module")
def schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


@pytest.fixture
def policy() -> dict:
    return json.loads(POLICY_PATH.read_text(encoding="utf-8"))


def errors_for(schema: dict, policy: dict) -> list:
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    return list(validator.iter_errors(policy))


def test_checked_in_policy_is_valid(schema: dict, policy: dict) -> None:
    assert errors_for(schema, policy) == []


def test_unknown_keys_fail(schema: dict, policy: dict) -> None:
    invalid = copy.deepcopy(policy)
    invalid["datasets"]["fuelprice"]["unexpected"] = True

    assert errors_for(schema, invalid)


def test_unsupported_adapters_fail(schema: dict, policy: dict) -> None:
    invalid = copy.deepcopy(policy)
    invalid["datasets"]["fuelprice"]["adapter"] = "selenium"

    assert errors_for(schema, invalid)


@pytest.mark.parametrize(
    "template",
    [
        "http://storage.data.gov.my/pricecatcher/pricecatcher_{YYYY-MM}.parquet",
        "https://example.com/pricecatcher_{YYYY-MM}.parquet",
        "https://storage.data.gov.my/pricecatcher/{YYYY-MM}/../../secrets",
    ],
)
def test_unsafe_url_templates_fail(schema: dict, policy: dict, template: str) -> None:
    invalid = copy.deepcopy(policy)
    invalid["datasets"]["pricecatcher"]["dynamic-url"]["template"] = template

    assert errors_for(schema, invalid)


@pytest.mark.parametrize("field", ["", "Date", "date-value", "date;rm", "../date"])
def test_invalid_date_fields_fail(schema: dict, policy: dict, field: str) -> None:
    invalid = copy.deepcopy(policy)
    invalid["datasets"]["fuelprice"]["freshness"]["content-date-field"] = field

    assert errors_for(schema, invalid)


def test_shared_http_template_with_headers_is_valid(schema: dict, policy: dict) -> None:
    configured = copy.deepcopy(policy)
    configured["templates"] = {
        "bnm-open-api": {
            "type": "http",
            "headers": {
                "Accept": "application/vnd.BNM.API.v1+json",
                "User-Agent": "Mozilla/5.0 (compatible; DataPulseMY/1.0)",
            },
            "freshness": {
                "content-date-field": "meta.last_updated",
                "extraction-mode": "max",
                "fallback": "last-modified",
            },
        }
    }
    configured["datasets"]["bnm_opr"] = {"template": "bnm-open-api"}

    assert errors_for(schema, configured) == []


def test_header_values_with_newlines_fail(schema: dict, policy: dict) -> None:
    configured = copy.deepcopy(policy)
    configured["templates"] = {
        "bnm-open-api": {
            "type": "http",
            "headers": {"Accept": "application/json\r\nX-Injected: true"},
        }
    }

    assert errors_for(schema, configured)
