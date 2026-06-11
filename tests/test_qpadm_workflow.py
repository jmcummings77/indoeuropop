"""Tests for planning external ADMIXTOOLS qpAdm runs."""

import json
from pathlib import Path

import pytest

from indoeuropop.qpadm_workflow import (
    QpAdmRunConfig,
    qpadm_run_command,
    qpadm_run_manifest,
    resolve_qpadm_genotype_prefix,
    write_qpadm_run_manifest,
)


def _write_genotype_set(prefix: Path) -> Path:
    """Write a tiny EIGENSTRAT-shaped genotype trio for path tests."""
    Path(f"{prefix}.geno").write_text("0\n", encoding="utf-8")
    Path(f"{prefix}.snp").write_text("rs1 1 0.0 1 A G\n", encoding="utf-8")
    Path(f"{prefix}.ind").write_text("I001 F Group\n", encoding="utf-8")
    return prefix


def _write_targets(path: Path) -> Path:
    """Write a minimal qpAdm target group file."""
    path.write_text(
        "region\taadr_group_id\nbritain\tEngland_BellBeaker\n", encoding="utf-8"
    )
    return path


def _write_runner(path: Path) -> Path:
    """Write a tiny runner placeholder for manifest tests."""
    path.write_text("#!/usr/bin/env Rscript\n", encoding="utf-8")
    return path


def test_resolve_qpadm_genotype_prefix_accepts_direct_prefix(tmp_path: Path) -> None:
    """A complete genotype prefix should resolve directly."""
    prefix = _write_genotype_set(tmp_path / "tiny")

    assert resolve_qpadm_genotype_prefix(prefix) == prefix


def test_resolve_qpadm_genotype_prefix_accepts_dotted_prefix(tmp_path: Path) -> None:
    """AADR prefixes can contain dots before the genotype extension."""
    prefix = _write_genotype_set(tmp_path / "v66.p1_1240K.aadr.patch.PUB")

    assert resolve_qpadm_genotype_prefix(prefix) == prefix


def test_resolve_qpadm_genotype_prefix_prefers_1240k_files(tmp_path: Path) -> None:
    """Directory resolution should prefer 1240K-looking genotype prefixes."""
    _write_genotype_set(tmp_path / "other")
    preferred = _write_genotype_set(tmp_path / "v66_1240K_public")

    assert resolve_qpadm_genotype_prefix(tmp_path) == preferred


def test_resolve_qpadm_genotype_prefix_rejects_missing_inputs(tmp_path: Path) -> None:
    """Missing or incomplete genotype inputs should fail before qpAdm runs."""
    with pytest.raises(ValueError, match="search directory"):
        resolve_qpadm_genotype_prefix(tmp_path / "missing" / "prefix")

    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    with pytest.raises(ValueError, match=r"no \.geno"):
        resolve_qpadm_genotype_prefix(empty_dir)

    incomplete = tmp_path / "incomplete"
    incomplete.mkdir()
    (incomplete / "bad.geno").write_text("0\n", encoding="utf-8")
    with pytest.raises(ValueError, match="no complete"):
        resolve_qpadm_genotype_prefix(incomplete)


def test_qpadm_run_config_builds_command_and_manifest(tmp_path: Path) -> None:
    """A valid qpAdm run config should produce an auditable command."""
    config = QpAdmRunConfig(
        genotype_prefix=_write_genotype_set(tmp_path / "tiny"),
        target_groups_path=_write_targets(tmp_path / "targets.tsv"),
        output_csv_path=tmp_path / "steppe-estimates.csv",
        f2_dir=tmp_path / "f2",
        runner_script_path=_write_runner(tmp_path / "run_qpadm.R"),
    )
    manifest_path = tmp_path / "manifests" / "qpadm.json"

    command = qpadm_run_command(config)
    manifest = qpadm_run_manifest(config)
    returned_path = write_qpadm_run_manifest(config, manifest_path)
    loaded_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert command[:3] == ("Rscript", str(config.runner_script_path), "--prefix")
    assert manifest["target_group_count"] == 1
    assert manifest["regions"] == ["britain"]
    assert loaded_manifest["command"] == list(command)
    assert returned_path == manifest_path


def test_qpadm_run_config_rejects_invalid_paths(tmp_path: Path) -> None:
    """The qpAdm plan should reject missing files and vague output paths."""
    prefix = _write_genotype_set(tmp_path / "tiny")
    targets = _write_targets(tmp_path / "targets.tsv")
    runner = _write_runner(tmp_path / "run_qpadm.R")

    with pytest.raises(ValueError, match="genotype_prefix"):
        QpAdmRunConfig(
            genotype_prefix=tmp_path / "missing",
            target_groups_path=targets,
            output_csv_path=tmp_path / "out.csv",
            f2_dir=tmp_path / "f2",
            runner_script_path=runner,
        )
    with pytest.raises(ValueError, match="target_groups_path"):
        QpAdmRunConfig(
            genotype_prefix=prefix,
            target_groups_path=tmp_path / "missing.tsv",
            output_csv_path=tmp_path / "out.csv",
            f2_dir=tmp_path / "f2",
            runner_script_path=runner,
        )
    with pytest.raises(ValueError, match="runner_script_path"):
        QpAdmRunConfig(
            genotype_prefix=prefix,
            target_groups_path=targets,
            output_csv_path=tmp_path / "out.csv",
            f2_dir=tmp_path / "f2",
            runner_script_path=tmp_path / "missing.R",
        )
    with pytest.raises(ValueError, match="output_csv_path"):
        QpAdmRunConfig(
            genotype_prefix=prefix,
            target_groups_path=targets,
            output_csv_path=Path(""),
            f2_dir=tmp_path / "f2",
            runner_script_path=runner,
        )
    with pytest.raises(ValueError, match="f2_dir"):
        QpAdmRunConfig(
            genotype_prefix=prefix,
            target_groups_path=targets,
            output_csv_path=tmp_path / "out.csv",
            f2_dir=Path(""),
            runner_script_path=runner,
        )
