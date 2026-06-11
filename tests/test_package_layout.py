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
        "child_region_overrides": "indoeuropop.orchestration.child_region_overrides",
        "cli": "indoeuropop.orchestration.cli",
        "config": "indoeuropop.simulation.config",
        "curation_decisions": "indoeuropop.data.curation_decisions",
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
        "refinement": "indoeuropop.analysis.refinement",
        "qpadm_cli": "indoeuropop.orchestration.qpadm_cli",
        "qpadm_estimates": "indoeuropop.data.qpadm_estimates",
        "qpadm_rerun_ingestion": "indoeuropop.data.qpadm_rerun_ingestion",
        "qpadm_rerun_models": "indoeuropop.data.qpadm_rerun_models",
        "qpadm_rerun_report": "indoeuropop.reporting.qpadm_rerun_report",
        "qpadm_reruns": "indoeuropop.data.qpadm_reruns",
        "qpadm_workflow": "indoeuropop.data.qpadm_workflow",
        "override_delta": "indoeuropop.reporting.override_delta",
        "override_delta_workflow": "indoeuropop.orchestration.override_delta",
        "override_sensitivity": "indoeuropop.analysis.override_sensitivity",
        "override_sensitivity_candidates": (
            "indoeuropop.analysis.override_sensitivity_candidates"
        ),
        "override_sensitivity_report": "indoeuropop.reporting.override_sensitivity",
        "override_sensitivity_workflow": (
            "indoeuropop.orchestration.override_sensitivity"
        ),
        "report_cli": "indoeuropop.orchestration.report_cli",
        "reproducibility": "indoeuropop.reporting.reproducibility",
        "sample_metadata": "indoeuropop.data.sample_metadata",
        "sensitivity": "indoeuropop.analysis.sensitivity",
        "sex_bias": "indoeuropop.models.sex_bias",
        "source_downloader": "indoeuropop.data.source_downloader",
        "summary": "indoeuropop.analysis.summary",
        "summary_statistics": "indoeuropop.analysis.summary_statistics",
        "sweep_reporting": "indoeuropop.reporting.sweep_reporting",
        "sweep_config_export": "indoeuropop.orchestration.sweep_config_export",
        "sweep_workflows": "indoeuropop.orchestration.sweep_workflows",
        "sweeps": "indoeuropop.orchestration.sweeps",
        "target_audit": "indoeuropop.reporting.target_audit",
        "target_audit_report": "indoeuropop.reporting.target_audit_report",
        "target_cli": "indoeuropop.orchestration.target_cli",
        "target_comparison": "indoeuropop.orchestration.target_comparison",
        "target_curation": "indoeuropop.data.target_curation",
        "target_decision_cli": "indoeuropop.orchestration.target_decision_cli",
        "target_decisions": "indoeuropop.data.target_decisions",
        "target_notes": "indoeuropop.data.target_notes",
        "target_pipeline": "indoeuropop.data.target_pipeline",
        "target_refinement": "indoeuropop.orchestration.target_refinement",
        "target_refinement_report": "indoeuropop.reporting.target_refinement",
        "target_review": "indoeuropop.reporting.target_review",
        "target_structure": "indoeuropop.orchestration.target_structure",
        "target_validation": "indoeuropop.orchestration.target_validation",
        "target_validation_report": "indoeuropop.reporting.target_validation",
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
    assert "QpAdmRerunIngestionConfig" in public_api.__all__
    assert "qpadm_rerun_report_markdown" in public_api.__all__
    assert "run_target_validation_workflow" in public_api.__all__
    assert "target_validation_markdown" in public_api.__all__
    assert "run_target_refinement_workflow" in public_api.__all__
    assert "target_refinement_markdown" in public_api.__all__
    assert "target_note_metadata" in public_api.__all__
    assert "run_target_structure_workflow" in public_api.__all__
    assert "sweep_spec_to_toml" in public_api.__all__
    assert "load_child_region_overrides" in public_api.__all__
    assert "apply_child_region_overrides" in public_api.__all__
    assert "load_override_delta_report" in public_api.__all__
    assert "run_override_delta_workflow" in public_api.__all__
    assert "run_child_override_sensitivity_workflow" in public_api.__all__
    assert "child_override_count_reproduction_interaction_candidates" in (
        public_api.__all__
    )
    assert "override_sensitivity_markdown" in public_api.__all__
    assert "validate_curation_decision_files" in public_api.__all__
    assert "CurationDecisionValidationReport" in public_api.__all__


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
