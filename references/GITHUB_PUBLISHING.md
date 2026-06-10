# GitHub Repo Publishing Workflow

To package a Hermes skill for GitHub:

1. Create repo: `gh repo create [NAME] --public`
2. Clone: `git clone [REPO_URL] /tmp/[NAME]`
3. Structure: `mkdir -p src/{v1,v2} docs tests templates`
4. Sync files from `~/.hermes/skills/finance/[SKILL]/`:
   - Scripts → `src/`
   - Refs → `docs/`
   - Tests → `tests/`
   - Templates → `templates/`
5. Docs:
   - Generate `README.md` (Quickstart, Usage, Features, Methodology reference)
   - Add `LICENSE` (MIT)
   - Add `.gitignore` (ignore venv, SQLite, .tmp files)
6. Push:
   - `git add .`
   - `git commit -m "Initial release"`
   - `git push origin main`

*Pro-tip: Keep local skill folder and Git repo synced by running script copies from ~/.hermes/skills/... to the local repo dir.*