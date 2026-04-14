# Windows Task Scheduler setup

1. Open **Task Scheduler** (search in Start menu).
2. Click **Create Task** (not Basic Task).
3. **General** tab:
   - Name: `StartupRadar`
   - Check "Run whether user is logged on or not" if you want it to run when locked
4. **Triggers** tab → New:
   - Daily, start time 08:00, recur every 1 day
5. **Actions** tab → New:
   - Action: Start a program
   - Program/script: `python`
   - Add arguments: `daily_run.py`
   - Start in: full path to this repo (e.g. `C:\Users\you\startup-radar-template`)
6. **Conditions** tab:
   - Uncheck "Start the task only if the computer is on AC power" if you use a laptop
7. **Settings** tab:
   - Check "Run task as soon as possible after a scheduled start is missed"
8. Click OK. You'll be asked for your Windows password.

Test it: right-click the task → **Run**. Check `logs/YYYY-MM-DD.log` for output.
