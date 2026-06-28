const stageLabels = new Map();

function formatDate(value) {
  if (!value) return "Unknown";
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

function statusFor(project) {
  if (project.stage_status.render === "done") return "rendered";
  if (project.stage_status.assets === "review") return "asset review";
  if (project.stage_status.storyboard === "done") return "storyboarded";
  return "planning";
}

function addDetail(list, label, value) {
  const dt = document.createElement("dt");
  dt.textContent = label;
  const dd = document.createElement("dd");
  dd.textContent = value;
  list.append(dt, dd);
}

function makeCopyButton(label, value) {
  const button = document.createElement("button");
  button.type = "button";
  button.textContent = label;
  button.addEventListener("click", async () => {
    await navigator.clipboard.writeText(value);
    button.textContent = "Copied";
    setTimeout(() => {
      button.textContent = label;
    }, 1200);
  });
  return button;
}

function renderPipeline(data) {
  const pipeline = document.querySelector("#pipeline");
  pipeline.innerHTML = "";
  for (const stage of data.stages) {
    stageLabels.set(stage.key, stage.label);
    const item = document.createElement("div");
    item.className = "stage-total";
    item.innerHTML = `<strong>${data.summary.done_counts[stage.key] || 0}</strong><span>${stage.label}</span>`;
    pipeline.appendChild(item);
  }
}

function renderProject(project, stages) {
  const template = document.querySelector("#projectCardTemplate");
  const card = template.content.firstElementChild.cloneNode(true);
  card.querySelector(".slug").textContent = project.slug;
  card.querySelector("h3").textContent = project.title;
  card.querySelector(".badge").textContent = statusFor(project);
  card.querySelector(".next-action").textContent = project.next_action;

  const stageRow = card.querySelector(".stage-row");
  for (const stage of stages) {
    const chip = document.createElement("div");
    const status = project.stage_status[stage.key] || "missing";
    chip.className = `stage-chip ${status}`;
    chip.textContent = stage.label;
    chip.title = `${stage.label}: ${status}`;
    stageRow.appendChild(chip);
  }

  const details = card.querySelector(".details");
  addDetail(details, "Scenes", String(project.scene_count || 0));
  addDetail(details, "Assets", `${project.asset_summary.approved}/${project.asset_summary.total} approved`);
  addDetail(details, "Need files", String(project.asset_summary.missing_local || 0));
  addDetail(details, "Bad rows", String(project.asset_summary.malformed_rows || 0));
  addDetail(details, "Updated", formatDate(project.updated));

  const links = card.querySelector(".links");
  if (project.files.storyboard?.path) links.appendChild(makeCopyButton("Copy storyboard path", project.files.storyboard.path));
  if (project.files.asset_board?.path) links.appendChild(makeCopyButton("Copy asset board", project.files.asset_board.path));
  if (project.links.render_path) links.appendChild(makeCopyButton("Copy render path", project.links.render_path));
  if (project.links.hyperframes_preview) {
    const a = document.createElement("a");
    a.href = project.links.hyperframes_preview;
    a.textContent = "Open preview";
    a.target = "_blank";
    a.rel = "noreferrer";
    links.appendChild(a);
  }
  if (!links.children.length) {
    const empty = document.createElement("span");
    empty.className = "muted";
    empty.textContent = "No links yet";
    links.appendChild(empty);
  }
  return card;
}

async function loadDashboard() {
  const response = await fetch(`data/projects.json?ts=${Date.now()}`);
  if (!response.ok) throw new Error(`Could not load dashboard data: ${response.status}`);
  const data = await response.json();

  document.querySelector("#generatedAt").textContent = `Updated ${formatDate(data.generated_at)}`;
  document.querySelector("#projectCount").textContent = data.summary.project_count;
  document.querySelector("#renderedCount").textContent = data.summary.rendered_count;
  document.querySelector("#assetReviewCount").textContent = data.summary.needs_asset_review;

  renderPipeline(data);
  const grid = document.querySelector("#projectGrid");
  grid.innerHTML = "";
  for (const project of data.projects) {
    grid.appendChild(renderProject(project, data.stages));
  }
}

document.querySelector("#refreshButton").addEventListener("click", loadDashboard);
loadDashboard().catch((error) => {
  document.querySelector("#projectGrid").innerHTML = `<article class="project-card"><h3>Dashboard data missing</h3><p>${error.message}</p><p>Run <code>python scripts/build_dashboard.py</code>.</p></article>`;
});
