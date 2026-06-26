const DATA_ROOT = new URL("./public/data/v1/", window.location.href);
const HERO_ASSET_ROOT = new URL("./public/assets/heroes/", window.location.href);
const state = {
  manifest: null,
  heroes: [],
  audit: null,
  portraits: {},
  selectedSlug: null,
  selectedHero: null,
  search: "",
  showRaw: false,
  copyLinkFeedbackTimer: null,
};

const elements = {
  selectView: document.querySelector("#hero-select-view"),
  statsView: document.querySelector("#stats-view"),
  search: document.querySelector("#hero-search"),
  roleSections: document.querySelector("#role-sections"),
  selectMessage: document.querySelector("#select-message"),
  heroDetail: document.querySelector("#hero-detail"),
  auditStatus: document.querySelector("#audit-status"),
  rawToggle: document.querySelector("#raw-toggle"),
  allHeroes: document.querySelector("#all-heroes"),
};

document.addEventListener("DOMContentLoaded", init);

async function init() {
  try {
    const [manifest, heroes, audit, portraits] = await Promise.all([
      fetchJson("manifest.json"),
      fetchJson("heroes.index.json"),
      fetchJson("audit-summary.json"),
      fetchPortraitManifest(),
    ]);
    state.manifest = manifest;
    state.heroes = heroes;
    state.audit = audit;
    state.portraits = portraits;

    bindEvents();

    const requestedSlug = getHeroSlugFromUrl();
    const initialHero = getHeroFromUrl();
    if (initialHero) {
      await selectHero(initialHero);
    } else if (requestedSlug) {
      showHeroSelect("Hero not found. Choose a hero below.");
    } else {
      showHeroSelect();
    }
  } catch (error) {
    elements.selectView.hidden = true;
    elements.statsView.hidden = false;
    elements.heroDetail.innerHTML = `
      <div class="empty-state error">
        <h2>Data could not be loaded</h2>
        <p>${escapeHtml(error.message)}</p>
      </div>
    `;
  }
}

async function fetchPortraitManifest() {
  const url = new URL("manifest.json", HERO_ASSET_ROOT).href;
  try {
    const response = await fetch(url);
    if (!response.ok) {
      return {};
    }
    const entries = await response.json();
    return Object.fromEntries(entries.map((entry) => [entry.hero_slug, entry]));
  } catch {
    return {};
  }
}

function bindEvents() {
  elements.search.addEventListener("input", (event) => {
    state.search = event.target.value.trim().toLowerCase();
    renderHeroSelect();
  });

  elements.rawToggle.addEventListener("click", () => {
    state.showRaw = !state.showRaw;
    elements.rawToggle.setAttribute("aria-pressed", String(state.showRaw));
    elements.rawToggle.textContent = state.showRaw ? "Hide raw values" : "Show raw values";
    if (state.selectedHero) {
      renderHeroDetail(state.selectedHero);
    }
  });

  elements.allHeroes.addEventListener("click", () => {
    showHeroSelect("", { historyMode: "push" });
  });

  window.addEventListener("popstate", () => {
    const requestedSlug = getHeroSlugFromUrl();
    const hero = getHeroFromUrl();
    if (hero) {
      selectHero(hero);
    } else if (requestedSlug) {
      showHeroSelect("Hero not found. Choose a hero below.");
    } else {
      showHeroSelect();
    }
  });
}

async function fetchJson(path) {
  const url = resolveDataUrl(path);
  let response;

  try {
    response = await fetch(url);
  } catch (error) {
    throw new Error(
      `Failed to load ${path} from ${url}. ${error.message}. Serve the site with python -m http.server instead of opening index.html directly.`,
    );
  }

  if (!response.ok) {
    throw new Error(`Failed to load ${path} from ${url}: ${response.status}`);
  }
  return response.json();
}

