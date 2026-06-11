"""Package organization and compatibility import tests."""

from importlib import import_module


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
        "target_curation": "indoeuropop.data.target_curation",
        "target_pipeline": "indoeuropop.data.target_pipeline",
        "targets": "indoeuropop.data.targets",
        "validation": "indoeuropop.analysis.validation",
        "visualization": "indoeuropop.reporting.visualization",
        "workflows": "indoeuropop.orchestration.workflows",
    }

    for module_name, expected_name in expected_modules.items():
        imported_module = import_module(f"indoeuropop.{module_name}")

        assert imported_module.__name__ == expected_name
