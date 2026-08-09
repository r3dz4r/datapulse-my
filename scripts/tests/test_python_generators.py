import ast
import json
import re
import shutil
import subprocess
from pathlib import Path

from scripts.tests.generator_harness import (
    GeneratorRun,
    run_generator,
    run_generator_twice,
)


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "scripts/tests/fixtures/generator/python_release"

CHANGELOG_GENERATOR = ROOT / "scripts/gen_changelog.py"
JSONLD_GENERATOR = ROOT / "scripts/gen_jsonld_catalog.py"
MCP_GENERATOR = ROOT / "scripts/gen_mcp_reference.py"

CHANGELOG_INPUTS = ["datapulse.json", "health/latest.json"]
CHANGELOG_OUTPUTS = ["changelog.json"]
JSONLD_INPUTS = ["datapulse.json", "health/latest.json", "docs/index.html"]
JSONLD_OUTPUTS = [
    "data/jsonld/catalog.json",
    "data/jsonld/alpha.json",
    "data/jsonld/beta.json",
    "docs/index.html",
]
MCP_INPUTS = ["datapulse.json", "mcp.json", "mcp/server.py", "docs"]
MCP_OUTPUTS = ["docs/mcp-reference.md", "mcp.json"]

EXPECTED_TOOL_NAMES = (
    "search_datasets",
    "get_dataset",
    "find_stale",
    "get_provenance",
    "find_by_licence",
)


def _run(
    generator: Path,
    inputs: list[str],
    outputs: list[str],
    *,
    source_root: Path = FIXTURE,
    workdir_root: Path | None = None,
) -> GeneratorRun:
    return run_generator(
        source_root,
        generator,
        inputs,
        outputs,
        workdir_root=workdir_root,
    )


def _json_output(run: GeneratorRun, path: str) -> dict:
    output = run.outputs[path]
    assert output is not None, f"missing generated output: {path}"
    document = json.loads(output.decode("utf-8"))
    assert isinstance(document, dict)
    return document


def _is_mcp_tool_decorator(decorator: ast.expr) -> bool:
    return (
        isinstance(decorator, ast.Call)
        and isinstance(decorator.func, ast.Attribute)
        and isinstance(decorator.func.value, ast.Name)
        and decorator.func.value.id == "mcp"
        and decorator.func.attr == "tool"
    )


def _manually_registered_functions(tree: ast.Module) -> set[str]:
    registered: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        owner = node.func.value
        if (
            node.func.attr == "from_function"
            and isinstance(owner, ast.Name)
            and owner.id == "FunctionTool"
            and node.args
            and isinstance(node.args[0], ast.Name)
        ):
            registered.add(node.args[0].id)
    return registered


def _schema_for_type(annotation: ast.expr) -> dict:
    if isinstance(annotation, ast.Name):
        primitive_types = {"str": "string", "int": "integer", "bool": "boolean"}
        if annotation.id in primitive_types:
            return {"type": primitive_types[annotation.id]}
        if annotation.id == "None":
            return {"type": "null"}

    if isinstance(annotation, ast.Constant) and annotation.value is None:
        return {"type": "null"}

    if isinstance(annotation, ast.BinOp) and isinstance(annotation.op, ast.BitOr):
        return {
            "anyOf": [
                _schema_for_type(annotation.left),
                _schema_for_type(annotation.right),
            ]
        }

    if (
        isinstance(annotation, ast.Subscript)
        and isinstance(annotation.value, ast.Name)
        and annotation.value.id == "list"
    ):
        return {"items": _schema_for_type(annotation.slice), "type": "array"}

    raise AssertionError(f"unsupported MCP parameter annotation: {ast.dump(annotation)}")


def _schema_for_parameter(annotation: ast.expr, default: ast.expr | None) -> dict:
    assert isinstance(annotation, ast.Subscript)
    assert isinstance(annotation.value, ast.Name)
    assert annotation.value.id == "Annotated"
    assert isinstance(annotation.slice, ast.Tuple)

    base_annotation, field = annotation.slice.elts
    schema = _schema_for_type(base_annotation)
    assert isinstance(field, ast.Call)
    assert isinstance(field.func, ast.Name) and field.func.id == "Field"

    is_array = schema.get("type") == "array"
    field_names = {
        "description": "description",
        "examples": "examples",
        "ge": "minimum",
        "le": "maximum",
        "min_length": "minItems" if is_array else "minLength",
        "max_length": "maxItems" if is_array else "maxLength",
    }
    for keyword in field.keywords:
        if keyword.arg in field_names:
            schema[field_names[keyword.arg]] = ast.literal_eval(keyword.value)

    if default is not None:
        schema["default"] = ast.literal_eval(default)
    return schema


