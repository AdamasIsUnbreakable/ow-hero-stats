const DATA_ROOT = "./public/data/v1/";
const state = {
  manifest: null,
  heroes: [],
  audit: null,
  selectedSlug: null,
  selectedHero: null,
  search: "",
  role: "All",
  showRaw: false,
};

const elements = {
  search: document.querySelector("#hero-search"),
  role: document.querySelector("#role-filter"),
  heroList: document.querySelector("#hero-list"),
  heroCount: document.querySelector("#hero-count"),
  heroDetail: document.querySelector("#hero-detail"),
  auditStatus: document.querySelector("#audit-status"),
  rawToggle: document.querySelector("#raw-toggle"),
};

document.addEventListener("DOMContentLoaded", init);

async function init() {
  try {
    const [manifest, heroes, audit] = await Promise.all([
      fetchJson("manifest.json"),
      fetchJson("heroes.index.json"),
      fetchJson("audit-summary.json"),
    ]);
    state.manifest = manifest;
    state.heroes = heroes;
    state.audit = audit;

    bindEvents();
    renderAuditStatus();
    renderHeroList();

    if (heroes.length > 0) {
      await selectHero(heroes[0]);
    }
  } catch (error) {
    elements.heroDetail.innerHTML = `
      <div class="empty-state error">
        <h2>Data could not be loaded</h2>
        <p>${escapeHtml(error.message)}</p>
      </div>
    `;
  }
}

function bindEvents() {
  elements.search.addEventListener("input", (event) => {
    state.search = event.target.value.trim().toLowerCase();
    renderHeroList();
  });

  elements.role.addEventListener("change", (event) => {
    state.role = event.target.value;
    renderHeroList();
  });

  elements.rawToggle.addEventListener("click", () => {
    state.showRaw = !state.showRaw;
    elements.rawToggle.setAttribute("aria-pressed", String(state.showRaw));
    elements.rawToggle.textContent = state.showRaw ? "Hide raw values" : "Show raw values";
    if (state.selectedHero) {
      renderHeroDetail(state.selectedHero);
    }
  });
}

async function fetchJson(path) {
  const response = await fetch(`${DATA_ROOT}${path}`);
  if (!response.ok) {
    throw new Error(`Failed to load ${path}: ${response.status}`);
  }
  return response.json();
}

function renderAuditStatus() {
  const totals = state.audit?.totals || {};
  const sourceValidation = state.audit?.source_validation || {};
  const missingMetadata = sourceValidation.heroes_missing_metadata?.length || 0;
  const missingAbilities = sourceValidation.heroes_missing_abilities?.length || 0;
  const generatedAt = state.manifest?.generated_at || "unknown";

  elements.auditStatus.innerHTML = `
    <div>
      <h2>Data status</h2>
      <p class="muted">Generated ${escapeHtml(generatedAt)} from ${escapeHtml(state.manifest?.source || "unknown source")}.</p>
    </div>
    <dl class="status-grid">
      <div><dt>Heroes</dt><dd>${formatNumber(totals.playable_heroes)}</dd></div>
      <div><dt>Ability rows</dt><dd>${formatNumber(totals.ability_rows)}</dd></div>
      <div><dt>Missing metadata</dt><dd>${formatNumber(missingMetadata)}</dd></div>
      <div><dt>Missing abilities</dt><dd>${formatNumber(missingAbilities)}</dd></div>
    </dl>
  `;
}

function renderHeroList() {
  const filtered = state.heroes.filter((hero) => {
    const matchesSearch = hero.name.toLowerCase().includes(state.search);
    const matchesRole = state.role === "All" || hero.role === state.role;
    return matchesSearch && matchesRole;
  });

  elements.heroCount.textContent = `${filtered.length} shown`;
  elements.heroList.innerHTML = filtered.map(renderHeroCard).join("");

  elements.heroList.querySelectorAll("[data-hero-slug]").forEach((button) => {
    button.addEventListener("click", () => {
      const hero = state.heroes.find((item) => item.slug === button.dataset.heroSlug);
      if (hero) {
        selectHero(hero);
      }
    });
  });
}

function renderHeroCard(hero) {
  const activeClass = hero.slug === state.selectedSlug ? " active" : "";
  return `
    <button class="hero-card${activeClass}" type="button" data-hero-slug="${escapeHtml(hero.slug)}">
      <span class="hero-card-main">
        <strong>${escapeHtml(hero.name)}</strong>
        <span class="role-pill ${roleClass(hero.role)}">${escapeHtml(hero.role || "Unknown")}</span>
      </span>
      <span class="hero-card-meta">
        ${formatHealth(hero.health)} &middot; ${hero.ability_count} abilities &middot; ${hero.warning_count} warnings
      </span>
      <span class="confidence-summary">${renderConfidenceSummary(hero.confidence_counts)}</span>
    </button>
  `;
}

async function selectHero(indexHero) {
  state.selectedSlug = indexHero.slug;
  renderHeroList();
  elements.heroDetail.innerHTML = `<div class="empty-state"><p>Loading ${escapeHtml(indexHero.name)}...</p></div>`;

  try {
    const detail = await fetchJson(indexHero.detail_path);
    state.selectedHero = detail;
    renderHeroDetail(detail);
  } catch (error) {
    elements.heroDetail.innerHTML = `
      <div class="empty-state error">
        <h2>Hero detail could not be loaded</h2>
        <p>${escapeHtml(error.message)}</p>
      </div>
    `;
  }
}

