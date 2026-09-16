"""A task split must align by flight identity and exclude unidentified geometry."""

import runpy
from pathlib import Path

import pandas as pd
import pytest


@pytest.fixture
def attach_tasks(monkeypatch):
    scripts = (
        Path(__file__).resolve().parents[2] / "scripts/reporting/ch3_global_transport"
    )
    monkeypatch.syspath_prepend(str(scripts))
    return runpy.run_path(str(scripts / "generate_altitude_hurst.py"))[
        "attach_declared_tasks"
    ]


def test_task_join_preserves_flight_order_and_original_index(attach_tasks):
    members = pd.DataFrame(
        {"flight_id": ["30", "10", "20"], "cluster": [7, 5, 6]}, index=[8, 2, 9]
    )
    catalog = pd.DataFrame(
        {
            "flight_id": [10, 20, 30],
            "flight_type": ["Dist 3 pts", "Marche et Vol", "triangle FAI"],
        }
    )
    result = attach_tasks(members, catalog)
    assert result.flight_id.tolist() == ["30", "10", "20"]
    assert result.index.tolist() == [8, 2, 9]
    assert result.cluster.tolist() == [7, 5, 6]
    assert result.task.tolist() == ["closed", "open", "unknown"]
    assert "task" not in members


def test_missing_catalog_entry_is_unknown_not_open(attach_tasks):
    members = pd.DataFrame({"flight_id": ["missing", "known"]})
    catalog = pd.DataFrame({"flight_id": ["known"], "flight_type": ["Aller-Retour"]})
    result = attach_tasks(members, catalog)
    assert result.task.tolist() == ["unknown", "closed"]
    assert result.missing_catalog_task.tolist() == [True, False]


@pytest.mark.parametrize("duplicate", ["members", "catalog"])
def test_duplicate_flight_id_cannot_expand_or_reassign_curves(attach_tasks, duplicate):
    members = pd.DataFrame({"flight_id": ["one"]})
    catalog = pd.DataFrame({"flight_id": ["one"], "flight_type": ["Dist libre"]})
    if duplicate == "members":
        members = pd.concat([members, members])
    else:
        catalog = pd.concat([catalog, catalog])
    with pytest.raises(ValueError, match="unique flight"):
        attach_tasks(members, catalog)
