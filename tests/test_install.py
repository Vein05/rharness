import os, subprocess
from conftest import REPO
from test_update import make_tarball


def test_install_sh_with_local_tarball(tmp_path):
    tb = make_tarball(tmp_path, "1.2.3")
    home = tmp_path / "h"; home.mkdir()
    (home / ".zshrc").write_text("# rc\n")
    env = dict(os.environ, HOME=str(home), RHARNESS_HOME=str(home / ".rharness"),
               RHARNESS_VERSION="1.2.3", RHARNESS_TARBALL=str(tb), SHELL="/bin/zsh")
    r = subprocess.run(["sh", str(REPO / "install.sh")], env=env, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr + r.stdout
    shim = home / ".rharness" / "bin" / "rharness"
    assert shim.exists() and os.access(shim, os.X_OK)
    assert (home / ".rharness" / "store" / "current" / "VERSION").read_text().strip() == "1.2.3"
    rc = (home / ".zshrc").read_text()
    assert rc.count("# rharness") == 1 and ".rharness/bin" in rc
    out = subprocess.run([str(shim), "version"], env=env, capture_output=True, text=True)
    assert out.stdout.strip() == "1.2.3"
    r2 = subprocess.run(["sh", str(REPO / "install.sh")], env=env, capture_output=True, text=True)
    assert r2.returncode == 0 and (home / ".zshrc").read_text().count("# rharness") == 1
