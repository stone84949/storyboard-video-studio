# First Test Preflight

Before evaluating or running the first real storyboard video test, install the
supporting Codex plugins and skills needed for this repo's intended workflow.

## Plugin Candidates

Install only the ones needed for the first test lane:

```powershell
codex plugin add hyperframes@openai-curated
codex plugin add fal@openai-curated
codex plugin add render@openai-curated
```

Consider later, once the talking-head or avatar lane is active:

```powershell
codex plugin add heygen@openai-curated
```

## Skill Candidates

Useful for visual QA and media handling:

```powershell
python C:\Users\jston\.codex\skills\.system\skill-installer\scripts\install-skill-from-github.py --repo openai/skills --path skills/.curated/playwright
python C:\Users\jston\.codex\skills\.system\skill-installer\scripts\install-skill-from-github.py --repo openai/skills --path skills/.curated/screenshot
python C:\Users\jston\.codex\skills\.system\skill-installer\scripts\install-skill-from-github.py --repo openai/skills --path skills/.curated/transcribe
```

Restart Codex after installing new skills or plugins so they load cleanly.

## Open Design Check

Open Design should be checked before the first pilot because it already exposes
video, design-system, image, and talking-head style skills that may shape the
first template choice.

See [open-design-integration.md](open-design-integration.md).

Also complete the template browsing pass in
[template-discovery-plan.md](template-discovery-plan.md).

## Reason

Do not judge the first test run until the supporting tools are installed. The
first pilot should test the storyboard workflow, sourced-image handling, and
style template direction, not fail because the local agent environment is
missing obvious video/QA helpers.
