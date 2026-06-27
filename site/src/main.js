const DATA_ROOT = new URL("./public/data/v1/", window.location.href);
const HERO_ASSET_ROOT = new URL("./public/assets/heroes/", window.location.href);
const ABILITY_ASSET_ROOT = new URL("./public/assets/abilities/", window.location.href);
const state = {
  manifest: null,
  heroes: [],
  audit: null,
  portraits: {},
  abilityIcons: [],
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
    const [manifest, heroes, audit, portraits, abilityIcons] = await Promise.all([
      fetchJson("manifest.json"),
      fetchJson("heroes.index.json"),
      fetchJson("audit-summary.json"),
      fetchPortraitManifest(),
      fetchAbilityIconManifest(),
    ]);
    state.manifest = manifest;
    state.heroes = heroes;
    state.audit = audit;
    state.portraits = portraits;
    state.abilityIcons = abilityIcons;

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

async function fetchAbilityIconManifest() {
  const url = new URL("manifest.json", ABILITY_ASSET_ROOT).href;
  try {
    const response = await fetch(url);
    if (!response.ok) {
      return {};
    }
    const entries = await response.json();
    return Array.isArray(entries) ? entries : [];
  } catch {
    return [];
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
    state.search = "";
    elements.search.value = "";
    showHeroSelect("", { historyMode: "push" });
    elements.search.focus();
  });

  document.addEventListener("click", (event) => {
    if (!event.target.closest("[data-ability-row]")) {
      closeExpandedAbilityRows();
    }
  });

  window.addEventListener("resize", positionOpenAbilityPanel);
  window.addEventListener("scroll", positionOpenAbilityPanel, true);

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
    detail.abilities = (detail.abilities || []).map((ability, abilityIndex) => ({
      ...ability,
      ability_index: ability.ability_index ?? abilityIndex,
    }));
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
  const groups = groupHeroAbilities(hero.abilities || []);
  elements.heroDetail.innerHTML = `
    <article class="hero-info-page">
      ${renderHeroBackdrop(hero)}
      <div class="hero-info-layout">
        <section class="hero-info-column hero-info-left">
          <div class="ow-section-title">Hero &amp; Weapon</div>
          <header class="ow-hero-card">
            ${renderHeroIdentityPortrait(hero)}
            <div>
              <div class="hero-title-row">
                <h2>${escapeHtml(hero.name)}</h2>
                <button class="copy-link-button" type="button" data-copy-link>Copy link</button>
              </div>
              <p>
                <span class="role-pill ${roleClass(hero.role)}">${escapeHtml(hero.role || "Unknown")}</span>
                ${hero.sub_role ? `<span class="ow-muted">${escapeHtml(hero.sub_role)}</span>` : ""}
              </p>
              <p class="copy-link-feedback" aria-live="polite" data-copy-link-feedback></p>
            </div>
          </header>

          <section class="ow-panel">
            <h3>Hero Stats</h3>
            <dl class="ow-health-grid">
              ${renderHealthCell("Health", hero.health?.health)}
              ${renderHealthCell("Armor", hero.health?.armor)}
              ${renderHealthCell("Shield", hero.health?.shield)}
            </dl>
            <div class="confidence-summary">${renderConfidenceSummary(hero.audit?.confidence_counts || {})}</div>
            <p class="ow-muted">${hero.audit?.warning_count || 0} parser warnings</p>
          </section>

          ${renderAbilitySection("Weapons", groups.weapons)}
          ${renderAbilitySection("Ultimate", groups.ultimate)}
        </section>

        <section class="hero-info-column hero-info-middle">
          ${renderAbilitySection("Abilities", groups.abilities, "primary")}
          ${renderAbilitySection("Passive", groups.passive)}
        </section>

        <section class="hero-info-column hero-info-right">
          ${renderPerkSection(groups.perks)}
          <section class="ow-panel ow-audit-panel">
            <h3>Data Notes</h3>
            ${renderWarningsByAbility(hero.audit?.warnings_by_ability || {}) || '<p class="ow-muted">No parser warnings for this hero.</p>'}
          </section>
        </section>
      </div>
    </article>
  `;

  const copyButton = elements.heroDetail.querySelector("[data-copy-link]");
  copyButton?.addEventListener("click", () => copySelectedHeroLink(hero.slug));
  bindAbilityRows();
}

