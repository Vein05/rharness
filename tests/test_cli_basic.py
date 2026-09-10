from conftest import run_cli, REPO


def test_version_prints_version_file(tmp_path):
    code, out, err = run_cli(["version"], cwd=tmp_path)
    assert code == 0
    assert out.strip() == (REPO / "VERSION").read_text().strip()


def test_no_args_prints_usage_and_exits_2(tmp_path):
    code, out, err = run_cli([], cwd=tmp_path)
    assert code == 2
    assert "usage" in (out + err).lower()
