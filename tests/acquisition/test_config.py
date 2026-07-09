"""Tests for load_config: YAML parsing, env-var override, and error paths."""

import os
from pathlib import Path

import pytest

from soaring.acquisition.ffvl.config import Config, HttpConfig, load_config

# A dedicated env var name so the tests never touch the real SOARING_*_DATA_ROOT.
ENV = "SOARING_TEST_DATA_ROOT"

_FULL_YAML = """\
data_root: /data/from/file
seasons:
  start: 2001
  end: 2020
source:
  base_url: https://example.invalid
  list_path: /cfd/liste/{year}
  xml_query: "?xml=1"
http:
  impersonate: safari
  workers: 8
  timeout_s: 45
  max_retries: 3
  backoff_base_s: 1.5
  min_delay_s: 0.1
"""

# Minimal file: no data_root, no http block (the env var must supply data_root and
# HttpConfig must fall back to its defaults).
_MINIMAL_YAML = """\
seasons:
  start: 2001
  end: 2002
source:
  base_url: https://x.invalid
"""


def _write(tmp_path: Path, text: str) -> Path:
    p = tmp_path / "cfg.yaml"
    p.write_text(text, encoding="utf-8")
    return p


def test_parses_all_fields_with_correct_types(tmp_path, monkeypatch):
    monkeypatch.delenv(ENV, raising=False)
    cfg = load_config(_write(tmp_path, _FULL_YAML), data_root_env=ENV)

    assert isinstance(cfg, Config)
    assert cfg.data_root == Path("/data/from/file")
    assert cfg.season_start == 2001
    assert cfg.season_end == 2020
    assert list(cfg.years) == list(range(2001, 2021))
    assert cfg.base_url == "https://example.invalid"
    assert cfg.list_path == "/cfd/liste/{year}"
    assert cfg.xml_query == "?xml=1"

    assert cfg.http.impersonate == "safari"
    assert cfg.http.workers == 8 and isinstance(cfg.http.workers, int)
    assert cfg.http.timeout_s == 45.0 and isinstance(cfg.http.timeout_s, float)
    assert cfg.http.max_retries == 3
    assert cfg.http.backoff_base_s == 1.5
    assert cfg.http.min_delay_s == 0.1


def test_env_var_overrides_file_data_root(tmp_path, monkeypatch):
    monkeypatch.setenv(ENV, "/data/from/env")
    cfg = load_config(_write(tmp_path, _FULL_YAML), data_root_env=ENV)
    assert cfg.data_root == Path("/data/from/env")  # env wins over the file value


def test_env_var_supplies_data_root_when_file_lacks_it(tmp_path, monkeypatch):
    monkeypatch.setenv(ENV, "/data/from/env")
    cfg = load_config(_write(tmp_path, _MINIMAL_YAML), data_root_env=ENV)
    assert cfg.data_root == Path("/data/from/env")


def test_source_and_http_defaults_when_omitted(tmp_path, monkeypatch):
    monkeypatch.setenv(ENV, "/d")
    cfg = load_config(_write(tmp_path, _MINIMAL_YAML), data_root_env=ENV)
    assert cfg.list_path == "/cfd/liste/{year}"
    assert cfg.xml_query == "?xml=1"
    assert cfg.http == HttpConfig()  # whole http block omitted -> dataclass defaults


def test_data_root_expands_env_vars(tmp_path, monkeypatch):
    monkeypatch.setenv(ENV, "$HOME/archives/igc")
    cfg = load_config(_write(tmp_path, _MINIMAL_YAML), data_root_env=ENV)
    assert "$" not in str(cfg.data_root)
    assert cfg.data_root == Path(os.path.expandvars("$HOME/archives/igc"))


def test_data_root_expands_user_home(tmp_path, monkeypatch):
    # _expand also runs expanduser: exercise the '~' branch, not just $VAR.
    monkeypatch.setenv(ENV, "~/archives/igc")
    cfg = load_config(_write(tmp_path, _MINIMAL_YAML), data_root_env=ENV)
    assert "~" not in str(cfg.data_root)
    assert cfg.data_root == Path("~/archives/igc").expanduser()


def test_missing_file_raises_filenotfound(tmp_path, monkeypatch):
    monkeypatch.delenv(ENV, raising=False)
    with pytest.raises(FileNotFoundError):
        load_config(tmp_path / "does-not-exist.yaml", data_root_env=ENV)


def test_missing_data_root_raises_keyerror(tmp_path, monkeypatch):
    monkeypatch.delenv(ENV, raising=False)  # neither file nor env provides it
    with pytest.raises(KeyError):
        load_config(_write(tmp_path, _MINIMAL_YAML), data_root_env=ENV)