function resolveDataUrl(path) {
  const normalizedPath = String(path || "")
    .replaceAll("\\", "/")
    .replace(/^\.?\//, "");

  if (/^https?:\/\//.test(normalizedPath)) {
    return normalizedPath;
  }

  const dataPath = normalizedPath
    .replace(/^site\/public\/data\/v1\//, "")
    .replace(/^public\/data\/v1\//, "")
    .replace(/^data\/v1\//, "");

  return new URL(dataPath, DATA_ROOT).href;
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

function showHeroSelect(message = "", options = {}) {
  const { historyMode = "none" } = options;
  state.selectedSlug = null;
  state.selectedHero = null;
  clearCopyLinkFeedback();
  updateSelectorUrl(historyMode);

  elements.selectView.hidden = false;
  elements.statsView.hidden = true;
  elements.rawToggle.hidden = true;
  elements.allHeroes.hidden = true;
  elements.selectMessage.textContent = message;
  renderHeroSelect();
}

function renderHeroSelect() {
  const filtered = state.heroes.filter((hero) => hero.name.toLowerCase().includes(state.search));
  const grouped = groupHeroesByRole(filtered);
  const sections = ["Tank", "Damage", "Support", "Unknown"]
    .filter((role) => grouped[role]?.length)
    .map((role) => renderRoleSection(role, grouped[role]));

  elements.roleSections.innerHTML = sections.length
    ? sections.join("")
    : `<div class="empty-state selector-empty"><h2>No matches</h2><p>Try a different hero name.</p></div>`;

  elements.roleSections.querySelectorAll("[data-hero-slug]").forEach((button) => {
    button.addEventListener("click", () => {
      const hero = state.heroes.find((item) => item.slug === button.dataset.heroSlug);
      if (hero) {
        selectHero(hero, { historyMode: "push" });
      }
    });
  });
}

function groupHeroesByRole(heroes) {
  return heroes.reduce((groups, hero) => {
    const role = ["Tank", "Damage", "Support"].includes(hero.role) ? hero.role : "Unknown";
    groups[role] = groups[role] || [];
    groups[role].push(hero);
    return groups;
  }, {});
}

function renderRoleSection(role, heroes) {
  return `
    <section class="role-section role-section-${escapeHtml(role.toLowerCase())}">
      <div class="role-section-heading">
        <h3>${escapeHtml(role)}</h3>
        <span>${heroes.length} heroes</span>
      </div>
      <div class="hero-tile-grid">
        ${heroes.map(renderHeroTile).join("")}
      </div>
    </section>
  `;
}

function renderHeroTile(hero) {
  const portrait = renderHeroTilePortrait(hero);
  return `
    <button class="hero-tile" type="button" data-hero-slug="${escapeHtml(hero.slug)}">
      ${portrait}
      <span class="hero-tile-name">${escapeHtml(hero.name)}</span>
    </button>
  `;
}

function renderHeroTilePortrait(hero) {
  const portrait = state.portraits?.[hero.slug];
  if (portrait?.local_path) {
    const src = resolvePublicAssetUrl(portrait.local_path);
    return `<span class="hero-tile-image-wrap"><img src="${escapeHtml(src)}" alt="${escapeHtml(hero.name)} portrait" loading="lazy"></span>`;
  }

  return `
    <span class="hero-tile-fallback" aria-hidden="true">
      ${escapeHtml(heroInitials(hero.name))}
    </span>
  `;
}

async function selectHero(indexHero, options = {}) {
  const { historyMode = "none" } = options;
  state.selectedSlug = indexHero.slug;
  elements.selectView.hidden = true;
  elements.statsView.hidden = false;
  elements.rawToggle.hidden = false;
  elements.allHeroes.hidden = false;
  renderAuditStatus();
  elements.heroDetail.innerHTML = `<div class="empty-state"><p>Loading ${escapeHtml(indexHero.name)}...</p></div>`;

  updateHeroUrl(indexHero.slug, historyMode);

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
        <div class="detail-identity">
          ${renderHeroPortrait(hero.slug, hero.name, "hero-portrait")}
          <div>
            <div class="hero-title-row">
              <h2>${escapeHtml(hero.name)}</h2>
              <button class="copy-link-button" type="button" data-copy-link>Copy link</button>
            </div>
            <p>
              <span class="role-pill ${roleClass(hero.role)}">${escapeHtml(hero.role || "Unknown")}</span>
              ${hero.sub_role ? `<span class="muted">${escapeHtml(hero.sub_role)}</span>` : ""}
            </p>
            <p class="copy-link-feedback" aria-live="polite" data-copy-link-feedback></p>
          </div>
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

  const copyButton = elements.heroDetail.querySelector("[data-copy-link]");
  copyButton?.addEventListener("click", () => copySelectedHeroLink(hero.slug));
}

function renderHeroPortrait(slug, name, className) {
  const portrait = state.portraits?.[slug];
  if (!portrait?.local_path) {
    return "";
  }
  const src = resolvePublicAssetUrl(portrait.local_path);
  return `<img class="${className}" src="${escapeHtml(src)}" alt="${escapeHtml(name)} portrait" loading="lazy">`;
}

function resolvePublicAssetUrl(path) {
  const normalizedPath = String(path || "")
    .replaceAll("\\", "/")
    .replace(/^\.?\//, "")
    .replace(/^site\/public\//, "")
    .replace(/^public\//, "");
  return new URL(normalizedPath, new URL("./public/", window.location.href)).href;
}

async function copySelectedHeroLink(slug) {
  const url = buildHeroUrl(slug);
  const feedback = elements.heroDetail.querySelector("[data-copy-link-feedback]");

  clearCopyLinkFeedback();

  if (navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(url);
      showCopyLinkFeedback("Copied link");
      return;
    } catch {
      showCopyLinkFeedback(`Copy failed. Link: ${url}`);
      return;
    }
  }

  if (feedback) {
    feedback.innerHTML = `Copy this link: <span>${escapeHtml(url)}</span>`;
  }
}

function clearCopyLinkFeedback() {
  if (state.copyLinkFeedbackTimer) {
    window.clearTimeout(state.copyLinkFeedbackTimer);
    state.copyLinkFeedbackTimer = null;
  }
}

function showCopyLinkFeedback(message) {
  const feedback = elements.heroDetail.querySelector("[data-copy-link-feedback]");
  if (!feedback) {
    return;
  }

  feedback.textContent = message;
  state.copyLinkFeedbackTimer = window.setTimeout(() => {
    feedback.textContent = "";
    state.copyLinkFeedbackTimer = null;
  }, 1800);
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
  const componentsHtml = stat.components?.length ? renderStatComponents(stat.components) : "";
  const rawText = displayRaw(stat);
  const rawHtml = state.showRaw && hasText(rawText)
    ? `<div class="raw-value">Raw: ${escapeHtml(rawText)}</div>`
    : "";
  const warningHtml = stat.warnings?.length
    ? `<div class="stat-warnings">${stat.warnings.map((warning) => `Warning: ${escapeHtml(warning)}`).join("<br>")}</div>`
    : "";

  return `
    <div class="stat-row">
      <div class="stat-label">${escapeHtml(stat.label || stat.field)}</div>
      <div class="stat-value">
        <span>${formatted}</span>
        ${componentsHtml}
        ${rawHtml}
        ${warningHtml}
      </div>
      <div><span class="confidence ${confidenceClass(stat.confidence)}">${escapeHtml(stat.confidence || "unparsed")}</span></div>
    </div>
  `;
}

function renderStatComponents(components) {
  return `
    <div class="stat-components">
      <div class="stat-components-title">Breakdown</div>
      <div class="stat-component-grid">
      ${components.map(renderStatComponent).join("")}
      </div>
    </div>
  `;
}

function renderStatComponent(component) {
  const rawText = displayRaw(component);
  const rawHtml = state.showRaw && hasText(rawText)
    ? `<div class="component-raw">Raw: ${escapeHtml(rawText)}</div>`
    : "";
  const notesHtml = component.notes?.length
    ? `<div class="component-notes">${component.notes.map(escapeHtml).join("; ")}</div>`
    : "";
  const warningHtml = component.warnings?.length
    ? `<div class="component-warnings">${component.warnings.map(escapeHtml).join("; ")}</div>`
    : "";

  return `
    <article class="stat-component-card">
      <div class="component-label">${escapeHtml(titleCase(component.label || "component"))}</div>
      <div class="component-value">${formatComponentValue(component)}</div>
      ${notesHtml}
      ${rawHtml}
      ${warningHtml}
    </article>
  `;
}

function formatComponentValue(component) {
  if (component.min_value !== null && component.min_value !== undefined && component.max_value !== null && component.max_value !== undefined) {
    return `${formatNumber(component.min_value)}-${formatNumber(component.max_value)} ${escapeHtml(component.unit || "")}`.trim();
  }
  if (component.value !== null && component.value !== undefined && component.value !== "") {
    return `${formatNumber(component.value)} ${escapeHtml(component.unit || "")}`.trim();
  }
  const rawText = displayRaw(component);
  if (hasText(rawText)) {
    return `Raw: ${escapeHtml(rawText)}`;
  }
  return "-";
}

function formatStatValue(stat) {
  if (stat.components?.length) {
    return `<span class="not-parsed">No single value; see breakdown</span>`;
  }
  if (stat.min_value !== null && stat.min_value !== undefined && stat.max_value !== null && stat.max_value !== undefined) {
    return `${formatNumber(stat.min_value)}-${formatNumber(stat.max_value)} ${escapeHtml(stat.unit || "")}`.trim();
  }
  if (stat.value !== null && stat.value !== undefined && stat.value !== "") {
    return `${formatNumber(stat.value)} ${escapeHtml(stat.unit || "")}`.trim();
  }
  const rawText = displayRaw(stat);
  if (hasText(rawText)) {
    return `<span class="not-parsed">Not safely parsed: Raw: ${escapeHtml(rawText)}</span>`;
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
  return `<div><dt>${label}</dt><dd>${value ?? "-"}</dd></div>`;
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

function getHeroFromUrl() {
  const slug = getHeroSlugFromUrl();
  if (!slug) {
    return null;
  }

  return state.heroes.find((hero) => hero.slug === slug) || null;
}

function getHeroSlugFromUrl() {
  const slug = new URLSearchParams(window.location.search).get("hero");
  return slug ? slug.toLowerCase() : null;
}

function updateHeroUrl(slug, historyMode) {
  if (historyMode === "none") {
    return;
  }

  const url = buildHeroUrl(slug);
  if (url === window.location.href) {
    return;
  }

  if (historyMode === "replace") {
    window.history.replaceState({ hero: slug }, "", url);
    return;
  }

  if (historyMode === "push") {
    window.history.pushState({ hero: slug }, "", url);
  }
}

function buildHeroUrl(slug) {
  const url = new URL(window.location.href);
  url.searchParams.set("hero", slug);
  return url.href;
}

function updateSelectorUrl(historyMode) {
  if (historyMode === "none") {
    return;
  }

  const url = new URL(window.location.href);
  url.searchParams.delete("hero");
  if (url.href === window.location.href) {
    return;
  }

  if (historyMode === "replace") {
    window.history.replaceState({}, "", url.href);
    return;
  }

  if (historyMode === "push") {
    window.history.pushState({}, "", url.href);
  }
}

function titleCase(value) {
  return String(value)
    .replaceAll("_", " ")
    .replace(/\w\S*/g, (word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase());
}

function heroInitials(name) {
  return String(name)
    .split(/[\s.-]+/)
    .filter(Boolean)
    .map((part) => part[0])
    .join("")
    .slice(0, 3)
    .toUpperCase();
}

function displayRaw(item) {
  return hasText(item?.raw_display) ? item.raw_display : item?.raw;
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
