"""Preflight and manifest helpers for external ADMIXTOOLS qpAdm runs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from indoeuropop.data.aadr_curation import load_aadr_group_selections

_GENOTYPE_EXTENSIONS = (".geno", ".snp", ".ind")


@dataclass(frozen=True)
class QpAdmRunConfig:
    """Paths needed to run the external qpAdm script reproducibly.

    The Python package does not import ADMIXTOOLS or execute qpAdm directly.
    This config records the exact genotype prefix, target group list, output
    estimate CSV, f2-statistics directory, and R runner path needed by the
    external command.
    """

    genotype_prefix: Path
    target_groups_path: Path
    output_csv_path: Path
    f2_dir: Path
    runner_script_path: Path = Path("scripts/run_qpadm.R")

    def __post_init__(self) -> None:
        """Validate required qpAdm run paths and target rows."""
        _require_genotype_files(self.genotype_prefix)
        _require_file(self.target_groups_path, "target_groups_path")
        _require_file(self.runner_script_path, "runner_script_path")
        load_aadr_group_selections(self.target_groups_path)
        if not self.output_csv_path.name:
            raise ValueError("output_csv_path must name an output file")
        if not self.f2_dir.name:
            raise ValueError("f2_dir must name a directory")


def resolve_qpadm_genotype_prefix(path: str | Path) -> Path:
    """Resolve a qpAdm genotype prefix from a prefix path or directory.

    A prefix is the shared basename for `.geno`, `.snp`, and `.ind` files. When
    a directory is supplied, the first `.geno` file whose name contains `1240`
    is preferred, matching the AADR 1240K use case.
    """
    candidate = Path(path)
    if _has_genotype_files(candidate):
        return candidate
    search_dir = candidate if candidate.is_dir() else candidate.parent
    if not search_dir.is_dir():
        raise ValueError(f"genotype search directory does not exist: {search_dir}")
    geno_paths = sorted(search_dir.glob("*.geno"))
    if not geno_paths:
        raise ValueError(f"no .geno files found in genotype directory: {search_dir}")
    preferred = tuple(path for path in geno_paths if "1240" in path.name.lower())
    for geno_path in (*preferred, *geno_paths):
        prefix = geno_path.with_suffix("")
        if _has_genotype_files(prefix):
            return prefix
    raise ValueError(f"no complete .geno/.snp/.ind set found in {search_dir}")


def qpadm_run_command(config: QpAdmRunConfig) -> tuple[str, ...]:
    """Return the shell-safe command tuple for the external qpAdm run."""
    return (
        "Rscript",
        str(config.runner_script_path),
        "--prefix",
        str(config.genotype_prefix),
        "--targets",
        str(config.target_groups_path),
        "--out",
        str(config.output_csv_path),
        "--f2dir",
        str(config.f2_dir),
    )


def qpadm_run_manifest(config: QpAdmRunConfig) -> dict[str, object]:
    """Return a JSON-ready manifest describing an external qpAdm run."""
    selections = load_aadr_group_selections(config.target_groups_path)
    return {
        "kind": "external_qpadm_run",
        "command": list(qpadm_run_command(config)),
        "genotype_prefix": str(config.genotype_prefix),
        "target_groups_path": str(config.target_groups_path),
        "target_group_count": len(selections),
        "regions": sorted({selection.region for selection in selections}),
        "output_csv_path": str(config.output_csv_path),
        "f2_dir": str(config.f2_dir),
        "runner_script_path": str(config.runner_script_path),
        "note": (
            "Run this command outside the Python test suite with system R and "
            "ADMIXTOOLS 2 installed; then convert the output with "
            "load-qpadm-estimates."
        ),
    }


def write_qpadm_run_manifest(config: QpAdmRunConfig, path: str | Path) -> Path:
    """Write a qpAdm run manifest JSON file and return the path."""
    manifest_path = Path(path)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(qpadm_run_manifest(config), indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest_path


def _require_genotype_files(prefix: Path) -> None:
    """Raise if a genotype prefix does not have all required files."""
    if not _has_genotype_files(prefix):
        raise ValueError(f"genotype_prefix is incomplete: {prefix}")


def _has_genotype_files(prefix: Path) -> bool:
    """Return whether all EIGENSTRAT genotype files exist for a prefix."""
    return all(
        _genotype_file(prefix, extension).is_file()
        for extension in _GENOTYPE_EXTENSIONS
    )


def _genotype_file(prefix: Path, extension: str) -> Path:
    """Return one genotype file path by appending an EIGENSTRAT extension."""
    return Path(f"{prefix}{extension}")


def _require_file(path: Path, field_name: str) -> None:
    """Raise if a required path is not an existing file."""
    if not path.is_file():
        raise ValueError(f"{field_name} must point to an existing file: {path}")
