# AI + CAD Discovery Feed

Machine-readable candidate-paper feed for the **科研工作台 / Research Workspace**.

The repository searches public scholarly metadata every day, normalizes and
deduplicates candidates, then publishes `data/latest.json`. It stores metadata
only: no PDFs, private notes, local paths, or personal research data are
uploaded.

## Schedule

GitHub Actions runs every day at **00:00 UTC / 08:00 Asia/Shanghai**. The daily
job searches a rolling three-day window so indexing delays do not cause gaps.
Manual workflow runs may specify a custom start and end date.

## Sources

- arXiv
- OpenAlex
- Crossref
- selected public Awesome AI+CAD lists

## Files

- `config/ai-cad.json` — search terms, exclusions, categories and source list
- `data/latest.json` — current candidate feed consumed by the workbench
- `data/manifest.json` — lightweight feed metadata
- `scripts/discover.py` — standard-library discovery pipeline

The feed is a discovery aid, not a claim that every returned paper is relevant.
The workbench keeps a human confirmation step before download and cataloguing.