function renderHeroDetail(hero) {
  elements.heroDetail.innerHTML = `
    <article>
      <header class="detail-header">
        <div>
          <h2>${escapeHtml(hero.name)}</h2>
          <p>
            <span class="role-pill ${roleClass(hero.role)}">${escapeHtml(hero.role || "Unknown")}</span>
            ${hero.sub_role ? `<span class="muted">${escapeHtml(hero.sub_role)}</span>` : ""}
          </p>
        </div>
        <dl class="health-grid">
          ${renderHealthCell("Health", hero.health?.health)}
          ${renderHealthCell("Armor", hero.health?.armor)}
          ${renderHealthCell("Shield", hero.health?.shield)}
        </dl>
      </header>

      <section class="summary-card">
        <h3>Audit</h3>
        <p>${hero.audit?.warning_count || 0} parser warnings</p>
        <div class="confidence-summary">${renderConfidenceSummary(hero.audit?.confidence_counts || {})}</div>
        ${renderWarningsByAbility(hero.audit?.warnings_by_ability || {})}
      </section>

      <section class="ability-list">
        ${hero.abilities.map(renderAbilityCard).join("")}
      </section>
    </article>
  `;
}

function renderAbilityCard(ability) {
  const stats = Object.values(ability.stats || {});
  return `
    <article class="ability-card">
      <header>
        <div>
          <h3>${escapeHtml(ability.name)}</h3>
          <p class="muted">
            ${escapeHtml(ability.slot || "No slot")} &middot; ${escapeHtml(ability.type || "No type")}
          </p>
        </div>
      </header>
      ${ability.shot_type?.length ? `<p class="shot-type">${ability.shot_type.map(escapeHtml).join(", ")}</p>` : ""}
      <div class="stat-table">
        ${stats.map(renderStatRow).join("")}
      </div>
      ${ability.parse_warnings?.length ? renderWarningList(ability.parse_warnings) : ""}
    </article>
  `;
}

function renderStatRow(stat) {
  const formatted = formatStatValue(stat);
  const rawHtml = state.showRaw && hasText(stat.raw)
    ? `<div class="raw-value">Raw: ${escapeHtml(stat.raw)}</div>`
    : "";
  const warningHtml = stat.warnings?.length
    ? `<div class="stat-warnings">${stat.warnings.map((warning) => `Warning: ${escapeHtml(warning)}`).join("<br>")}</div>`
    : "";

  return `
    <div class="stat-row">
      <div class="stat-label">${escapeHtml(stat.label || stat.field)}</div>
      <div class="stat-value">
        <span>${formatted}</span>
        ${rawHtml}
        ${warningHtml}
      </div>
      <div><span class="confidence ${confidenceClass(stat.confidence)}">${escapeHtml(stat.confidence || "unparsed")}</span></div>
    </div>
  `;
}

function formatStatValue(stat) {
  if (stat.min_value !== null && stat.min_value !== undefined && stat.max_value !== null && stat.max_value !== undefined) {
    return `${formatNumber(stat.min_value)}-${formatNumber(stat.max_value)} ${escapeHtml(stat.unit || "")}`.trim();
  }
  if (stat.value !== null && stat.value !== undefined && stat.value !== "") {
    return `${formatNumber(stat.value)} ${escapeHtml(stat.unit || "")}`.trim();
  }
  if (hasText(stat.raw)) {
    return `<span class="not-parsed">Raw: ${escapeHtml(stat.raw)}</span>`;
  }
  return "-";
}

function renderWarningsByAbility(grouped) {
  const entries = Object.entries(grouped).filter(([, warnings]) => warnings.length);
  if (!entries.length) {
    return "";
  }
  return `
    <div class="warning-panel">
      <h4>Warnings by ability</h4>
      ${entries.map(([ability, warnings]) => `
        <div>
          <strong>${escapeHtml(ability)}</strong>
          ${renderWarningList(warnings)}
        </div>
      `).join("")}
    </div>
  `;
}

function renderWarningList(warnings) {
  return `
    <ul class="warning-list">
      ${warnings.map((warning) => `<li>${escapeHtml(warning)}</li>`).join("")}
    </ul>
  `;
}

function renderConfidenceSummary(counts) {
  return ["high", "medium", "low", "unparsed"].map((key) => {
    const count = counts?.[key] || 0;
    return `<span class="confidence ${confidenceClass(key)}">${key}: ${count}</span>`;
  }).join("");
}

function renderHealthCell(label, value) {
  return `<div><dt>${label}</dt><dd>${value ?? "—"}</dd></div>`;
}

function formatHealth(health = {}) {
  const parts = [];
  if (health.health !== null && health.health !== undefined) parts.push(`${health.health} HP`);
  if (health.armor !== null && health.armor !== undefined) parts.push(`${health.armor} Armor`);
  if (health.shield !== null && health.shield !== undefined) parts.push(`${health.shield} Shield`);
  return parts.length ? parts.join(" / ") : "No health";
}

function formatNumber(value) {
  if (value === null || value === undefined) {
    return "0";
  }
  return typeof value === "number" ? Number(value.toFixed(3)).toString() : String(value);
}

function confidenceClass(confidence) {
  return `confidence-${confidence || "unparsed"}`;
}

function roleClass(role) {
  return `role-${String(role || "unknown").toLowerCase()}`;
}

function hasText(value) {
  return value !== null && value !== undefined && String(value).trim() !== "";
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
