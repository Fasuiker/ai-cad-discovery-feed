# Research Workspace Discovery Feeds

Machine-readable candidate-paper feeds for the **科研工作台 / Research Workspace**.
The default starter profile covers **large language models and agents**; the
original AI+CAD profile remains available for specialist use.

The repository searches public scholarly metadata every day, normalizes and
deduplicates candidates, then publishes `data/latest.json`. It stores metadata
only: no PDFs, private notes, local paths, or personal research data are
uploaded.

## Schedule

GitHub Actions runs every day at **00:00 UTC / 08:00 Asia/Shanghai**. The public
job maintains a rolling 30-day candidate pool so individual workbench users can
choose a 1–30 day local lookback without uploading their private preferences.
Manual workflow runs may specify a custom start and end date.

## Sources

- arXiv
- OpenAlex
- Crossref
- selected public Awesome AI+CAD lists

## Files

- `config/llm.json` — default large-model and agent discovery profile
- `data/archive/llm/latest.json` — default candidate feed consumed by new workspaces
- `config/ai-cad.json` — specialist AI+CAD profile and multi-profile job entry
- `data/latest.json` — legacy AI+CAD candidate feed
- `data/manifest.json` — lightweight feed metadata
- `scripts/discover.py` — standard-library discovery pipeline

The feed is a broad discovery aid, not a claim that every returned paper is
relevant. The workbench applies each user's local keywords, exclusions, source
selection, arXiv categories and lookback window before presenting new daily
candidates, then keeps a human confirmation step before download and cataloguing.

## Use your own fork / 使用自己的检索源

1. Fork this repository without renaming it.
2. Open the fork's **Actions** tab and enable `Daily AI+CAD discovery` (GitHub
   disables scheduled workflows in new public forks by default).
3. Edit `config/llm.json` on the default branch. The next workflow run writes
   both the candidates and the public configuration snapshot to
   `data/archive/llm/latest.json`. AI+CAD users can instead edit
   `config/ai-cad.json` and use `data/latest.json` as a custom feed.
4. In Research Workspace, open `文献 → 文献发现 → 每日发现 → 设置`, select
   `我的 GitHub Fork`, enter the GitHub username, test the connection, and enable
   `跟随候选源中的公开配置` if the fork should be the source of truth.

Local-only preferences remain available: leave the follow switch off to use the
fork as a broad candidate pool while filtering it with settings stored only on
the current device.