function renderHeroBackdrop(hero) {
  const portrait = state.portraits?.[hero.slug];
  if (!portrait?.local_path) {
    return `<div class="hero-backdrop hero-backdrop-fallback">${escapeHtml(heroInitials(hero.name))}</div>`;
  }
  const src = resolvePublicAssetUrl(portrait.local_path);
  return `<div class="hero-backdrop" style="background-image: url('${escapeHtml(src)}')"></div>`;
}

function renderHeroIdentityPortrait(hero) {
  return renderHeroPortrait(hero.slug, hero.name, "ow-hero-portrait")
    || `<span class="ow-hero-portrait hero-portrait-fallback">${escapeHtml(heroInitials(hero.name))}</span>`;
}

function groupHeroAbilities(abilities) {
  return abilities.reduce((groups, ability) => {
    groups[abilityGroup(ability)].push(ability);
    return groups;
  }, { weapons: [], abilities: [], passive: [], ultimate: [], perks: [] });
}

function abilityGroup(ability) {
  const type = String(ability.type || "").toLowerCase();
  const slot = String(ability.slot || "").toLowerCase();
  const name = String(ability.name || "").toLowerCase();
  if (type.includes("perk")) return "perks";
  if (type.includes("passive") || slot.includes("passive")) return "passive";
  if (type.includes("ultimate") || slot.includes("ultimate") || name.includes("ultimate")) return "ultimate";
  if (type.includes("weapon") || slot.includes("primary fire") || slot.includes("secondary fire")) return "weapons";
  return "abilities";
}

function renderAbilitySection(title, abilities, variant = "") {
  if (!abilities.length) {
    return "";
  }
  return `
    <section class="ow-ability-section ${variant ? `ow-ability-section-${variant}` : ""}">
      <div class="ow-section-title">${escapeHtml(title)}</div>
      <div class="ow-ability-list">
        ${abilities.map(renderAbilityRow).join("")}
      </div>
    </section>
  `;
}

function renderPerkSection(perks) {
  if (!perks.length) {
    return `
      <section class="ow-ability-section">
        <div class="ow-section-title">Perks</div>
        <div class="ow-panel ow-empty-panel">No perk data available.</div>
      </section>
    `;
  }
  const minor = perks.filter((perk) => String(perk.type || "").toLowerCase().includes("minor"));
  const major = perks.filter((perk) => String(perk.type || "").toLowerCase().includes("major"));
  const other = perks.filter((perk) => !minor.includes(perk) && !major.includes(perk));
  return `
    <section class="ow-ability-section">
      <div class="ow-section-title">Perks</div>
      ${minor.length ? `<div class="ow-subtitle">Minor</div><div class="ow-ability-list">${minor.map(renderAbilityRow).join("")}</div>` : ""}
      ${major.length ? `<div class="ow-subtitle">Major</div><div class="ow-ability-list">${major.map(renderAbilityRow).join("")}</div>` : ""}
      ${other.length ? `<div class="ow-ability-list">${other.map(renderAbilityRow).join("")}</div>` : ""}
    </section>
  `;
}

function renderAbilityRow(ability) {
  return `
    <article class="ow-ability-row" tabindex="0" data-ability-row>
      ${renderAbilityVisual(ability, "ow-ability-icon")}
      <div class="ow-ability-summary">
        <div class="ow-ability-heading">
          <h3>${escapeHtml(ability.name)}</h3>
          ${ability.slot ? `<span class="slot-badge">${escapeHtml(ability.slot)}</span>` : ""}
        </div>
        ${abilityDescription(ability) ? `<p>${escapeHtml(abilityDescription(ability))}</p>` : ""}
      </div>
      ${renderAbilityDetailPanel(ability)}
    </article>
  `;
}

