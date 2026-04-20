# `data` branch — GH Actions DB store

Startup Radar's GitHub Actions workflow persists the SQLite DB (`startup_radar.db`) by committing it to an orphan branch named `data`. This doc is the one-time bootstrap for a fresh fork.

## Why a branch, not cache?

See `docs/CRITIQUE_APPENDIX.md` §5. TL;DR: `actions/cache` is evicted at 7 days no-access and racy across concurrent runs. A git branch is free, observable (`git log data -- startup_radar.db`), and recoverable.

## First-time setup (run once per fork)

**Easiest:** open Claude Code in the project folder and run `/data-branch-bootstrap`. The skill walks the same steps below interactively and only pushes after you confirm.

If you'd rather do it manually:

```bash
# Create an orphan `data` branch with no history.
git checkout --orphan data
git rm -rf .                               # strip everything from the index
printf '# startup-radar data branch\n' > README.md
git add README.md
git commit -m "chore(data): initialize orphan data branch"
git push origin data

# Back to main.
git checkout main
```

You also need to confirm GitHub Actions has write access to the repo:
**Settings → Actions → General → Workflow permissions → "Read and write permissions"**.

After that, the daily workflow will commit `startup_radar.db` to `data` automatically.

## Manual restore (pull the prod DB locally)

**Easiest:** run `/data-branch-restore` in Claude Code.

If you'd rather do it manually:

```bash
git fetch origin data:data
git checkout data -- startup_radar.db
# Now `startup_radar.db` at repo root is the latest prod DB.
```

## Garbage collection

A separate workflow (`.github/workflows/data-branch-gc.yml`) force-pushes a fresh orphan commit every Sunday to prevent binary-diff bloat. If you never want GC, delete that workflow — the DB will still persist, but the branch history will grow indefinitely.

## Failure modes

- **Pipeline fails** → no commit to `data`; prior DB stays as-is. Failed run's partial DB is in the `startup-radar-db` artifact (7-day retention).
- **`data` branch deleted accidentally** → next run starts fresh, same as a new fork. No data rescue from the branch; use the most recent `startup-radar-db` artifact (Actions → workflow run → Artifacts).
- **Force-push from elsewhere** → last writer wins. GC workflow is the only force-pusher by design.
