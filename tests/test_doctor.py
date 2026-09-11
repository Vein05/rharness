import json, os
from conftest import run_cli


def _fake_bin(tmp_path, *names):
    b = tmp_path / "fakebin"; b.mkdir(exist_ok=True)
    for n in names:
        f = b / n; f.write_text("#!/bin/sh\necho 0.0\n"); f.chmod(0o755)
    return str(b)


def test_doctor_outside_workspace_reports_toolchain(tmp_path, home):
    code, out, err = run_cli(["doctor"], cwd=tmp_path)
    assert code == 1
    assert "python" in out and "git" in out
    assert "workspace" in out.lower()


def test_doctor_passes_with_rtk_hook(ws, tmp_path):
    run_cli(["add", "rtk"], cwd=ws)
    path = _fake_bin(tmp_path, "rtk", "jq") + os.pathsep + os.environ["PATH"]
    code, out, err = run_cli(["doctor"], cwd=ws, env={"PATH": path})
    assert code == 0, out
    assert "rtk hook" in out and "ok" in out


def test_doctor_fails_when_hook_removed(ws, tmp_path):
    run_cli(["add", "rtk"], cwd=ws)
    s = ws / ".claude" / "settings.json"
    s.write_text(json.dumps({"hooks": {"PreToolUse": []}}))
    path = _fake_bin(tmp_path, "rtk", "jq") + os.pathsep + os.environ["PATH"]
    code, out, err = run_cli(["doctor"], cwd=ws, env={"PATH": path})
    assert code == 1 and "FAIL" in out and "rtk hook" in out


def test_doctor_fails_when_rtk_binary_missing(ws, tmp_path):
    run_cli(["add", "rtk"], cwd=ws)
    path = _fake_bin(tmp_path, "git", "git-lfs", "jq", "python3")
    code, out, err = run_cli(["doctor"], cwd=ws, env={"PATH": path})
    assert code == 1 and any("rtk binary" in l and "FAIL" in l for l in out.splitlines())


def test_doctor_optional_tools_are_notes_not_failures(ws, tmp_path):
    path = _fake_bin(tmp_path, "git", "git-lfs", "python3")
    code, out, err = run_cli(["doctor"], cwd=ws, env={"PATH": path})
    lines = out.splitlines()
    for tool in ("latexmk", "pdflatex", "pdfinfo", "pdftotext"):
        line = next(l for l in lines if l.split(":")[0].strip().endswith(tool))
        assert line.startswith("note"), line
    assert not any(l.startswith("FAIL") and ("latexmk" in l or "pdfinfo" in l) for l in lines)
    assert "TinyTeX" in out and "Overleaf" in out


def test_doctor_optional_tools_present_are_ok(ws, tmp_path):
    path = _fake_bin(tmp_path, "git", "git-lfs", "python3", "latexmk", "pdflatex", "pdfinfo", "pdftotext")
    code, out, err = run_cli(["doctor"], cwd=ws, env={"PATH": path})
    assert code == 0, out
    assert any(l.startswith("ok") and l.split(":")[0].strip().endswith("latexmk") for l in out.splitlines())
