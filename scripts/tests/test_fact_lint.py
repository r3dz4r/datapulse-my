from pathlib import Path

from scripts.fact_lint import lint_documents


def lint_fixture(
    tmp_path: Path,
    *,
    current_text: str | None = None,
    historical_text: str | None = None,
) -> list[str]:
    current_docs: tuple[str, ...] = ()
    historical_docs: tuple[str, ...] = ()

    if current_text is not None:
        (tmp_path / "current.md").write_text(current_text, encoding="utf-8")
        current_docs = ("current.md",)
    if historical_text is not None:
        (tmp_path / "historical.md").write_text(historical_text, encoding="utf-8")
        historical_docs = ("historical.md",)

    return lint_documents(tmp_path, current_docs, historical_docs)


def test_current_doc_with_stale_economy_count_is_flagged(tmp_path: Path) -> None:
    errors = lint_fixture(tmp_path, current_text="Filters: Economy (45)\n")

    assert errors == [
        "current.md:1: prohibited literal 'Economy (45)' in current doc "
        "(current: 'Economy (126)')"
    ]


def test_current_doc_with_stale_missing_count_is_flagged(tmp_path: Path) -> None:
    errors = lint_fixture(tmp_path, current_text="The audit found 74 missing files.\n")

    assert errors == [
        "current.md:1: prohibited literal '74 missing' in current doc "
        "(current: '0 missing')"
    ]


def test_historical_doc_without_date_stamp_is_flagged(tmp_path: Path) -> None:
    errors = lint_fixture(tmp_path, historical_text="# Historical report\n\nNo date here.\n")

    assert errors == ["historical.md: missing date stamp in first 5 lines"]


def test_historical_doc_with_date_stamp_in_first_five_lines_passes(
    tmp_path: Path,
) -> None:
    errors = lint_fixture(
        tmp_path,
        historical_text="# Historical report\n\nObserved on 2026-08-05.\n",
    )

    assert errors == []


def test_stale_166_dataset_count_is_flagged(tmp_path: Path) -> None:
    errors = lint_fixture(tmp_path, current_text="The registry contains 166 datasets.\n")

    assert errors == [
        "current.md:1: prohibited literal '166 datasets' in current doc "
        "(current: '335 datasets')"
    ]


def test_clean_current_doc_passes(tmp_path: Path) -> None:
    errors = lint_fixture(tmp_path, current_text="The registry contains 335 datasets.\n")

    assert errors == []
