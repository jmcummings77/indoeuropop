"""Package organization and compatibility import tests."""

from importlib import import_module
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_FILE_LINE_LIMIT = 400
TEST_AND_DOC_FILE_LINE_LIMIT = 1000


def test_legacy_module_names_resolve_to_new_subpackages() -> None:
    """Import historical module paths through their organized implementations."""

    expected_modules = {
        "aadr": "indoeuropop.data.aadr",
        "aadr_curation": "indoeuropop.data.aadr_curation",
        "aadr_groups": "indoeuropop.data.aadr_groups",
        "age_structure": "indoeuropop.models.age_structure",
        "ancestry_estimates": "indoeuropop.data.ancestry_estimates",
        "cli": "indoeuropop.orchestration.cli",
        "config": "indoeuropop.simulation.config",
        "data_cli": "indoeuropop.orchestration.data_cli",
        "data_sources": "indoeuropop.data.data_sources",
        "debugging": "indoeuropop.analysis.debugging",
        "diagnostics": "indoeuropop.analysis.diagnostics",
        "emulator_training": "indoeuropop.analysis.emulator_training",
        "emulator_validation": "indoeuropop.analysis.emulator_validation",
        "epidemics": "indoeuropop.simulation.epidemics",
        "events": "indoeuropop.simulation.events",
        "experiments": "indoeuropop.orchestration.experiments",
        "fitting": "indoeuropop.analysis.fitting",
        "parameterization": "indoeuropop.models.parameterization",
        "provenance": "indoeuropop.reporting.provenance",
        "qpadm_estimates": "indoeuropop.data.qpadm_estimates",
        "qpadm_workflow": "indoeuropop.data.qpadm_workflow",
        "report_cli": "indoeuropop.orchestration.report_cli",
        "reproducibility": "indoeuropop.reporting.reproducibility",
        "sample_metadata": "indoeuropop.data.sample_metadata",
        "sensitivity": "indoeuropop.analysis.sensitivity",
        "sex_bias": "indoeuropop.models.sex_bias",
        "source_downloader": "indoeuropop.data.source_downloader",
        "summary": "indoeuropop.analysis.summary",
        "summary_statistics": "indoeuropop.analysis.summary_statistics",
        "sweep_reporting": "indoeuropop.reporting.sweep_reporting",
        "sweep_workflows": "indoeuropop.orchestration.sweep_workflows",
        "sweeps": "indoeuropop.orchestration.sweeps",
        "target_audit": "indoeuropop.reporting.target_audit",
        "target_audit_report": "indoeuropop.reporting.target_audit_report",
        "target_comparison": "indoeuropop.orchestration.target_comparison",
        "target_curation": "indoeuropop.data.target_curation",
        "target_decision_cli": "indoeuropop.orchestration.target_decision_cli",
        "target_decisions": "indoeuropop.data.target_decisions",
        "target_pipeline": "indoeuropop.data.target_pipeline",
        "target_review": "indoeuropop.reporting.target_review",
        "targets": "indoeuropop.data.targets",
        "validation": "indoeuropop.analysis.validation",
        "visualization": "indoeuropop.reporting.visualization",
        "workflows": "indoeuropop.orchestration.workflows",
    }

    for module_name, expected_name in expected_modules.items():
        imported_module = import_module(f"indoeuropop.{module_name}")

        assert imported_module.__name__ == expected_name


def test_public_api_exports_target_decision_helpers() -> None:
    """Expose target-decision helpers through the top-level package."""

    public_api = import_module("indoeuropop")

    assert "TargetDecisionDataset" in public_api.__all__
    assert "apply_target_decisions" in public_api.__all__


def test_project_files_stay_under_line_limits() -> None:
    """Keep source, test, and documentation files within project limits."""

    checked_roots = (
        (PROJECT_ROOT / "src", "*.py", SOURCE_FILE_LINE_LIMIT),
        (PROJECT_ROOT / "tests", "*.py", TEST_AND_DOC_FILE_LINE_LIMIT),
        (PROJECT_ROOT / "docs", "*.md", TEST_AND_DOC_FILE_LINE_LIMIT),
    )
    oversized_files: list[str] = []
    for root, pattern, line_limit in checked_roots:
        for path in root.rglob(pattern):
            line_count = _line_count(path)
            if line_count > line_limit:
                relative_path = path.relative_to(PROJECT_ROOT)
                oversized_files.append(f"{relative_path}: {line_count}>{line_limit}")

    assert oversized_files == []


def _line_count(path: Path) -> int:
    """Return the number of text lines in a project file."""

    return len(path.read_text(encoding="utf-8").splitlines())
