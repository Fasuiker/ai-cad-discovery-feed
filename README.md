# AI + CAD Discovery Feed

Machine-readable candidate-paper feed for the **科研工作台 / Research Workspace**.

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

- `config/ai-cad.json` — public baseline terms, exclusions, categories, enabled
  sources and collection window
- `data/latest.json` — current candidate feed consumed by the workbench
- `data/manifest.json` — lightweight feed metadata
- `scripts/discover.py` — standard-library discovery pipeline

The feed is a broad discovery aid, not a claim that every returned paper is
relevant. The workbench applies each user's local keywords, exclusions, source
selection, arXiv categories and lookback window before presenting new daily
candidates, then keeps a human confirmation step before download and cataloguing.