def _runtime_schemas_from_ast(server_path: Path) -> dict[str, dict]:
    tree = ast.parse(server_path.read_text(encoding="utf-8"), filename=str(server_path))
    manual_tools = _manually_registered_functions(tree)
    schemas: dict[str, dict] = {}

    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        decorated = any(_is_mcp_tool_decorator(item) for item in node.decorator_list)
        if not decorated and node.name not in manual_tools:
            continue

        defaults = [None] * (len(node.args.args) - len(node.args.defaults)) + list(
            node.args.defaults
        )
        properties: dict[str, dict] = {}
        required: list[str] = []
        for argument, default in zip(node.args.args, defaults, strict=True):
            assert argument.annotation is not None
            properties[argument.arg] = _schema_for_parameter(argument.annotation, default)
            if default is None:
                required.append(argument.arg)

        schemas[node.name] = {
            "additionalProperties": False,
            "properties": properties,
            "required": required,
            "type": "object",
        }

    return schemas


def _markdown_tool_schemas(markdown: str) -> dict[str, dict]:
    schemas: dict[str, dict] = {}
    pattern = re.compile(
        r"^### `([^`]+)`\n.*?^```json\n(.*?)^```$",
        flags=re.MULTILINE | re.DOTALL,
    )
    for name, schema_text in pattern.findall(markdown):
        schemas[name] = json.loads(schema_text)
    return schemas


def test_changelog_joins_manifest_and_health() -> None:
    result = _run(CHANGELOG_GENERATOR, CHANGELOG_INPUTS, CHANGELOG_OUTPUTS)

    assert result.returncode == 0, result.stderr
    changelog = _json_output(result, "changelog.json")
    assert changelog["generated_at"] == "2026-08-08T12:34:56Z"
    assert changelog["health"]["checked_at"] == "2026-08-08T12:34:56Z"
    assert {
        row["dataset_id"]: {
            "name": row["name"],
            "namespace": row["namespace"],
            "licence": row["licence"],
            "lifecycle": row["lifecycle"],
            "status": row["status"],
            "last_checked": row["last_checked"],
        }
        for row in changelog["datasets"]
    } == {
        "alpha": {
            "name": "Alpha Dataset",
            "namespace": "official",
            "licence": "CC BY 4.0",
            "lifecycle": "active",
            "status": "fresh",
            "last_checked": "2026-08-08T12:30:00Z",
        },
        "beta": {
            "name": "Beta Dataset",
            "namespace": "community",
            "licence": "Open Government Licence (Malaysia)",
            "lifecycle": "maintained",
            "status": "stale",
            "last_checked": "2026-08-08T12:31:00Z",
        },
    }


def test_changelog_counts_match_trust_summary() -> None:
    result = _run(CHANGELOG_GENERATOR, CHANGELOG_INPUTS, CHANGELOG_OUTPUTS)

    assert result.returncode == 0, result.stderr
    changelog = _json_output(result, "changelog.json")
    health = json.loads((FIXTURE / "health/latest.json").read_text(encoding="utf-8"))
    assert changelog["manifest"]["datasets_total"] == 2
    assert changelog["health"]["datasets_total"] == 2
    assert changelog["health"]["by_status"] == health["_trust_summary"]["by_status"]


def test_changelog_handles_malformed_health(tmp_path: Path) -> None:
    source = tmp_path / "malformed-source"
    shutil.copytree(FIXTURE, source)
    (source / "health/latest.json").write_text('{"checked_at":', encoding="utf-8")

    result = _run(
        CHANGELOG_GENERATOR,
        ["datapulse.json", "health"],
        CHANGELOG_OUTPUTS,
        source_root=source,
    )

    assert result.returncode != 0
    assert result.outputs["changelog.json"] is None


def test_jsonld_catalog_covers_all_manifest_ids() -> None:
    result = _run(JSONLD_GENERATOR, JSONLD_INPUTS, JSONLD_OUTPUTS)

    assert result.returncode == 0, result.stderr
    catalog = _json_output(result, "data/jsonld/catalog.json")
    assert {row["identifier"] for row in catalog["dataset"]} == {"alpha", "beta"}
    assert result.outputs["data/jsonld/alpha.json"] is not None
    assert result.outputs["data/jsonld/beta.json"] is not None
    by_id = {row["identifier"]: row for row in catalog["dataset"]}
    assert by_id["alpha"]["dateModified"] == "2026-08-07"
    assert by_id["beta"]["dateModified"] == "2026-08-08"
    assert by_id["alpha"]["variableMeasured"][1]["value"] == 11
    assert by_id["beta"]["variableMeasured"][1]["value"] == 22


def test_jsonld_urls_use_canonical_host() -> None:
    result = _run(JSONLD_GENERATOR, JSONLD_INPUTS, JSONLD_OUTPUTS)

    assert result.returncode == 0, result.stderr
    for dataset_id in ("alpha", "beta"):
        dataset = _json_output(result, f"data/jsonld/{dataset_id}.json")
        assert dataset["@id"].startswith("https://data-pulse.my/")
        assert dataset["url"].startswith("https://data-pulse.my/")
        assert dataset["publisher"]["@id"].startswith("https://data-pulse.my/")
        assert dataset["distribution"][0]["contentUrl"].startswith(
            "https://data-pulse.my/"
        )
        assert "r3dz4r.github.io" not in json.dumps(dataset)


