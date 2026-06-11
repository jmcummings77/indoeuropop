"""Public package exports and legacy module import aliases."""

import sys
from importlib import import_module

from indoeuropop._api import *  # noqa: F403
from indoeuropop._api import __all__ as __all__

_COMPATIBILITY_MODULES: dict[str, str] = {
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
    "qpadm_cli": "indoeuropop.orchestration.qpadm_cli",
    "qpadm_estimates": "indoeuropop.data.qpadm_estimates",
    "qpadm_reruns": "indoeuropop.data.qpadm_reruns",
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
    "target_comparison": "indoeuropop.orchestration.target_comparison",
    "target_audit": "indoeuropop.reporting.target_audit",
    "target_audit_report": "indoeuropop.reporting.target_audit_report",
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

for _module_name, _implementation_name in _COMPATIBILITY_MODULES.items():
    sys.modules[f"{__name__}.{_module_name}"] = import_module(_implementation_name)
