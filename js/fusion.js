const GAME = document.body.dataset.game || "wars";
const IS_EMPIRES = GAME === "empires";
const DATA_URL = IS_EMPIRES ? "data/empires/units.json" : "data/units.json";
const CATALOG_PAGE = IS_EMPIRES ? "empires.html" : "wars.html";
const FUSION_K = 0.6;
const ORDER_CAP = 240;
const POWERUPS = [
  { cash: 1, bonus: 1 },
  { cash: 2, bonus: 2 },
  { cash: 4, bonus: 4 },
  { cash: 8, bonus: 8 },
  { cash: 15, bonus: 15 },
  { cash: 20, bonus: 20 },
];
const EMPIRES_BLOCKED_GROUPS = new Set(["boar", "cow", "horse", "sheep", "cart"]);
const EMPIRES_BLOCKED_NAMES = new Set(["eagle", "white eagle", "settler"]);
const EXCLUDE_IDS = new Set([
  923, 933, 1005, 1009, 1011, 1012, 1013, 1017, 1018, 1019, 1024, 1032, 1034,
  1035, 1043, 1049, 1050, 1051, 1052, 1053, 1068, 1103, 1108, 1118, 1130, 1131,
  1132, 1140, 1142, 1176, 1401, 1402, 1403, 1404, 1128, 1153, 1163, 1164, 1171,
  1173, 1179, 1182, 1193, 1206, 1211, 1216, 1224, 1238, 1240, 1247, 1249, 1251,
  1255, 1257, 1264, 1269, 1273, 1277, 1286, 1289, 1294, 1298, 1300, 1302, 1304,
  1306, 1308, 1310, 1312, 1314, 1316, 1318, 1322, 1320, 1324, 1326, 1328, 1330,
  1332, 1334, 1336, 1342, 1338, 1344, 1340, 1346, 1348, 1350, 1352, 1354, 1357,
  1363, 1361, 1365, 1369, 1371, 1372, 1373, 1374, 1378, 1376, 1380, 1386, 1387,
  1389, 1391, 1393, 1395, 1397, 1399, 1409, 1407, 1411, 1413, 1415, 1417, 1419,
  1421, 1423, 1425, 1429, 1431, 1384,
]);

const slotA = document.getElementById("slot-a");
const slotB = document.getElementById("slot-b");
const resultsEl = document.getElementById("results");
const resultsToolbar = document.getElementById("results-toolbar");
const mathEl = document.getElementById("math");
const countEl = document.getElementById("fusion-count");
const subtitle = document.getElementById("subtitle");
const overlay = document.getElementById("overlay");
const player = document.getElementById("player");
const statsEl = document.getElementById("stats");
const titleEl = document.getElementById("viewer-title");
const idEl = document.getElementById("viewer-id");
const viewerLink = document.getElementById("viewer-link");
const rangeTrack = document.getElementById("range-track");
const rangeFill = document.getElementById("range-fill");
const markA = document.getElementById("mark-a");
const markB = document.getElementById("mark-b");
const rangeLoLabel = document.getElementById("range-lo-label");
const rangeHiLabel = document.getElementById("range-hi-label");
const boostChips = document.getElementById("boost-chips");
const picker = document.getElementById("picker");
const pickerGrid = document.getElementById("picker-grid");
const pickerSearch = document.getElementById("picker-search");
const pickerFilters = document.getElementById("picker-filters");
const pickerFilterToggle = document.getElementById("picker-filter-toggle");
const pickerClose = document.getElementById("picker-close");
const pickerTitle = document.getElementById("picker-title");
const pickerSub = document.getElementById("picker-sub");
const cardPool = document.getElementById("card-pool");
const sortEl = document.getElementById("sort");

/** @type {object[]} */
let fuseUnits = [];
/** @type {Map<number, object>} */
const unitsById = new Map();
/** @type {object | null} */
let parentA = null;
/** @type {object | null} */
let parentB = null;
let boostLevel = 0;
let writingHash = false;
/** @type {"a" | "b" | null} */
let pickRole = null;
/** @type {Set<string>} */
const selectedGroups = new Set();
/** @type {Set<string>} */
const selectedTraits = new Set();
/** @type {Map<number, HTMLElement>} */
const cardsById = new Map();
const playerImg = document.createElement("img");
let sortKey = "alvo";