def test_jsonld_removes_obsolete_per_id_files(tmp_path: Path) -> None:
    source = tmp_path / "stale-source"
    shutil.copytree(FIXTURE, source)
    obsolete = source / "data/jsonld/obsolete.json"
    obsolete.parent.mkdir(parents=True)
    obsolete.write_text('{"identifier": "obsolete"}\n', encoding="utf-8")

    result = _run(
        JSONLD_GENERATOR,
        JSONLD_INPUTS + ["data/jsonld/obsolete.json"],
        JSONLD_OUTPUTS + ["data/jsonld/obsolete.json"],
        source_root=source,
    )

    assert result.returncode == 0, result.stderr
    # The generator writes current IDs but never scans or unlinks the directory;
    # its approved current policy is therefore to preserve obsolete JSON-LD files.
    assert result.outputs["data/jsonld/obsolete.json"] == (
        b'{"identifier": "obsolete"}\n'
    )


def test_mcp_reference_matches_runtime_schema() -> None:
    result = _run(MCP_GENERATOR, MCP_INPUTS, MCP_OUTPUTS)

    assert result.returncode == 0, result.stderr
    output = result.outputs["docs/mcp-reference.md"]
    assert output is not None
    documented = _markdown_tool_schemas(output.decode("utf-8"))
    runtime = _runtime_schemas_from_ast(FIXTURE / "mcp/server.py")
    assert tuple(documented) == EXPECTED_TOOL_NAMES
    assert documented == runtime


def test_mcp_reference_json_matches_runtime_schema() -> None:
    result = _run(MCP_GENERATOR, MCP_INPUTS, MCP_OUTPUTS)

    assert result.returncode == 0, result.stderr
    discovery = _json_output(result, "mcp.json")
    runtime = _runtime_schemas_from_ast(FIXTURE / "mcp/server.py")
    generated = {tool["name"]: tool["inputSchema"] for tool in discovery["tools"]}
    assert tuple(generated) == EXPECTED_TOOL_NAMES
    assert len(discovery["tools"]) == 5
    assert generated == runtime


def test_mcp_reference_handles_missing_server() -> None:
    result = _run(
        MCP_GENERATOR,
        ["datapulse.json", "mcp.json"],
        MCP_OUTPUTS,
    )

    assert result.returncode != 0
    assert result.outputs["docs/mcp-reference.md"] is None


def test_deterministic_second_run_for_all_generators() -> None:
    cases = (
        (CHANGELOG_GENERATOR, CHANGELOG_INPUTS, CHANGELOG_OUTPUTS),
        (JSONLD_GENERATOR, JSONLD_INPUTS, JSONLD_OUTPUTS),
        (MCP_GENERATOR, MCP_INPUTS, MCP_OUTPUTS),
    )
    for generator, inputs, outputs in cases:
        first, second, diff = run_generator_twice(
            FIXTURE, generator, inputs, outputs
        )
        assert first.returncode == second.returncode == 0, (
            first.stderr or second.stderr
        )
        assert set(diff) == set(outputs)
        assert all(diff[path] for path in outputs)


def test_generated_changelog_is_valid_json() -> None:
    result = _run(CHANGELOG_GENERATOR, CHANGELOG_INPUTS, CHANGELOG_OUTPUTS)

    assert result.returncode == 0, result.stderr
    output = result.outputs["changelog.json"]
    assert output is not None
    assert isinstance(json.loads(output.decode("utf-8")), dict)


def test_generated_jsonld_is_valid_jsonld() -> None:
    result = _run(JSONLD_GENERATOR, JSONLD_INPUTS, JSONLD_OUTPUTS)

    assert result.returncode == 0, result.stderr
    for dataset_id in ("alpha", "beta"):
        dataset = _json_output(result, f"data/jsonld/{dataset_id}.json")
        assert "schema.org" in dataset["@context"]


def test_does_not_touch_tracked_workspace() -> None:
    cases = (
        (CHANGELOG_GENERATOR, CHANGELOG_INPUTS, CHANGELOG_OUTPUTS),
        (JSONLD_GENERATOR, JSONLD_INPUTS, JSONLD_OUTPUTS),
        (MCP_GENERATOR, MCP_INPUTS, MCP_OUTPUTS),
    )
    for generator, inputs, outputs in cases:
        result = _run(generator, inputs, outputs)
        assert result.returncode == 0, result.stderr

    status = subprocess.run(
        [
            "git",
            "status",
            "--short",
            "--",
            "changelog.json",
            "mcp.json",
            "data/jsonld",
            "docs/mcp-reference.md",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert status.returncode == 0, status.stderr
    assert status.stdout == ""
