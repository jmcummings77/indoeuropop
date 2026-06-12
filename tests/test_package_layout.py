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
        "abc_smc": "indoeuropop.analysis.abc_smc",
        "abc_smc_report": "indoeuropop.reporting.abc_smc",
        "abc_smc_workflow": "indoeuropop.orchestration.abc_smc",
        "age_structure": "indoeuropop.models.age_structure",
        "ancestry_estimates": "indoeuropop.data.ancestry_estimates",
        "child_region_candidates": "indoeuropop.analysis.child_region_candidates",
        "child_region_candidate_report": (
            "indoeuropop.reporting.child_region_candidates"
        ),
        "child_region_candidate_workflow": (
            "indoeuropop.orchestration.child_region_candidates"
        ),
        "child_region_overrides": "indoeuropop.orchestration.child_region_overrides",
        "cli": "indoeuropop.orchestration.cli",
        "config": "indoeuropop.simulation.config",
        "curation_decision_cli": "indoeuropop.orchestration.curation_decision_cli",
        "curation_decisions": "indoeuropop.data.curation_decisions",
        "data_cli": "indoeuropop.orchestration.data_cli",
        "data_sources": "indoeuropop.data.data_sources",
        "debugging": "indoeuropop.analysis.debugging",
        "disagreement_target_audit": (
            "indoeuropop.reporting.disagreement_target_audit"
        ),
        "disagreement_target_audit_models": (
            "indoeuropop.reporting.disagreement_target_audit_models"
        ),
        "disagreement_target_audit_report": (
            "indoeuropop.reporting.disagreement_target_audit_report"
        ),
        "diagnostics": "indoeuropop.analysis.diagnostics",
        "emulator_training": "indoeuropop.analysis.emulator_training",
        "emulator_validation": "indoeuropop.analysis.emulator_validation",
        "epidemics": "indoeuropop.simulation.epidemics",
        "events": "indoeuropop.simulation.events",
        "experiments": "indoeuropop.orchestration.experiments",
        "fitting": "indoeuropop.analysis.fitting",
        "inference": "indoeuropop.analysis.inference",
        "inference_cli": "indoeuropop.orchestration.inference_cli",
        "inference_report": "indoeuropop.reporting.inference",
        "inference_workflow": "indoeuropop.orchestration.inference",
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
        "real_pipeline_refresh": "indoeuropop.orchestration.real_pipeline_refresh",
        "real_pipeline_refresh_cli": (
            "indoeuropop.orchestration.real_pipeline_refresh_cli"
        ),
        "override_delta": "indoeuropop.reporting.override_delta",
        "override_delta_workflow": "indoeuropop.orchestration.override_delta",
        "posterior_predictive": "indoeuropop.analysis.posterior_predictive",
        "posterior_predictive_report": "indoeuropop.reporting.posterior_predictive",
        "structural_candidate_cli": (
            "indoeuropop.orchestration.structural_candidate_cli"
        ),
        "structural_candidate_report": "indoeuropop.reporting.structural_candidates",
        "structural_candidate_workflow": (
            "indoeuropop.orchestration.structural_candidates"
        ),
        "structural_candidates": "indoeuropop.analysis.structural_candidates",
        "structural_head_to_head": "indoeuropop.analysis.structural_head_to_head",
        "structural_head_to_head_cli": (
            "indoeuropop.orchestration.structural_head_to_head_cli"
        ),
        "structural_head_to_head_outputs": (
            "indoeuropop.orchestration.structural_head_to_head_outputs"
        ),
        "structural_head_to_head_report": (
            "indoeuropop.reporting.structural_head_to_head"
        ),
        "structural_head_to_head_workflow": (
            "indoeuropop.orchestration.structural_head_to_head"
        ),
        "structural_smc_cli": "indoeuropop.orchestration.structural_smc_cli",
        "structural_smc_disagreement_report": (
            "indoeuropop.reporting.structural_smc_disagreements"
        ),
        "structural_smc_uncertainty_report": (
            "indoeuropop.reporting.structural_smc_uncertainty"
        ),
        "structural_smc_outputs": ("indoeuropop.orchestration.structural_smc_outputs"),
        "structural_smc_report": "indoeuropop.reporting.structural_smc",
        "structural_smc_uncertainty_cli": (
            "indoeuropop.orchestration.structural_smc_uncertainty_cli"
        ),
        "structural_smc_validation": (
            "indoeuropop.orchestration.structural_smc_validation_models"
        ),
        "structural_smc_validation_cli": (
            "indoeuropop.orchestration.structural_smc_validation_cli"
        ),
        "structural_smc_validation_outputs": (
            "indoeuropop.orchestration.structural_smc_validation_outputs"
        ),
        "structural_smc_validation_report": (
            "indoeuropop.reporting.structural_smc_validation"
        ),
        "structural_smc_validation_workflow": (
            "indoeuropop.orchestration.structural_smc_validation"
        ),
        "structural_smc_workflow": "indoeuropop.orchestration.structural_smc",
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
        "target_fragility": "indoeuropop.orchestration.target_fragility",
        "target_fragility_models": "indoeuropop.orchestration.target_fragility_models",
        "target_fragility_report": "indoeuropop.reporting.target_fragility",
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
    assert "load_real_pipeline_readiness" in public_api.__all__
    assert "real_pipeline_readiness_markdown" in public_api.__all__
    assert "RealPipelineReadinessReport" in public_api.__all__
    assert "ABCRejectionOptions" in public_api.__all__
    assert "run_abc_rejection_workflow" in public_api.__all__
    assert "abc_rejection_markdown" in public_api.__all__
    assert "ABCSMCOptions" in public_api.__all__
    assert "run_abc_smc_workflow" in public_api.__all__
    assert "abc_smc_markdown" in public_api.__all__
    assert "PosteriorPredictiveDiagnostics" in public_api.__all__
    assert "posterior_predictive_diagnostics" in public_api.__all__
    assert "posterior_predictive_markdown" in public_api.__all__
    assert "MigrationPulseCandidate" in public_api.__all__
    assert "run_migration_pulse_candidate_workflow" in public_api.__all__
    assert "migration_pulse_candidate_markdown" in public_api.__all__
    assert "ChildRegionCandidate" in public_api.__all__
    assert "run_child_region_candidate_workflow" in public_api.__all__
    assert "child_region_candidate_markdown" in public_api.__all__
    assert "StructuredPulseCandidate" in public_api.__all__
    assert "run_structured_head_to_head_workflow" in public_api.__all__
    assert "structured_head_to_head_markdown" in public_api.__all__
    assert "RealPipelineRefreshPaths" in public_api.__all__
    assert "run_real_pipeline_refresh_workflow" in public_api.__all__
    assert "StructuralSMCOutputPaths" in public_api.__all__
    assert "run_structural_smc_head_to_head_workflow" in public_api.__all__
    assert "structural_smc_markdown" in public_api.__all__
    assert "StructuralSMCValidationFoldSpec" in public_api.__all__
    assert "run_structural_smc_multifold_validation_workflow" in public_api.__all__
    assert "structural_smc_validation_markdown" in public_api.__all__
    assert "StructuralSMCDisagreementReport" in public_api.__all__
    assert "load_structural_smc_disagreement_report" in public_api.__all__
    assert "structural_smc_disagreement_markdown" in public_api.__all__
    assert "DisagreementTargetCurationAuditReport" in public_api.__all__
    assert "load_disagreement_target_curation_audit" in public_api.__all__
    assert "disagreement_target_audit_markdown" in public_api.__all__
    assert "StructuralSMCUncertaintyReport" in public_api.__all__
    assert "load_structural_smc_uncertainty_report" in public_api.__all__
    assert "structural_smc_uncertainty_markdown" in public_api.__all__
    assert "TargetFragilityDecision" in public_api.__all__
    assert "run_structural_smc_target_fragility_gate" in public_api.__all__
    assert "target_fragility_gate_markdown" in public_api.__all__


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
