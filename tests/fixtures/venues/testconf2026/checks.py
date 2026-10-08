def check(project_dir, venue):
    out = []
    main = project_dir / "paper" / "main.tex"
    if main.exists() and "TODO" in main.read_text():
        out.append(("warning", "paper/main.tex", "package check: main.tex still contains TODO"))
    return out
