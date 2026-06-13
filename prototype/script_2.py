
# Write a README specifically for this workflow
readme = '''# Storyboard → Video Pipeline
## How to use these two files

---

### Files included
| File | Purpose |
|---|---|
| `storyboard_template.csv` | Fill this in for every new video |
| `storyboard_to_config.py` | Place in `scripts/` in your repo — converts the CSV to a job config |

---

### Step 1 — Copy the template
```bash
cp storyboard_template.csv videos/my-new-video/storyboard.csv
```

---

### Step 2 — Fill in the CSV (open in Excel, Google Sheets, or any text editor)

**Top section (one row) — job settings:**
| Column | What to enter |
|---|---|
| `job_id` | Short slug, lowercase, no spaces (e.g. `ai-agents-2026`) |
| `title` | Full readable title of the video |
| `target_duration_seconds` | How long the video should be (max 179) |
| `resolution_w / resolution_h` | Leave as 1080 / 1920 for vertical shorts |
| `aspect_ratio` | Leave as 9:16 |
| `codec / crf / preset` | Leave defaults unless you know what you are doing |

**Bottom section (one row per panel/scene):**
| Column | What to enter |
|---|---|
| `panel_number` | 1, 2, 3... in order |
| `scene_description` | What is happening visually (for your reference) |
| `narration_text` | Exactly what the narrator says during this panel |
| `image_filename` | Filename of the image you will drop in the src folder (e.g. `hero.jpg`) |
| `image_mode` | `pad` = blurred background (safest), `fill` = zoomed crop, `fit` = letterbox |
| `focal_x / focal_y` | Where the subject is: 0.5/0.5 = center, 0.5/0.3 = upper-center (face shots) |
| `allow_upscale` | `false` unless image is smaller than 720x1280 |
| `hold_seconds` | How many seconds this panel shows on screen |
| `notes` | Any reminder for yourself — not used by the pipeline |

**Image mode guide:**
- `pad` — safest choice: image fits inside frame, blurred version of itself fills the background. No cropping, no stretching.
- `fill` — image fills the full frame. Subject at focal_x/focal_y stays centered. Edges may be cropped.
- `fit` — image scaled down to fit fully, black or color bars fill leftover space.
- `stretch` — avoid this. It distorts the image.

---

### Step 3 — Preview before committing
```bash
python scripts/storyboard_to_config.py videos/my-new-video/storyboard.csv --preview
```
This prints a table showing all panels, images, and modes WITHOUT writing any files.
Review it. Make sure filenames and modes look right.

---

### Step 4 — Generate the job folder
```bash
python scripts/storyboard_to_config.py videos/my-new-video/storyboard.csv
```

This creates:
```
videos/my-new-video/
├── job_config.json          ← auto-generated, feeds the pipeline
├── storyboard.csv           ← your filled-in storyboard (copy saved here)
├── IMAGE_CHECKLIST.txt      ← checklist showing exactly which images to drop in
└── assets/images/src/       ← DROP YOUR IMAGES HERE
```

On Windows you can add `--open-folder` to pop open the src folder automatically:
```bash
python scripts/storyboard_to_config.py storyboard.csv --open-folder
```

---

### Step 5 — Drop in your images
Open `videos/my-new-video/IMAGE_CHECKLIST.txt` — it lists every filename expected.
Drop matching image files into `videos/my-new-video/assets/images/src/`.

---

### Step 6 — Process images (resize to 1080x1920, no distortion)
```bash
python scripts/process_images.py videos/my-new-video/job_config.json
```
Processed images appear in `assets/images/processed/` — these are what the video uses.

---

### Step 7 — Run the pipeline
```bash
archon workflow run create-archon-short --no-worktree "Your Video Title"
```

---

### Step 8 — Render
```bash
npx hyperframes render videos/my-new-video -o videos/my-new-video/out/my-new-video.mp4
```

---

### Step 9 — Edit manually (optional)
```bash
python scripts/export_edit_project.py my-new-video
# Opens in Shotcut:
shotcut videos/my-new-video/out/my-new-video.mlt
```

---

### Typical image mode recommendations by content type
| Content type | Recommended mode | Focal point |
|---|---|---|
| Person / face close-up | `fill` | 0.5, 0.25 (upper third) |
| Landscape / background scene | `pad` | 0.5, 0.5 |
| Product shot (square image) | `pad` | 0.5, 0.5 |
| Infographic / stat graphic | `pad` | 0.5, 0.5 |
| Action shot with subject off-center | `fill` | adjust x to subject position |
| Logo or icon (small image) | `pad` with `allow_upscale: true` | 0.5, 0.5 |
'''

with open("output/STORYBOARD_README.md", "w") as f:
    f.write(readme)

print("README written")
