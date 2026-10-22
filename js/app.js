const FPS = 30;
const FRAME_MS = 1000 / FPS;
const COST_LABELS = {
  gold: "Ouro",
  wood: "Madeira",
  oil: "Petróleo",
  steel: "Aço",
  cash: "Cash",
};
const BEST_LABELS = {
  ft_ground: "Terrestre",
  ft_armored: "Blindado",
  ft_flying: "Voador",
  ft_building: "Prédio",
};
const COMBAT_STATS = [
  ["attack", "Ataque"],
  ["defense", "Defesa"],
  ["life", "Vida"],
  ["velocity", "Velocidade"],
];
const DETAIL_STATS = [
  ["attack_range", "Alcance"],
  ["attack_interval", "Intervalo"],
  ["min_level", "Nível mín."],
  ["population", "População"],
];
const statMax = {
  attack: 1,
  defense: 1,
  life: 1,
  velocity: 1,
  attack_range: 1,
  attack_interval: 1,
  min_level: 1,
  population: 1,
};

function rememberStatMax(units) {
  units.forEach((unit) => {
    Object.keys(statMax).forEach((key) => {
      const value = Number(unit[key]) || 0;
      if (value > statMax[key]) statMax[key] = value;
    });
  });
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function statBar(key, value) {
  const max = statMax[key] || 1;
  const percent = Math.max(0, Math.min(100, Math.round((Number(value) || 0) * 100 / max)));
  return `<span class="stat-bar" aria-hidden="true"><i style="width:${percent}%"></i></span>`;
}

function renderCosts(costs) {
  if (!costs || typeof costs !== "object") return '<p class="stat-empty">—</p>';
  const chips = Object.entries(costs)
    .filter(([, value]) => value != null && value !== "")
    .map(([key, value]) => (
      `<span class="cost cost-${escapeHtml(key)}"><b>${escapeHtml(value)}</b>${COST_LABELS[key] || key}</span>`
    ));
  return chips.length ? `<div class="cost-list">${chips.join("")}</div>` : '<p class="stat-empty">—</p>';
}

function renderStats(unit) {
  const combat = COMBAT_STATS.map(([key, label]) => `
    <div class="stat-card">
      <span class="stat-label">${label}</span>
      <strong class="stat-value">${escapeHtml(unit[key] ?? 0)}</strong>
      ${statBar(key, unit[key])}
    </div>`).join("");
  const details = DETAIL_STATS.map(([key, label]) => (
    `<div class="stat-row"><span>${label}</span><b>${escapeHtml(unit[key] ?? 0)}</b></div>`
  )).join("");
  const versus = BEST_LABELS[unit.best_against] || unit.best_against || "—";
  statsEl.innerHTML = `
    <div class="stat-combat">${combat}</div>
    <div class="stat-block">
      <h3>Ficha</h3>
      <div class="stat-rows">
        ${details}
        <div class="stat-row"><span>Melhor contra</span><b>${escapeHtml(versus)}</b></div>
      </div>
    </div>
    <div class="stat-block">
      <h3>Custo</h3>
      ${renderCosts(unit.costs)}
    </div>`;
}

const GAME = document.body.dataset.game || "wars";
const DATA_URL = GAME === "empires" ? "data/empires/units.json" : "data/units.json";

const search = document.getElementById("search");
const grid = document.getElementById("grid");
const overlay = document.getElementById("overlay");
const player = document.getElementById("player");
const statsEl = document.getElementById("stats");
const tagsEl = document.getElementById("viewer-tags");
const titleEl = document.getElementById("viewer-title");
const idEl = document.getElementById("viewer-id");
const subtitle = document.getElementById("subtitle");
const filtersEl = document.getElementById("filters");
const filterToggle = document.getElementById("filter-toggle");

/** @type {Map<number, object>} */
const unitsById = new Map();
/** @type {Set<string>} */
const selectedGroups = new Set();
/** @type {Set<string>} */
const selectedTraits = new Set();
let animTimer = 0;
let openUnitId = null;

if (location.protocol === "file:") {
  document.getElementById("file-warn").style.display = "block";
}

function parseHash() {
  const match = location.hash.match(/^#\/unit\/(\d+)/);
  return match ? Number(match[1]) : null;
}

function applyFilters() {
  const query = search.value.trim().toLowerCase();
  grid.querySelectorAll(".card").forEach((card) => {
    const textOk = !query || card.dataset.name.includes(query) || card.dataset.id.includes(query);
    const groupOk = !selectedGroups.size || selectedGroups.has(card.dataset.group || "");
    const traits = (card.dataset.traits || "").split(",").filter(Boolean);
    const traitOk = !selectedTraits.size || [...selectedTraits].every((trait) => traits.includes(trait));
    card.classList.toggle("hidden", !(textOk && groupOk && traitOk));
  });
}

function toggleChip(set, value, button) {
  if (set.has(value)) set.delete(value);
  else set.add(value);
  button.classList.toggle("on", set.has(value));
  applyFilters();
}

function renderFilters(units) {
  if (!filtersEl) return;
  const groups = [];
  const traits = [];
  const seenGroup = new Set();
  const seenTrait = new Set();
  units.forEach((unit) => {
    const group = unit.group || "";
    const label = unit.group_label || "Outros";
    if (!seenGroup.has(group)) {
      seenGroup.add(group);
      groups.push({ value: group, label });
    }
    (unit.traits || []).forEach((key, index) => {
      if (seenTrait.has(key)) return;
      seenTrait.add(key);
      traits.push({ value: key, label: (unit.trait_labels || [])[index] || key });
    });
  });

  const groupChips = groups.map(({ value, label }) => (
    `<button type="button" class="chip" data-filter="group" data-value="${escapeHtml(value)}">${escapeHtml(label)}</button>`
  )).join("");
  const traitChips = traits.map(({ value, label }) => (
    `<button type="button" class="chip" data-filter="trait" data-value="${escapeHtml(value)}">${escapeHtml(label)}</button>`
  )).join("");
  filtersEl.innerHTML = `
    <div class="filter-row">
      <span>Grupo</span>
      <div class="chips">${groupChips}</div>
    </div>
    <div class="filter-row">
      <span>Traits</span>
      <div class="chips">${traitChips}</div>
    </div>`;
  filtersEl.querySelectorAll(".chip").forEach((button) => {
    button.addEventListener("click", () => {
      const set = button.dataset.filter === "group" ? selectedGroups : selectedTraits;
      toggleChip(set, button.dataset.value || "", button);
    });
  });
}

function stopAnim() {
  if (animTimer) {
    clearInterval(animTimer);
    animTimer = 0;
  }
}

function closeViewer(updateHash = true) {
  overlay.classList.remove("open");
  player.innerHTML = "";
  statsEl.innerHTML = "";
  tagsEl.innerHTML = "";
  stopAnim();
  if (openUnitId != null) {
    const prev = grid.querySelector(`.card[data-id="${openUnitId}"]`);
    if (prev) prev.classList.remove("active");
  }
  openUnitId = null;
  if (updateHash && parseHash() != null) {
    history.pushState(null, "", location.pathname + location.search);
  }
}

function openViewer(unit, updateHash = true) {
  if (!unit) return;
  stopAnim();
  if (openUnitId != null) {
    const prev = grid.querySelector(`.card[data-id="${openUnitId}"]`);
    if (prev) prev.classList.remove("active");
  }
  openUnitId = unit.id;
  const card = grid.querySelector(`.card[data-id="${unit.id}"]`);
  if (card) card.classList.add("active");

  const frames = (unit.frames && unit.frames.length ? unit.frames : (unit.image ? [unit.image] : []));
  titleEl.textContent = unit.name;
  idEl.textContent = `${unit.group_label || "Outros"} · ID ${unit.id}`;
  player.innerHTML = "";
  overlay.classList.add("open");

  renderStats(unit);
  tagsEl.innerHTML = (unit.trait_labels || []).map((tag) => `<span>${escapeHtml(tag)}</span>`).join("");

  if (unit.anim) {
    const image = document.createElement("img");
    image.alt = unit.name;
    image.src = unit.anim;
    player.appendChild(image);
  } else if (!frames.length) {
    player.innerHTML = '<p id="player-empty">Sem sprite de frente.</p>';
  } else {
    const image = document.createElement("img");
    image.alt = unit.name;
    player.appendChild(image);
    let index = 0;
    image.src = frames[0];
    if (frames.length > 1) {
      animTimer = setInterval(() => {
        index = (index + 1) % frames.length;
        image.src = frames[index];
      }, FRAME_MS);
    }
  }

  if (updateHash) {
    const next = `#/unit/${unit.id}`;
    if (location.hash !== next) history.pushState(null, "", next);
  }
}

function renderGrid(units) {
  const fragment = document.createDocumentFragment();
  units.forEach((unit) => {
    unitsById.set(unit.id, unit);
    const card = document.createElement("article");
    card.className = "card";
    card.dataset.id = String(unit.id);
    card.dataset.name = unit.name.toLowerCase();
    card.dataset.group = unit.group || "";
    card.dataset.traits = (unit.traits || []).join(",");
    const src = unit.thumb || unit.image;
    const thumb = src
      ? `<img src="${src}" alt="${unit.name}" loading="lazy">`
      : '<div class="no-img">sem imagem</div>';
    card.innerHTML = `
      <div class="thumb">${thumb}</div>
      <div class="meta">
        <strong>${unit.name}</strong>
        <span class="id">ID ${unit.id}</span>
        <span class="group">${unit.group_label || "Outros"}</span>
      </div>`;
    card.addEventListener("click", () => openViewer(unit));
    fragment.appendChild(card);
  });
  grid.replaceChildren(fragment);
  subtitle.textContent = `${units.length} unidades — vista de frente · clique para ficha e animação`;
}

function syncFromHash() {
  const unitId = parseHash();
  if (unitId == null) {
    if (openUnitId != null) closeViewer(false);
    return;
  }
  const unit = unitsById.get(unitId);
  if (unit) openViewer(unit, false);
}

async function main() {
  try {
    const response = await fetch(DATA_URL);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const units = await response.json();
    rememberStatMax(units);
    renderFilters(units);
    renderGrid(units);
    applyFilters();
    syncFromHash();
  } catch (error) {
    subtitle.textContent = "Não foi possível carregar o catálogo.";
    const warn = document.createElement("p");
    warn.id = "error";
    warn.textContent = location.protocol === "file:"
      ? "O JSON não carrega em file://. Rode python scripts/serve.py"
      : String(error);
    subtitle.after(warn);
  }
}

search.addEventListener("input", applyFilters);
if (filterToggle && filtersEl) {
  filterToggle.addEventListener("click", () => {
    const open = filtersEl.hasAttribute("hidden");
    filtersEl.toggleAttribute("hidden", !open);
    filterToggle.setAttribute("aria-expanded", String(open));
  });
}
document.getElementById("close").addEventListener("click", () => closeViewer());
overlay.addEventListener("click", (event) => {
  if (event.target === overlay) closeViewer();
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") closeViewer();
});
window.addEventListener("popstate", syncFromHash);
window.addEventListener("hashchange", syncFromHash);

main();
