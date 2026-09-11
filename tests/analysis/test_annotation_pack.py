import pytest

from soaring.analysis.segmentation.pack import (
    PACK_INPUTS,
    SOURCE_INPUTS,
    validate_pack_provenance,
    write_pack_provenance,
)


def _pack(tmp_path):
    pack = tmp_path / "pack"
    derived = tmp_path / "archive"
    pack.mkdir()
    for name in PACK_INPUTS:
        (pack / name).write_text("immutable candidate data")
    for name in SOURCE_INPUTS:
        path = derived / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("source data")
    write_pack_provenance(pack, {"test": derived})
    return pack, derived


def test_pack_provenance_preserves_editable_labels_and_offline_use(tmp_path):
    pack, derived = _pack(tmp_path)
    (pack / "phase_annotations.csv").write_text("new human labels")
    assert validate_pack_provenance(pack) == []
    derived.rename(tmp_path / "unmounted")
    assert validate_pack_provenance(pack) == ["test"]


def test_pack_refuses_changed_cleaning_source(tmp_path):
    pack, derived = _pack(tmp_path)
    (derived / "fixes.parquet").write_text("new cleaning, different processed clock")
    with pytest.raises(ValueError, match="changed since"):
        validate_pack_provenance(pack)


def test_pack_refuses_changed_candidate_windows(tmp_path):
    pack, _ = _pack(tmp_path)
    (pack / "annotation_windows.csv").write_text("new window bounds")
    with pytest.raises(ValueError, match="changed after"):
        validate_pack_provenance(pack)


def test_calibrating_model_and_predictions_keeps_blinded_pack_valid(tmp_path):
    pack, derived = _pack(tmp_path)
    (derived / "segmentation/phase_points.parquet").write_text("new phase predictions")
    (derived / "segmentation/model/metadata.json").write_text("new semantic mapping")
    assert validate_pack_provenance(pack) == []