function renderAbilityDetailPanel(ability) {
  const keywords = abilityKeywords(ability);
  const shotTypes = abilityShotTypes(ability);
  const notes = abilityNotes(ability);
  const description = abilityDescription(ability);
  const cooldown = hasDisplayableStat(ability.stats?.cooldown) ? stripHtml(formatStatValue(ability.stats.cooldown)) : "";
  const stats = Object.values(ability.stats || {}).filter(hasDisplayableStat);
  return `
    <aside class="ability-detail-panel">
      <div class="ability-detail-header">
        ${renderAbilityVisual(ability, "ability-detail-icon")}
        <div>
          <h4>${escapeHtml(ability.name)}</h4>
          <p>${[cooldown, ability.slot].filter(Boolean).map(escapeHtml).join(" | ")}</p>
        </div>
      </div>
      ${description ? `<p class="ability-detail-description">${escapeHtml(description)}</p>` : ""}
      ${shotTypes.length ? `<div class="ability-shot-types"><strong>Shot type</strong> ${shotTypes.map((shotType) => `<span>${escapeHtml(shotType)}</span>`).join("")}</div>` : ""}
      ${keywords.length ? `<div class="keyword-chips">${keywords.map((keyword) => `<span>${escapeHtml(keyword)}</span>`).join("")}</div>` : ""}
      <div class="ability-detail-stats">
        ${stats.length ? stats.map(renderDetailStat).join("") : '<p class="ow-muted">No parsed stat fields.</p>'}
      </div>
      ${notes.length ? renderAbilityNotes(notes) : ""}
      ${ability.parse_warnings?.length ? renderWarningList(ability.parse_warnings) : ""}
    </aside>
  `;
}

function renderDetailStat(stat) {
  const rawText = displayRaw(stat);
  const rawHtml = state.showRaw && hasText(rawText) ? `<div class="raw-value">Raw: ${escapeHtml(rawText)}</div>` : "";
  const warnings = stat.warnings?.length ? `<div class="stat-warnings">${stat.warnings.map((warning) => `Warning: ${escapeHtml(warning)}`).join("<br>")}</div>` : "";
  return `
    <section class="detail-stat">
      <div class="detail-stat-top">
        <h5>${escapeHtml(stat.label || stat.field)}</h5>
        <span class="confidence ${confidenceClass(stat.confidence)}">${escapeHtml(stat.confidence || "unparsed")}</span>
      </div>
      <div class="detail-stat-value">${formatStatValue(stat)}</div>
      ${stat.components?.length ? renderStatComponents(stat.components) : ""}
      ${rawHtml}
      ${warnings}
    </section>
  `;
}

function abilityDescription(ability) {
  return firstTextField(ability, [
    "official_description",
    "official description",
    "description",
    "summary",
  ]);
}

function abilityKeywords(ability) {
  const source = firstTextField(ability, ["ability_keywords", "ability keywords"]);
  return uniqueTextItems(String(source).split(/::|;;|[;,]/));
}

function abilityShotTypes(ability) {
  const source = firstTextField(ability, ["shot_type", "shot type"]);
  const values = source ? String(source).split(/::|;;|[;,]/) : (ability.shot_type || []);
  return uniqueTextItems(values);
}

function abilityNotes(ability) {
  const source = firstTextField(ability, ["ability_details", "ability details"]);
  if (!hasText(source)) {
    return [];
  }
  return uniqueTextItems(String(source).split(/\s*\*\s+|;;|::/));
}

function uniqueTextItems(items) {
  return [...new Set(items.map((item) => String(item).trim()).filter(Boolean))];
}

function renderAbilityNotes(notes) {
  return `
    <section class="ability-gameplay-notes">
      <h5>Gameplay notes</h5>
      <ul>${notes.map((note) => `<li>${escapeHtml(note)}</li>`).join("")}</ul>
    </section>
  `;
}

function firstTextField(ability, keys) {
  for (const source of [ability.raw_display, ability.raw]) {
    for (const key of keys) {
      if (hasText(source?.[key])) {
        return source[key];
      }
    }
  }
  return "";
}

function bindAbilityRows() {
  elements.heroDetail.querySelectorAll("[data-ability-row]").forEach((row) => {
    row.addEventListener("pointerenter", () => {
      if (hasExpandedAbilityRow()) {
        return;
      }
      row.classList.add("hovered");
      positionAbilityPanel(row);
    });
    row.addEventListener("pointerleave", () => row.classList.remove("hovered"));
    row.addEventListener("focusin", () => {
      if (hasExpandedAbilityRow()) {
        return;
      }
      row.classList.add("keyboard-open");
      positionAbilityPanel(row);
    });
    row.addEventListener("focusout", () => row.classList.remove("keyboard-open"));
    row.addEventListener("click", (event) => {
      event.stopPropagation();
      toggleExpandedAbilityRow(row);
    });
    row.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        toggleExpandedAbilityRow(row);
      }
      if (event.key === "Escape") {
        closeExpandedAbilityRows();
      }
    });
  });
}