if (location.protocol === "file:") {
  document.getElementById("file-warn").style.display = "block";
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function fusionOrder(unit) {
  const raw = Math.floor(Number(unit.life) / 20);
  if (IS_EMPIRES) return Math.max(0, raw);
  return Math.min(raw, ORDER_CAP);
}

function canFuse(unit) {
  if (String(unit.name || "").toLowerCase().includes("chained")) return false;
  if (IS_EMPIRES) {
    const traits = unit.traits || [];
    if (traits.includes("worker")) return false;
    if (Number(unit.population) <= 0) return false;
    const group = String(unit.group || "").toLowerCase();
    const label = String(unit.group_label || "").toLowerCase();
    if (EMPIRES_BLOCKED_GROUPS.has(group) || EMPIRES_BLOCKED_GROUPS.has(label)) return false;
    if (EMPIRES_BLOCKED_NAMES.has(String(unit.name || "").toLowerCase())) return false;
    return true;
  }
  if (unit.group === "WORKER") return false;
  if (EXCLUDE_IDS.has(Number(unit.id))) return false;
  return true;
}

function boostBonus(level) {
  return POWERUPS.slice(0, level).reduce((sum, item) => sum + item.bonus, 0);
}

function boostCash(level) {
  return POWERUPS.slice(0, level).reduce((sum, item) => sum + item.cash, 0);
}

function fusionRange(unitA, unitB, level) {
  const orderA = fusionOrder(unitA);
  const orderB = fusionOrder(unitB);
  const bonus = boostBonus(level);
  const parentMax = Math.max(orderA, orderB);
  // Wars: (A+B+bônus)×0.6. Empires: √(A×B), powerup só sobe o teto (powerupCeiling).
  const alvo = IS_EMPIRES
    ? Math.sqrt(orderA * orderB)
    : (orderA + orderB + bonus) * FUSION_K;
  const lo = Math.min(alvo, parentMax);
  const hi = IS_EMPIRES
    ? Math.max(alvo, parentMax) + bonus
    : Math.max(alvo, parentMax);
  return { orderA, orderB, bonus, alvo, lo, hi };
}

function parseMixHash() {
  const match = location.hash.match(/^#\/mix\/(\d+)\/(\d+)(?:\/boost\/(\d+))?/);
  if (!match) return null;
  return {
    a: Number(match[1]),
    b: Number(match[2]),
    boost: Math.min(6, Math.max(0, Number(match[3] || 0))),
  };
}

function writeMixHash() {
  writingHash = true;
  if (!parentA || !parentB) {
    if (location.hash.startsWith("#/mix/")) history.replaceState(null, "", location.pathname);
    writingHash = false;
    return;
  }
  const next = boostLevel
    ? `#/mix/${parentA.id}/${parentB.id}/boost/${boostLevel}`
    : `#/mix/${parentA.id}/${parentB.id}`;
  if (location.hash !== next) history.replaceState(null, "", next);
  writingHash = false;
}

function renderBoost() {
  boostChips.innerHTML = [0, 1, 2, 3, 4, 5, 6].map((level) => {
    const label = level === 0 ? "0" : `+${level}`;
    const on = level === boostLevel ? " on" : "";
    return `<button type="button" class="chip${on}" data-boost="${level}">${label}</button>`;
  }).join("");
}

function inSearchAndFilters(card) {
  const query = pickerSearch.value.trim().toLowerCase();
  const textOk = !query || card.dataset.name.includes(query) || card.dataset.id.includes(query);
  const groupOk = !selectedGroups.size || selectedGroups.has(card.dataset.group || "");
  const traits = (card.dataset.traits || "").split(",").filter(Boolean);
  const traitOk = !selectedTraits.size || [...selectedTraits].every((trait) => traits.includes(trait));
  return textOk && groupOk && traitOk;
}

function currentRange() {
  if (!parentA || !parentB) return null;
  const mix = fusionRange(parentA, parentB, boostLevel);
  return {
    mix,
    lo: Math.floor(mix.lo),
    hi: Math.ceil(mix.hi),
  };
}

function parkCards() {
  cardsById.forEach((card) => cardPool.appendChild(card));
}

function applyPickerFilter() {
  let visible = 0;
  cardsById.forEach((card) => {
    const show = inSearchAndFilters(card);
    card.classList.toggle("hidden", !show);
    if (show) visible += 1;
  });
  pickerSub.textContent = `${visible} tropas — clique para escolher.`;
}

function compareUnits(left, right) {
  const orderLeft = fusionOrder(left);
  const orderRight = fusionOrder(right);
  const range = currentRange();
  const alvo = range ? range.mix.alvo : 0;
  const name = left.name.localeCompare(right.name, "pt");
  switch (sortKey) {
    case "order-asc":
      return orderLeft - orderRight || name;
    case "order-desc":
      return orderRight - orderLeft || name;
    case "life-desc":
      return (Number(right.life) || 0) - (Number(left.life) || 0) || name;
    case "attack-desc":
      return (Number(right.attack) || 0) - (Number(left.attack) || 0) || name;
    case "name":
      return name;
    case "group":
      return (left.group_label || "").localeCompare(right.group_label || "", "pt") || name;
    case "pop-desc":
      return (Number(right.population) || 0) - (Number(left.population) || 0) || name;
    default:
      return Math.abs(orderLeft - alvo) - Math.abs(orderRight - alvo) || orderLeft - orderRight || name;
  }
}

function resultUnits() {
  const range = currentRange();
  if (!range) return [];
  return fuseUnits
    .filter((unit) => {
      const order = fusionOrder(unit);
      return order >= range.lo && order <= range.hi;
    })
    .sort(compareUnits);
}

function fillResults() {
  parkCards();
  const hits = resultUnits();
  hits.forEach((unit) => {
    const card = cardsById.get(unit.id);
    card.classList.remove("hidden");
    resultsEl.appendChild(card);
  });
  resultsToolbar.hidden = hits.length === 0;
  countEl.textContent = hits.length
    ? `${hits.length} tropas nessa faixa — o jogo sorteia uma.`
    : "Escolhe os dois pais.";
}

function fillPicker() {
  parkCards();
  fuseUnits.forEach((unit) => pickerGrid.appendChild(cardsById.get(unit.id)));
  applyPickerFilter();
}

function toggleChip(set, value, button) {
  if (set.has(value)) set.delete(value);
  else set.add(value);
  button.classList.toggle("on", set.has(value));
  applyPickerFilter();
}

function renderPickerFilters() {
  const groups = [];
  const traits = [];
  const seenGroup = new Set();
  const seenTrait = new Set();
  fuseUnits.forEach((unit) => {
    const group = unit.group || "";
    if (!seenGroup.has(group)) {
      seenGroup.add(group);
      groups.push({ value: group, label: unit.group_label || "Outros" });
    }
    (unit.traits || []).forEach((key, index) => {
      if (seenTrait.has(key)) return;
      seenTrait.add(key);
      traits.push({ value: key, label: (unit.trait_labels || [])[index] || key });
    });
  });
  pickerFilters.innerHTML = `
    <div class="filter-row">
      <span>Grupo</span>
      <div class="chips">${groups.map(({ value, label }) => (
        `<button type="button" class="chip" data-filter="group" data-value="${escapeHtml(value)}">${escapeHtml(label)}</button>`
      )).join("")}</div>
    </div>
    <div class="filter-row">
      <span>Traits</span>
      <div class="chips">${traits.map(({ value, label }) => (
        `<button type="button" class="chip" data-filter="trait" data-value="${escapeHtml(value)}">${escapeHtml(label)}</button>`
      )).join("")}</div>
    </div>`;
  pickerFilters.querySelectorAll(".chip").forEach((button) => {
    button.addEventListener("click", () => {
      const set = button.dataset.filter === "group" ? selectedGroups : selectedTraits;
      toggleChip(set, button.dataset.value || "", button);
    });
  });
}

function buildCatalog() {
  if (cardsById.size) return;
  const fragment = document.createDocumentFragment();
  fuseUnits.forEach((unit) => {
    const card = document.createElement("article");
    card.className = "card";
    card.dataset.id = String(unit.id);
    card.dataset.name = unit.name.toLowerCase();
    card.dataset.group = unit.group || "";
    card.dataset.traits = (unit.traits || []).join(",");
    const src = unit.thumb || unit.image;
    const thumb = document.createElement("div");
    thumb.className = "thumb";
    if (src) {
      const image = document.createElement("img");
      image.alt = unit.name;
      image.decoding = "async";
      image.src = src;
      thumb.appendChild(image);
    } else {
      thumb.innerHTML = '<div class="no-img">sem imagem</div>';
    }
    const meta = document.createElement("div");
    meta.className = "meta";
    meta.innerHTML = `
      <strong>${escapeHtml(unit.name)}</strong>
      <span class="order">order ${fusionOrder(unit)} · vida ${unit.life}</span>
      <span class="id">ID ${unit.id}</span>
      <span class="group">${escapeHtml(unit.group_label || "Outros")}</span>`;
    card.append(thumb, meta);
    card.addEventListener("click", () => onCatalogClick(unit));
    cardsById.set(unit.id, card);
    fragment.appendChild(card);
  });
  cardPool.replaceChildren(fragment);
}

function onCatalogClick(unit) {
  if (pickRole) {
    const role = pickRole;
    pickRole = null;
    setParent(role, unit);
    closePicker();
    return;
  }
  if (parentA && parentB) openViewer(unit);
}

function openPicker(role) {
  pickRole = role;
  pickerTitle.textContent = `Escolher pai ${role.toUpperCase()}`;
  if (!picker.open) picker.showModal();
  fillPicker();
}

function closePicker() {
  pickRole = null;
  if (picker.open) picker.close();
  else fillResults();
}

function parentThumb(unit) {
  const live = cardsById.get(unit.id)?.querySelector("img");
  if (live) {
    const clone = live.cloneNode(true);
    clone.loading = "eager";
    clone.alt = unit.name;
    return clone;
  }
  const image = document.createElement("img");
  image.alt = unit.name;
  image.src = unit.thumb || unit.image || "";
  return image;
}

function renderSlot(slotEl, unit, role) {
  const title = role === "a" ? "Pai A" : "Pai B";
  slotEl.replaceChildren();
  const label = document.createElement("label");
  label.textContent = title;
  slotEl.appendChild(label);
  if (!unit) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "parent-pick";
    button.dataset.pick = role;
    button.textContent = "Escolher tropa";
    slotEl.appendChild(button);
    return;
  }
  const card = document.createElement("div");
  card.className = "parent-card";
  const src = unit.thumb || unit.image;
  if (src) card.appendChild(parentThumb(unit));
  const info = document.createElement("div");
  info.innerHTML = `
    <strong>${escapeHtml(unit.name)}</strong>
    <span>ID ${unit.id} · order ${fusionOrder(unit)} · vida ${unit.life}</span>`;
  const change = document.createElement("button");
  change.type = "button";
  change.dataset.pick = role;
  change.textContent = "Trocar";
  card.append(info, change);
  slotEl.appendChild(card);
}

function setParent(role, unit) {
  if (role === "a") parentA = unit;
  else parentB = unit;
  renderSlot(role === "a" ? slotA : slotB, unit, role);
  renderMix();
  writeMixHash();
}

function renderRange(mix) {
  const maxScale = Math.max(80, Math.ceil(mix.hi / 10) * 10 + 10);
  const pct = (value) => `${Math.max(0, Math.min(100, (value / maxScale) * 100))}%`;
  rangeTrack.hidden = false;
  rangeFill.style.left = pct(mix.lo);
  rangeFill.style.width = pct(mix.hi - mix.lo);
  markA.style.left = pct(mix.orderA);
  markB.style.left = pct(mix.orderB);
  rangeLoLabel.textContent = String(Math.floor(mix.lo));
  rangeHiLabel.textContent = String(Math.ceil(mix.hi));
  rangeLoLabel.style.left = pct(mix.lo);
  rangeHiLabel.style.left = pct(mix.hi);
}

function renderMix() {
  if (!parentA || !parentB) {
    mathEl.textContent = "Escolhe os dois pais.";
    rangeTrack.hidden = true;
    if (!picker.open) fillResults();
    return;
  }

  const { mix, lo, hi } = currentRange();
  const cash = boostCash(boostLevel);
  const boostText = boostLevel
    ? ` · aprimorar +${boostLevel} (+${mix.bonus} order, ${cash} cash)`
    : "";
  const pair = IS_EMPIRES
    ? `√(<b>${escapeHtml(parentA.name)}</b> ${mix.orderA} × <b>${escapeHtml(parentB.name)}</b> ${mix.orderB})`
    : `<b>${escapeHtml(parentA.name)}</b> ${mix.orderA} + <b>${escapeHtml(parentB.name)}</b> ${mix.orderB}`;
  mathEl.innerHTML = `
    ${pair}
    → alvo <b>${mix.alvo.toFixed(1)}</b>
    · faixa <b>${lo}–${hi}</b>${boostText}`;
  renderRange(mix);
  if (!picker.open) fillResults();
}

function openViewer(unit) {
  titleEl.textContent = unit.name;
  idEl.textContent = `${unit.group_label || "Outros"} · ID ${unit.id} · order ${fusionOrder(unit)}`;
  const src = unit.anim || unit.thumb || unit.image;
  player.replaceChildren();
  if (src) {
    playerImg.alt = unit.name;
    if (playerImg.getAttribute("src") !== src) playerImg.src = src;
    player.appendChild(playerImg);
  } else {
    player.innerHTML = '<p id="player-empty">Sem sprite.</p>';
  }
  statsEl.innerHTML = `
    <div class="stat-block">
      <h3>Fusão</h3>
      <div class="stat-rows">
        <div class="stat-row"><span>Order</span><b>${fusionOrder(unit)}</b></div>
        <div class="stat-row"><span>Vida</span><b>${escapeHtml(unit.life)}</b></div>
        <div class="stat-row"><span>Ataque</span><b>${escapeHtml(unit.attack)}</b></div>
        <div class="stat-row"><span>População</span><b>${escapeHtml(unit.population)}</b></div>
      </div>
    </div>`;
  viewerLink.innerHTML = `<a href="${CATALOG_PAGE}#/unit/${unit.id}">Abrir ficha nas tropas</a>`;
  overlay.classList.add("open");
}

function closeViewer() {
  overlay.classList.remove("open");
}

function bindSlot(slotEl, role) {
  slotEl.addEventListener("click", (event) => {
    if (event.target.closest("[data-pick]")) openPicker(role);
  });
}

function applyHash() {
  if (writingHash) return;
  const mix = parseMixHash();
  if (!mix) return;
  const unitA = unitsById.get(mix.a);
  const unitB = unitsById.get(mix.b);
  if (!unitA || !unitB) return;
  boostLevel = mix.boost;
  parentA = unitA;
  parentB = unitB;
  renderBoost();
  renderSlot(slotA, parentA, "a");
  renderSlot(slotB, parentB, "b");
  renderMix();
}

async function main() {
  renderBoost();
  renderSlot(slotA, null, "a");
  renderSlot(slotB, null, "b");
  try {
    const response = await fetch(DATA_URL);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const units = await response.json();
    units.forEach((unit) => unitsById.set(unit.id, unit));
    fuseUnits = units.filter(canFuse);
    subtitle.textContent = IS_EMPIRES
      ? `${fuseUnits.length} tropas entram no Soul Mixer (sem workers, animais de pasto nem pop 0).`
      : `${fuseUnits.length} tropas entram na fusão (sem workers, chained nem exclusões).`;
    renderPickerFilters();
    buildCatalog();
    fillResults();
    applyHash();
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

bindSlot(slotA, "a");
bindSlot(slotB, "b");
document.getElementById("swap").addEventListener("click", () => {
  const previous = parentA;
  parentA = parentB;
  parentB = previous;
  renderSlot(slotA, parentA, "a");
  renderSlot(slotB, parentB, "b");
  renderMix();
  writeMixHash();
});
boostChips.addEventListener("click", (event) => {
  const button = event.target.closest("[data-boost]");
  if (!button) return;
  boostLevel = Number(button.dataset.boost);
  renderBoost();
  renderMix();
  writeMixHash();
});
document.getElementById("close").addEventListener("click", closeViewer);
pickerClose.addEventListener("click", closePicker);
picker.addEventListener("close", () => {
  pickRole = null;
  fillResults();
});
overlay.addEventListener("click", (event) => {
  if (event.target === overlay) closeViewer();
});
pickerSearch.addEventListener("input", applyPickerFilter);
pickerFilterToggle.addEventListener("click", () => {
  const open = pickerFilters.hasAttribute("hidden");
  pickerFilters.toggleAttribute("hidden", !open);
  pickerFilterToggle.setAttribute("aria-expanded", String(open));
});
sortEl.addEventListener("change", () => {
  sortKey = sortEl.value;
  if (!picker.open) fillResults();
});
document.addEventListener("keydown", (event) => {
  if (event.key !== "Escape") return;
  if (picker.open) return;
  closeViewer();
});
window.addEventListener("hashchange", applyHash);

main();
