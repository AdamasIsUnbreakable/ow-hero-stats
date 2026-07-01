const DATA_ROOT = new URL("./public/data/v1/", window.location.href);
const HERO_ASSET_ROOT = new URL("./public/assets/heroes/", window.location.href);
const ABILITY_ASSET_ROOT = new URL("./public/assets/abilities/", window.location.href);
const state = {
  manifest: null,
  heroes: [],
  searchIndex: [],
  heroDetails: new Map(),
  audit: null,
  portraits: {},
  abilityIcons: [],
  selectedSlug: null,
  selectedHero: null,
  selectedHeroSource: null,
  selectedRuleset: "5v5",
  search: "",
  searchTarget: "both",
  subrole: "",
  sort: "name",
  compareMode: false,
  compareSlugs: new Set(),
  compareBuilt: false,
  showRaw: false,
  abilityDialog: null,
  abilityDialogAbility: null,
  abilityDialogSource: null,
  bodyOverflowBeforeDialog: "",
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
  searchTarget: document.querySelector("#search-target"),
  subroleFilter: document.querySelector("#subrole-filter"),
  heroSort: document.querySelector("#hero-sort"),
  compareToggle: document.querySelector("#compare-toggle"),
};

document.addEventListener("DOMContentLoaded", init);

async function init() {
  showInitialLoadingState();
  try {
    const [manifest, heroes, searchIndex, audit, portraits, abilityIcons] = await Promise.all([
      fetchJson("manifest.json"),
      fetchJson("heroes.index.json"),
      fetchJson("search.index.json").catch(() => []),
      fetchJson("audit-summary.json"),
      fetchPortraitManifest(),
      fetchAbilityIconManifest(),
    ]);
    state.manifest = manifest;
    state.heroes = heroes;
    state.searchIndex = searchIndex;
    state.audit = audit;
    state.portraits = portraits;
    state.abilityIcons = abilityIcons;
    removeStaleModeFromUrl();
    elements.selectView.setAttribute("aria-busy", "false");
    populateSubroles();

    bindEvents();

    const requestedSlug = getHeroSlugFromUrl();
    const initialHero = getHeroFromUrl();
    if (initialHero) {
      await selectHero(initialHero);
    } else if (requestedSlug) {
      showHeroSelect("Hero not found. Choose a hero below.");
    } else {
      const rebuildComparison = state.compareMode && state.compareBuilt;
      showHeroSelect();
      if (rebuildComparison) renderComparison();
    }
  } catch (error) {
    elements.selectView.setAttribute("aria-busy", "false");
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

function showInitialLoadingState() {
  const requestedSlug = getHeroSlugFromUrl();
  const title = requestedSlug ? "Loading hero" : "Loading hero data";
  const message = requestedSlug
    ? `Preparing ${titleCase(requestedSlug.replaceAll("-", " "))} and its ability data…`
    : "Preparing the hero roster and stat assets…";
  elements.selectView.hidden = false;
  elements.statsView.hidden = true;
  elements.roleSections.innerHTML = `
    <div class="empty-state loading-state" role="status">
      <span class="loading-spinner" aria-hidden="true"></span>
      <h2>${escapeHtml(title)}</h2>
      <p>${escapeHtml(message)}</p>
    </div>
  `;
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
      return [];
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
  elements.searchTarget.addEventListener("change", (event) => { state.searchTarget = event.target.value; renderHeroSelect(); });
  elements.subroleFilter.addEventListener("change", (event) => { state.subrole = event.target.value; renderHeroSelect(); });
  elements.heroSort.addEventListener("change", (event) => { state.sort = event.target.value; renderHeroSelect(); });
  elements.compareToggle.addEventListener("click", () => {
    state.compareMode = !state.compareMode;
    if (!state.compareMode) {
      state.compareSlugs.clear();
      state.compareBuilt = false;
    }
    elements.compareToggle.setAttribute("aria-pressed", String(state.compareMode));
    elements.compareToggle.textContent = state.compareMode ? "Exit compare" : "Compare heroes";
    renderHeroSelect();
  });

  elements.rawToggle.addEventListener("click", () => {
    state.showRaw = !state.showRaw;
    elements.rawToggle.setAttribute("aria-pressed", String(state.showRaw));
    elements.rawToggle.textContent = state.showRaw ? "Hide raw values" : "Show raw values";
    if (state.selectedHero) {
      renderHeroDetail(state.selectedHero);
      refreshAbilityDialog();
    }
  });

  elements.allHeroes.addEventListener("click", () => {
    state.search = "";
    elements.search.value = "";
    showHeroSelect("", { historyMode: "push" });
    elements.search.focus();
  });

  window.addEventListener("resize", positionOpenAbilityPanel);
  window.addEventListener("scroll", positionOpenAbilityPanel, true);

  window.addEventListener("popstate", () => {
    removeStaleModeFromUrl();
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
  state.selectedHeroSource = null;
  updateSelectorUrl(historyMode);

  elements.selectView.hidden = false;
  elements.statsView.hidden = true;
  elements.rawToggle.hidden = true;
  elements.allHeroes.hidden = true;
  elements.selectMessage.textContent = message;
  renderHeroSelect();
}

function renderHeroSelect() {
  const filtered = state.heroes.filter(heroMatchesSearch)
    .filter((hero) => !state.subrole || hero.sub_role === state.subrole)
    .sort((a, b) => state.sort === "subrole"
      ? String(a.sub_role || "").localeCompare(String(b.sub_role || "")) || a.name.localeCompare(b.name)
      : a.name.localeCompare(b.name));
  const grouped = groupHeroesByRole(filtered);
  const sections = ["Tank", "Damage", "Support", "Unknown"]
    .filter((role) => grouped[role]?.length)
    .map((role) => renderRoleSection(role, grouped[role]));

  elements.roleSections.innerHTML = sections.length
    ? `${sections.join("")}${state.compareMode ? renderCompareTray() : ""}`
    : `<div class="empty-state selector-empty"><h2>No matches</h2><p>Try a different hero name.</p></div>`;

  elements.roleSections.querySelectorAll("[data-hero-slug]").forEach((button) => {
    button.addEventListener("click", () => {
      const hero = state.heroes.find((item) => item.slug === button.dataset.heroSlug);
      if (hero) {
        if (state.compareMode) toggleCompareHero(hero.slug);
        else selectHero(hero, { historyMode: "push" });
      }
    });
  });
  elements.roleSections.querySelector("[data-run-compare]")?.addEventListener("click", renderComparison);
}

function populateSubroles() {
  const values = [...new Set(state.heroes.map((hero) => hero.sub_role).filter(Boolean))].sort();
  elements.subroleFilter.insertAdjacentHTML("beforeend", values.map((value) => `<option value="${escapeHtml(value)}">${escapeHtml(value)}</option>`).join(""));
}

function heroMatchesSearch(hero) {
  if (!state.search) return true;
  const heroMatch = hero.name.toLowerCase().includes(state.search);
  const entry = state.searchIndex.find((item) => item.slug === hero.slug);
  const abilityMatch = entry?.abilities?.some((ability) => [ability.name, ability.type, ...(ability.tags || [])]
    .some((value) => String(value || "").toLowerCase().includes(state.search)));
  if (state.searchTarget === "heroes") return heroMatch;
  if (state.searchTarget === "abilities") return Boolean(abilityMatch);
  return heroMatch || Boolean(abilityMatch);
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
  const matches = getHeroSearchMatches(hero);
  return `
    <button class="hero-tile ${state.compareSlugs.has(hero.slug) ? "selected" : ""}" type="button" data-hero-slug="${escapeHtml(hero.slug)}" aria-pressed="${state.compareMode ? state.compareSlugs.has(hero.slug) : "false"}">
      ${portrait}
      <span class="hero-tile-name">${escapeHtml(hero.name)}</span>
      ${matches.length ? `<span class="hero-tile-matches">Matched: ${matches.map(escapeHtml).join(", ")}</span>` : ""}
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
    const detail = await loadHeroDetail(indexHero);
    state.selectedHeroSource = detail;
    state.selectedHero = resolveHeroRuleset(detail, state.selectedRuleset);
    renderHeroDetail(state.selectedHero);
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
                ${renderGeneratedTag()}
              </div>
              <p>
                <span class="role-pill ${roleClass(hero.role)}" tabindex="0" title="${escapeHtml(rolePassiveDescription(hero.role, state.selectedRuleset))}">${escapeHtml(hero.role || "Unknown")}</span>
                ${hero.sub_role ? `<span class="ow-muted">${escapeHtml(hero.sub_role)}</span>` : ""}
              </p>
            </div>
          </header>

          <section class="ow-panel">
            <h3>Hero Stats</h3>
            ${renderHealthStats(hero)}
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

  bindAbilityRows();
  bindArmorCalculator();
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
    <article class="ow-ability-row" tabindex="0" role="button" aria-haspopup="dialog"
      data-ability-row data-ability-index="${escapeHtml(ability.ability_index)}">
      ${renderAbilityVisual(ability, "ow-ability-icon")}
      <div class="ow-ability-summary">
        <div class="ow-ability-heading">
          <h3>${escapeHtml(ability.name)}</h3>
          ${ability.slot ? `<span class="slot-badge">${escapeHtml(ability.slot)}</span>` : ""}
        </div>
        ${abilityDescription(ability) ? `<p>${renderLinkedMentions(abilityDescription(ability), ability.name)}</p>` : ""}
      </div>
      ${renderAbilityDetailPanel(ability)}
    </article>
  `;
}

function renderAbilityDetailPanel(ability) {
  const keywords = abilityKeywords(ability);
  const shotTypes = abilityShotTypes(ability);
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
      ${description ? `<p class="ability-detail-description">${renderLinkedMentions(description, ability.name)}</p>` : ""}
      ${shotTypes.length ? `<div class="ability-shot-types"><strong>Shot type</strong> ${shotTypes.map((shotType) => `<span>${escapeHtml(shotType)}</span>`).join("")}</div>` : ""}
      ${keywords.length ? `<div class="keyword-chips">${keywords.map(renderKeywordChip).join("")}</div>` : ""}
      <div class="ability-detail-stats">
        ${stats.length ? stats.filter((stat) => stat.field !== "headshot_mod").map((stat) => renderDetailStat(stat, ability)).join("") : '<p class="ow-muted">No parsed stat fields.</p>'}
      </div>
      ${ability.parse_warnings?.length ? renderWarningList(ability.parse_warnings) : ""}
    </aside>
  `;
}

function renderDetailStat(stat, ability = null) {
  const rawText = displayRaw(stat);
  const rawHtml = state.showRaw && hasText(rawText) ? `<div class="raw-value">Raw: ${escapeHtml(rawText)}</div>` : "";
  const warnings = stat.warnings?.length ? `<div class="stat-warnings">${stat.warnings.map((warning) => `Warning: ${escapeHtml(warning)}`).join("<br>")}</div>` : "";
  return `
    <section class="detail-stat">
      <div class="detail-stat-top">
        <h5>${escapeHtml(stat.label || stat.field)}</h5>
        <span class="confidence ${confidenceClass(stat.confidence)}">${escapeHtml(stat.confidence || "unparsed")}</span>
      </div>
      <div class="detail-stat-value">${stat.field === "headshot" ? formatHeadshot(stat, ability?.stats?.headshot_mod) : formatStatValue(stat)}</div>
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

function renderAbilityNotes(notes, ability = null) {
  return `
    <section class="ability-gameplay-notes">
      <h5>Gameplay notes</h5>
      <ul>${notes.map((note) => `<li>${renderLinkedMentions(note, ability?.name || "")}</li>`).join("")}</ul>
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
      row.classList.add("hovered");
      positionAbilityPanel(row);
    });
    row.addEventListener("pointerleave", () => row.classList.remove("hovered"));
    row.addEventListener("focusin", () => {
      row.classList.add("keyboard-open");
      positionAbilityPanel(row);
    });
    row.addEventListener("focusout", () => row.classList.remove("keyboard-open"));
    row.addEventListener("click", (event) => {
      event.stopPropagation();
      openAbilityDialog(abilityForRow(row), row);
    });
    row.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        openAbilityDialog(abilityForRow(row), row);
      }
    });
  });
}

function abilityForRow(row) {
  const abilityIndex = Number(row.dataset.abilityIndex);
  return state.selectedHero?.abilities?.find((ability) => ability.ability_index === abilityIndex);
}

function openAbilityDialog(ability, sourceRow) {
  if (!ability) {
    return;
  }
  if (state.abilityDialog) {
    closeAbilityDialog({ restoreFocus: false });
  }
  clearAbilityPreviewState();

  const host = document.createElement("div");
  host.innerHTML = renderAbilityDialog(ability);
  const dialog = host.firstElementChild;
  document.body.append(dialog);
  state.abilityDialog = dialog;
  state.abilityDialogAbility = ability;
  state.abilityDialogSource = sourceRow;
  state.bodyOverflowBeforeDialog = document.body.style.overflow;
  document.body.style.overflow = "hidden";

  dialog.querySelector("[data-ability-dialog-close]").addEventListener("click", closeAbilityDialog);
  dialog.addEventListener("click", (event) => {
    if (event.target === dialog) {
      closeAbilityDialog();
    }
  });
  dialog.addEventListener("cancel", (event) => {
    event.preventDefault();
    closeAbilityDialog();
  });
  dialog.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      event.preventDefault();
      closeAbilityDialog();
    }
  });
  dialog.showModal();
  bindDamageCalculator(dialog);
  dialog.querySelector("[data-ability-dialog-close]").focus();
}

function clearAbilityPreviewState() {
  elements.heroDetail.querySelectorAll("[data-ability-row].hovered, [data-ability-row].keyboard-open")
    .forEach((row) => row.classList.remove("hovered", "keyboard-open"));
}

function closeAbilityDialog(options = {}) {
  const { restoreFocus = true } = options;
  const dialog = state.abilityDialog;
  const sourceRow = state.abilityDialogSource;
  if (!dialog) {
    return;
  }

  state.abilityDialog = null;
  state.abilityDialogAbility = null;
  state.abilityDialogSource = null;
  document.body.style.overflow = state.bodyOverflowBeforeDialog;
  state.bodyOverflowBeforeDialog = "";
  if (dialog.open) {
    dialog.close();
  }
  dialog.remove();
  if (restoreFocus && sourceRow?.isConnected) {
    sourceRow.focus();
  }
}

function refreshAbilityDialog() {
  const dialog = state.abilityDialog;
  const ability = state.abilityDialogAbility;
  if (!dialog || !ability) {
    return;
  }
  dialog.querySelector(".ability-dialog-body").innerHTML = renderAbilityDialogContent(ability);
  bindDamageCalculator(dialog);
  const matchingRow = elements.heroDetail.querySelector(`[data-ability-index="${ability.ability_index}"]`);
  state.abilityDialogSource = matchingRow || state.abilityDialogSource;
}

function renderAbilityDialog(ability) {
  const titleId = `ability-dialog-title-${ability.ability_index}`;
  return `
    <dialog class="ability-dialog-backdrop" aria-labelledby="${escapeHtml(titleId)}">
      <article class="ability-dialog">
        <header class="ability-dialog-header">
          ${renderAbilityVisual(ability, "ability-dialog-icon")}
          <div>
            <h2 id="${escapeHtml(titleId)}">${escapeHtml(ability.name)}</h2>
            <p>${[ability.slot, ability.type].filter(Boolean).map(escapeHtml).join(" | ")}</p>
          </div>
          <button class="ability-dialog-close" type="button" aria-label="Close ability details" data-ability-dialog-close>&times;</button>
        </header>
        <div class="ability-dialog-body">${renderAbilityDialogContent(ability)}</div>
      </article>
    </dialog>
  `;
}

function renderAbilityDialogContent(ability) {
  const description = abilityDescription(ability);
  const shotTypes = abilityShotTypes(ability);
  const keywords = abilityKeywords(ability);
  const notes = abilityNotes(ability);
  const stats = Object.values(ability.stats || {}).filter(hasDisplayableStat);
  return `
    ${description ? `<p class="ability-detail-description">${renderLinkedMentions(description, ability.name)}</p>` : ""}
    ${shotTypes.length ? `<section class="ability-dialog-section"><h3>Shot type</h3><div class="ability-shot-types">${shotTypes.map((shotType) => `<span>${escapeHtml(shotType)}</span>`).join("")}</div></section>` : ""}
    ${keywords.length ? `<section class="ability-dialog-section"><h3>Keywords</h3><div class="keyword-chips">${keywords.map(renderKeywordChip).join("")}</div></section>` : ""}
    <section class="ability-dialog-section">
      <h3>Parsed stats</h3>
      <div class="ability-detail-stats">${stats.length ? stats.filter((stat) => stat.field !== "headshot_mod").map((stat) => renderDetailStat(stat, ability)).join("") : '<p class="ow-muted">No parsed stat fields.</p>'}</div>
    </section>
    ${renderDamageCalculatorGraph(ability)}
    ${notes.length ? renderAbilityNotes(notes, ability) : ""}
    ${ability.parse_warnings?.length ? `<section class="ability-dialog-section"><h3>Parser warnings</h3>${renderWarningList(ability.parse_warnings)}</section>` : ""}
  `;
}

function positionOpenAbilityPanel() {
  const row = elements.heroDetail.querySelector(
    "[data-ability-row].hovered, [data-ability-row].keyboard-open",
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
  const amount = Number(value);
  return Number.isFinite(amount) && amount > 0
    ? `<div><dt>${label}</dt><dd>${formatNumber(amount)}</dd></div>`
    : "";
}

function renderHealthStats(hero = {}) {
  const health = hero.health || {};
  const healthAmount = positiveHealthValue(health.health);
  const armor = positiveHealthValue(health.armor);
  const shield = positiveHealthValue(health.shield);
  const total = healthAmount + armor + shield;
  const basePool = healthAmount + shield;
  const rawTerms = healthMathTerms(healthAmount, armor, shield);
  const baseTerms = healthMathTerms(healthAmount, 0, shield);

  if (!total) {
    return '<p class="ow-muted">No health data</p>';
  }

  const normalMath = armor
    ? `${baseTerms.join(" + ")}${baseTerms.length ? " + " : ""}${formatNumber(armor)} × d / max(d − 7, d × 0.5)`
    : `${formatNumber(total)} HP (no armor mitigation)`;
  const beamMath = armor
    ? `${baseTerms.join(" + ")}${baseTerms.length ? " + " : ""}${formatNumber(armor)} / 0.7 = ${formatHealthPool(basePool + armor / 0.7)} HP`
    : `${formatNumber(total)} HP (no armor mitigation)`;
  const normalMaximum = armor
    ? `<span class="functional-health-result">Maximum: ${formatHealthPool(basePool + armor * 2)} HP when d ≤ 14</span>`
    : "";

  return `
    <dl class="ow-health-grid">
      ${renderHealthCell("Health", healthAmount)}
      ${renderHealthCell("Armor", armor)}
      ${renderHealthCell("Shield", shield)}
    </dl>
    <div class="functional-health" ${armor ? "" : "hidden"}>
      <h4>Total functional health pool</h4>
      <p class="functional-health-total">${rawTerms.join(" + ")} = <strong>${formatNumber(total)} HP</strong></p>
      <dl>
        <div>
          <dt>Normal damage</dt>
          <dd><code>${normalMath}</code>${normalMaximum}</dd>
        </div>
        <div>
          <dt>Beam damage</dt>
          <dd><code>${beamMath}</code></dd>
        </div>
      </dl>
      <details class="armor-calculator"><summary>Armor damage calculator</summary><div class="calculator-grid"><label>Attacking hero<select data-armor-attacker><option value="">Choose a hero</option>${state.heroes.map((item) => `<option value="${escapeHtml(item.slug)}">${escapeHtml(item.name)}</option>`).join("")}</select></label><label>Weapon or ability<select data-armor-ability disabled><option>Choose an attacker first</option></select></label><label>Distance (m)<input data-armor-distance type="number" min="0" value="0"></label><label data-armor-headshot-label hidden><span><input data-armor-headshot type="checkbox"> Headshot</span></label><label>Target hero<select data-armor-target><option value="${escapeHtml(hero.slug)}">${escapeHtml(hero.name)}</option>${state.heroes.filter((item) => item.slug !== hero.slug).map((item) => `<option value="${escapeHtml(item.slug)}">${escapeHtml(item.name)}</option>`).join("")}</select></label></div><div class="calculator-result" data-armor-result aria-live="polite">Select an attacker and ability.</div></details>
      ${armor ? '<p class="functional-health-note"><var>d</var> is incoming damage per hit. Armor takes max(d − 7, d × 0.5) from normal hits and d × 0.7 from beams.</p>' : ""}
    </div>
  `;
}

function bindArmorCalculator() {
  const attacker = elements.heroDetail.querySelector("[data-armor-attacker]");
  if (!attacker) return;
  const abilitySelect = elements.heroDetail.querySelector("[data-armor-ability]");
  attacker.addEventListener("change", async () => {
    const indexHero = state.heroes.find((hero) => hero.slug === attacker.value);
    if (!indexHero) return;
    const detail = resolveHeroRuleset(await loadHeroDetail(indexHero), state.selectedRuleset);
    abilitySelect.disabled = false;
    abilitySelect.innerHTML = renderArmorAbilityOptions(detail.abilities);
    abilitySelect.dataset.heroSlug = indexHero.slug;
    updateArmorHeadshotControl(detail);
    elements.heroDetail.querySelector("[data-armor-result]").textContent = "Choose a modeled or explicitly unsupported damaging ability.";
  });
  abilitySelect.addEventListener("change", async () => {
    const indexHero = state.heroes.find((hero) => hero.slug === abilitySelect.dataset.heroSlug);
    updateArmorHeadshotControl(resolveHeroRuleset(await loadHeroDetail(indexHero), state.selectedRuleset));
    updateArmorResult();
  });
  elements.heroDetail.querySelector("[data-armor-distance]").addEventListener("input", updateArmorResult);
  elements.heroDetail.querySelector("[data-armor-headshot]").addEventListener("change", updateArmorResult);
  elements.heroDetail.querySelector("[data-armor-target]").addEventListener("change", updateArmorResult);
}

function renderArmorAbilityOptions(abilities) {
  const entries = abilities.filter(hasDamageSource).map((ability) => ({ ability, model: OWDamageModel.classify(ability) }));
  entries.sort((left, right) => Number(right.model.supported) - Number(left.model.supported) || left.ability.name.localeCompare(right.ability.name));
  if (!entries.length) return '<option value="">No damaging abilities found</option>';
  return `<option value="">Choose a weapon or ability</option>${entries.map(({ ability, model }) => {
    const suffix = model.supported ? "" : ` — Unsupported: ${model.reason}`;
    return `<option value="${ability.ability_index}" data-supported="${model.supported}">${escapeHtml(ability.name + suffix)}</option>`;
  }).join("")}`;
}

function hasDamageSource(ability) {
  const damage = ability.stats?.damage;
  const raw = String(damage?.raw_display ?? damage?.raw ?? "").trim().toLowerCase();
  return Number.isFinite(damage?.value)
    || Number.isFinite(damage?.min_value)
    || Number.isFinite(damage?.max_value)
    || Boolean(damage?.components?.length)
    || (raw !== "" && raw !== "none" && raw !== "n/a");
}

function renderGeneratedTag() {
  const generatedAt = state.manifest?.generated_at;
  if (!generatedAt) return '<span class="generated-tag">Generated date unavailable</span>';
  const parsed = new Date(generatedAt);
  const label = Number.isNaN(parsed.getTime()) ? generatedAt : parsed.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
  return `<time class="generated-tag" datetime="${escapeHtml(generatedAt)}">Updated ${escapeHtml(label)}</time>`;
}

function updateArmorHeadshotControl(attacker) {
  const abilitySelect = elements.heroDetail.querySelector("[data-armor-ability]");
  const checkbox = elements.heroDetail.querySelector("[data-armor-headshot]");
  const ability = abilitySelect.value === "" ? null : attacker.abilities.find((item) => item.ability_index === Number(abilitySelect.value));
  const model = OWDamageModel.classify(ability);
  checkbox.closest("[data-armor-headshot-label]").hidden = !model.canHeadshot;
  if (!model.canHeadshot) checkbox.checked = false;
}

function getHeroSearchMatches(hero) {
  if (!state.search || state.searchTarget === "heroes") return [];
  const entry = state.searchIndex.find((item) => item.slug === hero.slug);
  return (entry?.abilities || []).filter((ability) => [ability.name, ability.type, ...(ability.tags || [])]
    .some((value) => String(value || "").toLowerCase().includes(state.search)))
    .slice(0, 3).map((ability) => ability.name);
}

function renderLinkedMentions(text, currentAbility = "") {
  const candidates = [];
  state.heroes.forEach((hero) => candidates.push({ name: hero.name, html: `<a href="?hero=${encodeURIComponent(hero.slug)}">${escapeHtml(hero.name)}</a>` }));
  const abilityNames = new Map();
  state.searchIndex.flatMap((hero) => hero.abilities || []).forEach((ability) => {
    if (!abilityNames.has(ability.name)) abilityNames.set(ability.name, []);
    abilityNames.get(ability.name).push(ability);
  });
  abilityNames.forEach((abilities, name) => {
    if (abilities.length === 1 && name !== currentAbility && abilities[0].description) candidates.push({ name, html: `<span class="ability-mention" tabindex="0" title="${escapeHtml(abilities[0].description)}">${escapeHtml(name)}</span>` });
  });
  candidates.sort((a, b) => b.name.length - a.name.length);
  const pattern = candidates.filter((item) => item.name.length >= 3).map((item) => item.name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|");
  if (!pattern) return escapeHtml(text);
  const lookup = new Map(candidates.map((item) => [item.name.toLowerCase(), item.html]));
  return String(text).split(new RegExp(`\\b(${pattern})\\b`, "gi")).map((part) => lookup.get(part.toLowerCase()) || escapeHtml(part)).join("");
}

function bindDamageCalculator(dialog) {
  const calculator = dialog.querySelector("[data-damage-calculator]");
  if (!calculator) return;
  const distance = calculator.querySelector("[data-calc-distance]");
  const headshot = calculator.querySelector("[data-calc-headshot]");
  const target = calculator.querySelector("[data-calc-target]");
  const update = async () => {
    const ability = state.abilityDialogAbility;
    const meters = Number(distance.value);
    calculator.querySelector("[data-calc-distance-output]").textContent = `${formatNumber(meters)} m`;
    const hit = OWDamageModel.evaluate({ ruleset: state.selectedRuleset, ability, distance: meters, headshot: Boolean(headshot?.checked) });
    const maxDistance = Number(calculator.dataset.maxDistance);
    const maximum = OWDamageModel.evaluate({ ruleset: state.selectedRuleset, ability, distance: 0, headshot: Boolean(headshot?.checked) }).damage;
    calculator.querySelector("[data-graph-line]").setAttribute("points", Array.from({ length: 51 }, (_, index) => {
      const sampleDistance = (maxDistance * index) / 50;
      const sample = OWDamageModel.evaluate({ ruleset: state.selectedRuleset, ability, distance: sampleDistance, headshot: Boolean(headshot?.checked) });
      return sample.supported ? `${30 + index * 12.8},${225 - (sample.damage / Math.max(maximum, 1)) * 165}` : "";
    }).filter(Boolean).join(" "));
    calculator.querySelector("[data-graph-maximum]").textContent = `${formatNumber(maximum)} max damage`;
    const markerX = 30 + (Math.min(meters, maxDistance) / maxDistance) * 640;
    calculator.querySelector("[data-graph-selected]").setAttribute("x1", markerX);
    calculator.querySelector("[data-graph-selected]").setAttribute("x2", markerX);
    if (!hit.supported) {
      calculator.querySelector("[data-calc-result]").textContent = `Unavailable at ${formatNumber(meters)} m: ${hit.reason}`;
      return;
    }
    let targetText = "";
    if (target.value) {
      const indexHero = state.heroes.find((hero) => hero.slug === target.value);
      const resolved = resolveHeroRuleset(await loadHeroDetail(indexHero), state.selectedRuleset);
      const stk = OWDamageModel.shotsToKill({ ruleset: state.selectedRuleset, ability, target: resolved.health, distance: meters, headshot: Boolean(headshot?.checked) });
      targetText = stk.supported ? ` · ${stk.shots} shots to defeat ${resolved.name}` : ` · Breakpoint unavailable: ${stk.reason}`;
    }
    calculator.querySelector("[data-calc-result]").textContent = `${formatNumber(hit.damage)} damage${hit.dps === null ? " · DPS unavailable" : ` · ${formatNumber(hit.dps)} firing DPS`}${targetText}`;
  };
  distance.addEventListener("input", update);
  headshot?.addEventListener("change", update);
  target.addEventListener("change", update);
  update();
}

function renderDamageCalculatorGraph(ability) {
  const model = OWDamageModel.classify(ability);
  if (!model.supported) return `<section class="ability-dialog-section damage-falloff-graph"><h3>Damage calculator</h3><p class="damage-falloff-note">Unavailable: ${escapeHtml(model.reason)}</p></section>`;
  const maxDistance = model.hasFalloff ? Math.ceil(model.end + 10) : 50;
  const points = Array.from({ length: 51 }, (_, index) => {
    const distance = (maxDistance * index) / 50;
    const hit = OWDamageModel.evaluate({ ruleset: state.selectedRuleset, ability, distance });
    const x = 30 + index * 12.8;
    const y = hit.supported ? 225 - (hit.damage / Math.max(model.maximum, 1)) * 165 : null;
    return y === null ? "" : `${x},${y}`;
  }).filter(Boolean).join(" ");
  return `<section class="ability-dialog-section damage-falloff-graph" data-damage-calculator data-ability-index="${ability.ability_index}" data-max-distance="${maxDistance}"><h3>Damage, DPS, and breakpoints</h3><svg viewBox="0 0 700 280" role="img" aria-label="Programmatic damage by distance"><line class="graph-axis" x1="30" y1="225" x2="670" y2="225"></line><polyline class="graph-damage-line" data-graph-line points="${points}"></polyline><line class="graph-selected-marker" data-graph-selected x1="30" y1="45" x2="30" y2="225"></line><text class="graph-value" data-graph-maximum x="38" y="48">${formatNumber(model.maximum)} max damage</text><text class="graph-label" x="670" y="258" text-anchor="end">${maxDistance} m</text></svg>${model.partialFalloff ? '<p class="damage-falloff-note">Partial graph: falloff start/end are known, but reduced damage was not safely parsed. The curve stops where reliable calculation ends.</p>' : ""}<div class="calculator-grid"><label>Distance <input type="range" min="0" max="${maxDistance}" step="0.5" value="0" data-calc-distance><output data-calc-distance-output>0 m</output></label>${model.canHeadshot ? '<label><input type="checkbox" data-calc-headshot> Headshot</label>' : ""}<label>Target hero<select data-calc-target><option value="">No target</option>${state.heroes.map((hero) => `<option value="${escapeHtml(hero.slug)}">${escapeHtml(hero.name)}</option>`).join("")}</select></label></div><div class="calculator-result" data-calc-result aria-live="polite"></div></section>`;
}

async function updateArmorResult() {
  const abilitySelect = elements.heroDetail.querySelector("[data-armor-ability]");
  const result = elements.heroDetail.querySelector("[data-armor-result]");
  if (!abilitySelect?.dataset.heroSlug || !result) return;
  if (abilitySelect.value === "") {
    result.textContent = "Choose a weapon or ability.";
    return;
  }
  const attackerIndex = state.heroes.find((hero) => hero.slug === abilitySelect.dataset.heroSlug);
  const targetIndex = state.heroes.find((hero) => hero.slug === elements.heroDetail.querySelector("[data-armor-target]").value);
  const [attacker, target] = await Promise.all([loadHeroDetail(attackerIndex), loadHeroDetail(targetIndex)]);
  const resolvedAttacker = resolveHeroRuleset(attacker, state.selectedRuleset);
  const resolvedTarget = resolveHeroRuleset(target, state.selectedRuleset);
  const ability = resolvedAttacker.abilities.find((item) => item.ability_index === Number(abilitySelect.value));
  const distance = Number(elements.heroDetail.querySelector("[data-armor-distance]").value);
  const headshot = elements.heroDetail.querySelector("[data-armor-headshot]").checked;
  const hit = OWDamageModel.evaluate({ ruleset: state.selectedRuleset, ability, distance, headshot });
  if (!hit.supported) { result.textContent = `Unavailable: ${hit.reason}`; return; }
  const armorDamage = OWDamageModel.damageToArmor(hit.damage, hit.damageType);
  if (armorDamage === null) { result.textContent = "Unavailable: this damage type does not have a verified armor rule."; return; }
  const stk = OWDamageModel.shotsToKill({ ruleset: state.selectedRuleset, ability, target: resolvedTarget.health, distance, headshot });
  const targetArmorNote = positiveHealthValue(resolvedTarget.health?.armor) ? "" : `<br><span class="ow-muted">${escapeHtml(resolvedTarget.name)} has no armor in this mode; the armor figure is the per-hit rule preview.</span>`;
  result.innerHTML = `<strong>${formatNumber(hit.damage)} raw damage → ${formatNumber(armorDamage)} damage to armor</strong><br>${stk.supported ? `${stk.shots} shots to defeat ${escapeHtml(resolvedTarget.name)}` : `Shots to kill unavailable: ${escapeHtml(stk.reason)}`}<br><span class="ow-muted">${headshot ? "Headshot; " : ""}${escapeHtml(hit.damageType)} armor rule, ${escapeHtml(state.selectedRuleset)} stats</span>${targetArmorNote}`;
}

function positiveHealthValue(value) {
  const amount = Number(value);
  return Number.isFinite(amount) && amount > 0 ? amount : 0;
}

function healthMathTerms(health, armor, shield) {
  return [
    health > 0 ? `${formatNumber(health)} Health` : "",
    armor > 0 ? `${formatNumber(armor)} Armor` : "",
    shield > 0 ? `${formatNumber(shield)} Shield` : "",
  ].filter(Boolean);
}

function formatHealthPool(value) {
  return Number.isInteger(value) ? String(value) : value.toFixed(1);
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

function toggleCompareHero(slug) {
  if (state.compareSlugs.has(slug)) state.compareSlugs.delete(slug);
  else state.compareSlugs.add(slug);
  state.compareBuilt = false;
  renderHeroSelect();
}

function renderCompareTray() {
  return `<section class="compare-tray"><h2>Compare (${state.compareSlugs.size})</h2><p>Select at least two heroes. Values use ${escapeHtml(state.selectedRuleset)} resolved data. Only narrow, high-confidence fields are included; missing costs and complex damage stay unavailable.</p><button type="button" data-run-compare ${state.compareSlugs.size < 2 ? "disabled" : ""}>Build comparison</button><div class="compare-results" data-compare-results aria-live="polite"></div></section>`;
}

async function loadHeroDetail(indexHero) {
  if (state.heroDetails.has(indexHero.slug)) return state.heroDetails.get(indexHero.slug);
  const detail = await fetchJson(indexHero.detail_path);
  detail.abilities = (detail.abilities || []).map((ability, abilityIndex) => ({ ...ability, ability_index: ability.ability_index ?? abilityIndex }));
  state.heroDetails.set(indexHero.slug, detail);
  return detail;
}

async function renderComparison() {
  const host = elements.roleSections.querySelector("[data-compare-results]");
  host.innerHTML = '<p class="ow-muted">Loading comparison...</p>';
  const selected = [...state.compareSlugs].map((slug) => state.heroes.find((hero) => hero.slug === slug)).filter(Boolean);
  const details = await Promise.all(selected.map(async (hero) => resolveHeroRuleset(await loadHeroDetail(hero), state.selectedRuleset)));
  const rows = details.map((hero) => {
    const weapons = hero.abilities.filter((ability) => abilityGroup(ability) === "weapons");
    const primary = [...weapons].sort((a, b) => primaryWeaponRank(a) - primaryWeaponRank(b)).find((ability) => OWDamageModel.classify(ability).supported);
    const model = primary ? OWDamageModel.classify(primary) : null;
    const cooldowns = hero.abilities.filter((ability) => ability.stats?.cooldown?.confidence === "high" && Number.isFinite(Number(ability.stats.cooldown.value)) && Number(ability.stats.cooldown.value) > 0).map((ability) => `${ability.name}: ${formatNumber(Number(ability.stats.cooldown.value))}s`);
    const ultimate = hero.abilities.find((ability) => abilityGroup(ability) === "ultimate");
    const ult = ultimate?.stats?.ult_cost || ultimate?.stats?.ultimate_cost;
    const perkCosts = hero.abilities.filter((ability) => abilityGroup(ability) === "perks" && ability.stats?.perk_cost?.confidence === "high" && Number.isFinite(Number(ability.stats.perk_cost.value))).map((ability) => `${ability.name}: ${formatNumber(Number(ability.stats.perk_cost.value))}`);
    const primaryUnavailable = weapons.length ? OWDamageModel.classify(weapons.sort((a, b) => primaryWeaponRank(a) - primaryWeaponRank(b))[0]).reason : "No weapon data";
    const highConfidence = primary ? comparePrimaryStats(primary) : [];
    return `<tr><th>${escapeHtml(hero.name)}</th><td>${escapeHtml([hero.role, hero.sub_role].filter(Boolean).join(" / "))}</td><td>${escapeHtml(formatHealth(hero.health))}</td><td>${primary ? `${escapeHtml(primary.name)}: ${formatNumber(model.maximum)} damage` : `Unavailable: ${escapeHtml(primaryUnavailable)}`}</td><td>${model ? (model.hasFalloff ? `${formatNumber(model.start)}-${formatNumber(model.end)} m` : "No falloff") : "Unavailable"}</td><td>${cooldowns.length ? cooldowns.map(escapeHtml).join("<br>") : "Unavailable"}</td><td>${Number.isFinite(Number(ult?.value)) && ult.confidence === "high" ? formatNumber(Number(ult.value)) : "Unavailable in generated data"}</td><td>${perkCosts.length ? perkCosts.map(escapeHtml).join("<br>") : "Unavailable in generated data"}</td><td>${highConfidence.length ? highConfidence.map(escapeHtml).join("<br>") : "Unavailable"}</td></tr>`;
  });
  state.compareBuilt = true;
  host.innerHTML = `<div class="compare-table-wrap"><table><caption>${escapeHtml(state.selectedRuleset)} resolved comparison</caption><thead><tr><th>Hero</th><th>Role</th><th>Health pools</th><th>Primary damage</th><th>Falloff</th><th>Cooldowns</th><th>Ult cost</th><th>Perk costs</th><th>High-confidence weapon stats</th></tr></thead><tbody>${rows.join("")}</tbody></table></div>`;
}

function primaryWeaponRank(ability) {
  const slot = String(ability.slot || "").toLowerCase();
  const type = String(ability.type || "").toLowerCase();
  if (slot.includes("primary") || type.includes("primary")) return 0;
  if (slot.includes("secondary") || type.includes("secondary")) return 2;
  return 1;
}

function comparePrimaryStats(ability) {
  const wanted = ["ammo", "reload_time", "fire_rate", "dps"];
  return wanted.map((field) => ability.stats?.[field]).filter((stat) => stat?.confidence === "high" && hasDisplayableStat(stat))
    .map((stat) => `${stat.label}: ${stripHtml(formatStatValue(stat))}`);
}

function resolveHeroRuleset(detail, ruleset) {
  const base = detail.base || {
    role: detail.role,
    sub_role: detail.sub_role,
    health: detail.health,
    abilities: detail.abilities || [],
  };
  const patch = detail.ruleset_overrides?.[ruleset] || {};
  const resolved = deepMergeRuleset(structuredClone(base), patch);
  return { ...detail, ...resolved, selected_ruleset: ruleset };
}

function deepMergeRuleset(target, patch) {
  for (const [key, value] of Object.entries(patch || {})) {
    if (key === "abilities" && Array.isArray(value)) {
      for (const abilityPatch of value) {
        const ability = findAbilityForPatch(target.abilities || [], abilityPatch);
        if (ability) deepMergeRuleset(ability, abilityPatch);
      }
    } else if (value && typeof value === "object" && !Array.isArray(value)) {
      target[key] = deepMergeRuleset(target[key] || {}, value);
    } else {
      target[key] = value;
    }
  }
  return target;
}

function findAbilityForPatch(abilities, abilityPatch) {
  if (Number.isFinite(abilityPatch.ability_index)) {
    return abilities.find((ability) => ability.ability_index === abilityPatch.ability_index) || null;
  }

  let candidates = abilities.filter((ability) => ability.name === abilityPatch.name);
  if (hasText(abilityPatch.slot)) {
    candidates = candidates.filter((ability) => ability.slot === abilityPatch.slot);
  }
  if (hasText(abilityPatch.type)) {
    candidates = candidates.filter((ability) => ability.type === abilityPatch.type);
  }
  return candidates.length === 1 ? candidates[0] : null;
}

function formatHeadshot(stat, multiplier) {
  if (stat.value === true) {
    const suffix = Number.isFinite(multiplier?.value) ? ` (${formatNumber(multiplier.value)}x)` : "";
    return `&#10003; Headshot${suffix}`;
  }
  if (stat.value === false) return "&#10005; Headshot";
  return formatStatValue(stat);
}

// Patch-sensitive reference copy. Add a ruleset-specific entry when a role passive
// is confirmed to differ; otherwise non-default modes are explicitly described as shared.
const ROLE_PASSIVES = {
  Tank: "Tank role passive: reduced knockback and reduced ultimate charge generated by damage and healing received.",
  Damage: "Damage role passive: damaging an enemy temporarily reduces healing they receive.",
  Support: "Support role passive: health regeneration begins sooner after avoiding damage.",
};

function rolePassiveDescription(role, ruleset) {
  const description = ROLE_PASSIVES[role];
  if (!description) return "Role passive details are unavailable.";
  if (ruleset !== state.manifest?.rulesets?.default) {
    return `${description} Shared reference only; no confirmed ${ruleset}-specific passive description is available.`;
  }
  return description;
}

// Patch-sensitive glossary copy. Prefer generated/source-owned definitions when
// the export contract gains them; unknown keywords deliberately keep a neutral label.
const KEYWORD_DESCRIPTIONS = {
  armor: "A health type that reduces incoming damage.",
  barrier: "A deployable or projected obstacle that blocks eligible damage and effects.",
  overhealth: "Temporary health that cannot be healed and usually decays or expires.",
  stun: "Prevents the affected target from acting for a duration.",
  transformation: "Temporarily changes the hero or ability state.",
  "area of effect": "Affects targets within an area rather than only one direct target.",
};

function renderKeywordChip(keyword) {
  const description = KEYWORD_DESCRIPTIONS[String(keyword).toLowerCase()] || `Ability keyword: ${keyword}`;
  return `<span tabindex="0" title="${escapeHtml(description)}">${escapeHtml(keyword)}</span>`;
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

function removeStaleModeFromUrl() {
  const url = new URL(window.location.href);
  if (!url.searchParams.has("mode")) return;
  url.searchParams.delete("mode");
  window.history.replaceState(window.history.state, "", url.href);
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
  url.searchParams.delete("mode");
  url.searchParams.set("hero", slug);
  return url.href;
}

function updateSelectorUrl(historyMode) {
  if (historyMode === "none") {
    return;
  }

  const url = new URL(window.location.href);
  url.searchParams.delete("mode");
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