function toggleExpandedAbilityRow(row) {
  const shouldOpen = !row.classList.contains("expanded");
  closeExpandedAbilityRows();
  if (!shouldOpen) {
    return;
  }
  elements.heroDetail.querySelectorAll("[data-ability-row]").forEach((candidate) => {
    candidate.classList.remove("hovered", "keyboard-open");
  });
  row.classList.add("expanded");
  elements.heroDetail.classList.add("has-pinned-tooltip");
  positionAbilityPanel(row);
}

function closeExpandedAbilityRows() {
  elements.heroDetail.querySelectorAll("[data-ability-row].expanded").forEach((row) => {
    row.classList.remove("expanded");
  });
  elements.heroDetail.classList.remove("has-pinned-tooltip");
}

function hasExpandedAbilityRow() {
  return Boolean(elements.heroDetail.querySelector("[data-ability-row].expanded"));
}

function positionOpenAbilityPanel() {
  const row = elements.heroDetail.querySelector(
    "[data-ability-row].expanded, [data-ability-row].hovered, [data-ability-row].keyboard-open",
  );
  if (row) {
    positionAbilityPanel(row);
  }
}

function positionAbilityPanel(row) {
  if (window.matchMedia("(max-width: 900px)").matches) {
    return;
  }

  const panel = row.querySelector(".ability-detail-panel");
  if (!panel) {
    return;
  }

  const previousDisplay = panel.style.display;
  const previousVisibility = panel.style.visibility;

  panel.style.visibility = "hidden";
  panel.style.display = "grid";
  panel.style.setProperty("--panel-left", "0px");
  panel.style.setProperty("--panel-top", "0px");
  panel.style.setProperty("--panel-width", "min(520px, calc(100vw - 32px))");
  panel.style.setProperty("--panel-max-height", "calc(100vh - 32px)");

  const gap = 12;
  const margin = 16;
  const topMargin = Math.max(document.querySelector(".site-header")?.getBoundingClientRect().bottom || 0, 0) + 12;
  const rowRect = row.getBoundingClientRect();
  const panelRect = panel.getBoundingClientRect();
  const desiredPanelWidth = Math.min(
    520,
    Math.max(280, Math.min(panelRect.width || 520, window.innerWidth - margin * 2)),
  );
  const rightSpace = window.innerWidth - margin - rowRect.right - gap;
  const leftSpace = rowRect.left - gap - margin;
  const sideSpace = Math.max(rightSpace, leftSpace);
  const panelWidth = sideSpace >= 280 ? Math.min(desiredPanelWidth, sideSpace) : desiredPanelWidth;
  const maxPanelHeight = Math.max(120, window.innerHeight - topMargin - margin);
  const contentHeight = Math.max(panel.scrollHeight || 0, panelRect.height || 0);
  const isLongPanel = contentHeight > maxPanelHeight || panel.querySelectorAll(".detail-stat").length > 6;
  const panelHeight = isLongPanel ? maxPanelHeight : Math.min(contentHeight || 420, maxPanelHeight);

  let viewportLeft;
  if (rightSpace >= panelWidth && rightSpace >= leftSpace) {
    viewportLeft = rowRect.right + gap;
  } else if (leftSpace >= panelWidth) {
    viewportLeft = rowRect.left - gap - panelWidth;
  } else {
    viewportLeft = clamp(rowRect.left, margin, window.innerWidth - panelWidth - margin);
  }

  const viewportTop = clamp(rowRect.top, topMargin, window.innerHeight - panelHeight - margin);
  const relativeLeft = viewportLeft - rowRect.left;
  const relativeTop = viewportTop - rowRect.top;

  panel.style.setProperty("--panel-left", `${Math.round(relativeLeft)}px`);
  panel.style.setProperty("--panel-top", `${Math.round(relativeTop)}px`);
  panel.style.setProperty("--panel-width", `${Math.round(panelWidth)}px`);
  panel.style.setProperty("--panel-max-height", `${Math.round(maxPanelHeight)}px`);
  panel.style.display = previousDisplay;
  panel.style.visibility = previousVisibility;
}

function hasDisplayableStat(stat) {
  if (!stat) {
    return false;
  }
  return Boolean(
    hasText(displayRaw(stat))
    || stat.value !== null
    || stat.min_value !== null
    || stat.max_value !== null
    || stat.components?.length
    || stat.warnings?.length,
  );
}

function clamp(value, min, max) {
  if (max < min) {
    return min;
  }
  return Math.min(Math.max(value, min), max);
}

