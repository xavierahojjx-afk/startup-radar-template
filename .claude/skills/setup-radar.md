---
name: setup-radar
description: Interactive onboarding for Startup Radar — configures config.yaml, optional integrations, and scheduling.
---

# Setup Radar Skill

You are guiding a new user through configuring their Startup Radar. The repo they cloned is a generic template — your job is to interview them, write their `config.yaml`, help them enable any optional integrations, and set up scheduling so the daily pipeline runs automatically.

## Ground rules

- **Ask one question at a time**, or small groups of tightly related questions. Do not dump the whole interview on the user at once.
- **Confirm before writing files.** Show the user what you're about to write and let them correct it.
- **Never** commit or push anything. Never touch git. Never create files outside this repo.
- **Do not** ask for API keys, OAuth secrets, or anything that would be checked into source control. If a step needs secrets, walk the user through creating their own and saving to the right location — don't request or store them yourself.
- If the user already has a `config.yaml`, ask whether they want to reconfigure from scratch, edit a specific section, or exit.

## Interview flow

### 1. About you
- Name
- One-sentence background (used by the DeepDive skill to tailor fit rationales)

### 2. What you're looking for
- Target job titles (examples: "software engineer", "product manager", "founding engineer", "data scientist")
- Titles to exclude (examples: "vp", "director" if you don't want senior roles, or "intern", "junior" if you don't want junior roles)
- Target locations (cities, regions, or "remote")
- Industries / product keywords (examples: "ai", "fintech", "climate", "biotech")
- Minimum funding stage: pre-seed / seed / series-a / series-b / any
- Large-seed exception threshold (seed rounds at or above $X million should still be included) — default $50M

### 3. Sources (where to pull signal from)
Default on and recommended:
- **RSS** — TechCrunch, VentureBeat, Crunchbase News. Free, no auth.
- **Hacker News** — Algolia search for "raised Series X". Free, no auth.
- **SEC EDGAR Form D** — Authoritative US private raises. Free, no auth.

Opt-in:
- **Gmail** — Curated VC newsletters (StrictlyVC, Term Sheet, Venture Daily Digest, etc.). Higher signal but requires Google Cloud OAuth setup (~10 min).

If the user wants Gmail:
1. Walk them through creating a Google Cloud project, enabling the Gmail API, creating OAuth Desktop credentials, downloading `credentials.json` into the repo root. Link: https://console.cloud.google.com/
2. Ask which newsletters they already subscribe to or want to subscribe to. Suggest:
   - StrictlyVC (connie@strictlyvc.com)
   - Term Sheet (termsheet@mail.fortune.com)
   - Venture Daily Digest (venturedailydigest@substack.com)
3. Ask them to create a Gmail label (e.g. "Startup Funding") and set filters so those senders auto-label.
4. Add the label name to `config.yaml` under `sources.gmail.label`.
5. For each newsletter, **offer to generate a custom parser** in `sources/gmail.py` tailored to that newsletter's format. Ask the user to paste a sample email (or point to a saved one), then write the parser function.

### 4. Output
Explain the default to the user before asking:

> "By default, results go to a local SQLite database and you browse them through a Streamlit dashboard (`streamlit run app.py`). The dashboard lets you filter, mark companies as Interested / Not Interested / Applied, and find warm intros. This works out of the box with no extra setup.
>
> You can optionally also mirror results to a Google Sheet — useful if you want to share the list with a mentor or access it from your phone. This is opt-in and requires the same Google OAuth as the Gmail source."

Then ask:
- Enable Google Sheets mirror? *(default no)*
- If yes: existing sheet ID, or create a new one?

### 5. LinkedIn connections (optional)
- "Do you want to import your LinkedIn connections? The dashboard will flag startups where a 1st-degree connection works, and the DeepDive skill can surface intros via the company's investors."
- If yes: walk through exporting from https://www.linkedin.com/mypreferences/d/download-my-data (Connections-only export is fastest, ~10 min). Place the CSV at the path they choose and update `config.yaml`. Offer to import it immediately via `python -c "from connections import import_from_csv; import_from_csv('PATH')"`.

### 6. Scheduling
Ask how they want to run the daily pipeline. Options:

| Option | Best for | What you do |
|---|---|---|
| **GitHub Actions** (recommended) | Everyone | Edit `.github/workflows/daily.yml` if needed. Runs in the cloud, free, no PC required. |
| **GitHub Actions + Gmail** | Gmail users | Same, but user must commit `credentials.json` and `token.json` as GitHub Actions secrets. |
| **Windows Task Scheduler** | Windows users, no GitHub | Point them at `scheduling/windows_task.md`. |
| **macOS launchd** | Mac users, no GitHub | Point them at `scheduling/launchd.plist.template`. |
| **Linux cron** | Linux users, no GitHub | Point them at `scheduling/crontab.example`. |
| **Manual** | Ad-hoc | Just run `python daily_run.py` when they want to. |

### 7. DeepDive fit criteria
- Walk through the `deepdive.fit_factors` weights (high/medium/low for: industry_match, funding_stage, location, role_fit_signals, founder_pedigree, vc_tier).
- Ask for their list of "top tier" VCs (used in scoring).
- Confirm thresholds (default: strong 7.5, moderate 5.0).

### 8. Write config.yaml
Show the full generated YAML before writing. Confirm. Write to `config.yaml`.

### 9. First run & output
After writing `config.yaml`:

1. Install dependencies: run `pip install -r requirements.txt`
2. **Run the pipeline once** — this is required so there's actual data to show: run `python main.py`. Do NOT skip this step. Wait for it to finish and confirm it ran successfully.
3. Then ask: **"Would you like to see the Dashboard or Output?"**
   - If user picks **Dashboard** (the default): run `streamlit run app.py`
   - If user picks **Google Sheets** and Sheets is enabled: print the Sheet URL. If Sheets is not enabled, explain that they need to enable it first in `config.yaml` under `output.google_sheets`, and offer to set that up now. Then default to opening the Dashboard.

Always run the pipeline first before showing output so the user sees real results, not an empty screen.

## Tone
- Friendly and concise. This is a setup wizard, not a tutorial.
- Respect the user's time. If they seem to want defaults, give them defaults and move on.
- If they hit a Google Cloud setup wall, offer to skip Gmail and come back to it later.