function stripHtml(value) {
  return String(value).replace(/<[^>]*>/g, "");
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
        ${renderAbilityIcon(ability)}
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

function renderAbilityIcon(ability) {
  const icon = findAbilityIcon(ability);
  if (!icon?.local_path) {
    return renderMissingAbilityIcon("ability-icon");
  }
  const src = resolvePublicAssetUrl(icon.local_path);
  return `<img class="ability-icon" src="${escapeHtml(src)}" alt="${escapeHtml(ability.name)} icon" loading="lazy">`;
}

function renderAbilityVisual(ability, className) {
  const icon = findAbilityIcon(ability);
  if (icon?.local_path) {
    const src = resolvePublicAssetUrl(icon.local_path);
    return `<img class="${className}" src="${escapeHtml(src)}" alt="${escapeHtml(ability.name)} icon" loading="lazy">`;
  }
  return renderMissingAbilityIcon(className);
}

function renderMissingAbilityIcon(className) {
  return `<span class="${className} ability-icon-fallback" aria-hidden="true"><span class="missing-icon-glyph">?</span></span>`;
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
  const unit = formatUnit(component);
  if (component.min_value !== null && component.min_value !== undefined && component.max_value !== null && component.max_value !== undefined) {
    return `${formatNumber(component.min_value)}-${formatNumber(component.max_value)} ${escapeHtml(unit)}`.trim();
  }
  if (component.value !== null && component.value !== undefined && component.value !== "") {
    return `${formatNumber(component.value)} ${escapeHtml(unit)}`.trim();
  }
  const rawText = displayRaw(component);
  if (hasText(rawText)) {
    return `Raw: ${escapeHtml(rawText)}`;
  }
  return "-";
}

function formatStatValue(stat) {
  if (stat.components?.length) {
    return `<span class="complex-value">Complex value</span>`;
  }
  const unit = formatUnit(stat);
  if (stat.min_value !== null && stat.min_value !== undefined && stat.max_value !== null && stat.max_value !== undefined) {
    return `${formatNumber(stat.min_value)}-${formatNumber(stat.max_value)} ${escapeHtml(unit)}`.trim();
  }
  if (stat.value !== null && stat.value !== undefined && stat.value !== "") {
    return `${formatNumber(stat.value)} ${escapeHtml(unit)}`.trim();
  }
  const rawText = displayRaw(stat);
  if (hasText(rawText)) {
    return `<span class="not-parsed">Not safely parsed: Raw: ${escapeHtml(rawText)}</span>`;
  }
  return "-";
}

function formatUnit(item) {
  if (hasText(item?.display_unit)) {
    return item.display_unit;
  }
  if (hasText(item?.unit)) {
    return String(item.unit).replaceAll("_", " ");
  }
  return "";
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
  if (typeof value === "boolean") {
    return value ? "Yes" : "No";
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

function findAbilityIcon(ability) {
  const heroSlug = state.selectedHero?.slug || "";
  const candidates = (state.abilityIcons || []).filter((entry) => entry.hero_slug === heroSlug);
  const nameKey = iconIdentity(ability.name);
  const exact = candidates.filter((entry) => (
    iconIdentity(entry.ability_name) === nameKey
    && entry.slot !== undefined
    && entry.type !== undefined
    && iconIdentity(entry.slot) === iconIdentity(ability.slot)
    && iconIdentity(entry.type) === iconIdentity(ability.type)
  ));
  const indexed = exact.filter((entry) => entry.ability_index === ability.ability_index);
  if (indexed.length === 1) return indexed[0];
  if (exact.length === 1) return exact[0];

  const abilityKey = ability.ability_key || ability.slot;
  if (hasText(abilityKey)) {
    const keyMatches = candidates.filter((entry) => iconMatchKey(entry.ability_key) === iconMatchKey(abilityKey));
    if (keyMatches.length === 1) return keyMatches[0];
  }

  const nameMatches = candidates.filter((entry) => iconIdentity(entry.ability_name) === nameKey);
  const duplicateName = (state.selectedHero?.abilities || [])
    .filter((candidate) => iconIdentity(candidate.name) === nameKey).length > 1;
  return nameMatches.length === 1 && !duplicateName ? nameMatches[0] : null;
}

function iconIdentity(value) {
  return String(value || "").trim().toLowerCase();
}

function iconMatchKey(value) {
  return iconIdentity(value).replace(/[^a-z0-9]+/g, "");
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
