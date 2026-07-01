# OW Hero Stats

Python tools for exporting and auditing Overwatch hero metadata and ability stats from the Overwatch Fandom Wiki Cargo API.

The project keeps raw wiki values next to conservative parsed values. This is intentional: Overwatch stats often contain ranges, falloff, direct/splash components, charge scaling, tooltips, and wiki markup. The exporter should not silently pretend those are simpler than they are.

## Setup

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
```

For development tools:

```powershell
.\.venv\Scripts\python.exe -m pip install -e .[dev]
```

## Commands

Export one hero and write `data\output\ashe.json`:

```powershell
.\.venv\Scripts\python.exe -m overwatch_stats.cli hero Ashe
```

Print raw Cargo rows for debugging:

```powershell
.\.venv\Scripts\python.exe -m overwatch_stats.cli raw Ashe
```

Bypass cache and refetch one hero:

```powershell
.\.venv\Scripts\python.exe -m overwatch_stats.cli refresh Ashe
```

Export all Fandom hero pages:

```powershell
.\.venv\Scripts\python.exe -m overwatch_stats.cli all
```

Audit one hero without exporting JSON:

```powershell
.\.venv\Scripts\python.exe -m overwatch_stats.cli audit Ashe
```

Print the same hero audit as stable JSON for automation or a future UI:

```powershell
.\.venv\Scripts\python.exe -m overwatch_stats.cli audit Ashe --json
```

Audit all heroes and compare Fandom source sets:

```powershell
.\.venv\Scripts\python.exe -m overwatch_stats.cli audit all
```

Print the all-heroes audit as stable JSON:

```powershell
.\.venv\Scripts\python.exe -m overwatch_stats.cli audit all --json
```

Generate static website-ready data:

```powershell
.\.venv\Scripts\python.exe -m overwatch_stats.cli web-data
.\.venv\Scripts\python.exe -m overwatch_stats.cli web-data --refresh
```

Download hero portraits for the static viewer:

```powershell
.\.venv\Scripts\python.exe -m overwatch_stats.cli images
.\.venv\Scripts\python.exe -m overwatch_stats.cli images --refresh
```

Download matched ability icons for the static viewer:

```powershell
.\.venv\Scripts\python.exe -m overwatch_stats.cli ability-icons
.\.venv\Scripts\python.exe -m overwatch_stats.cli ability-icons --refresh
```

## Output Model

Each normalized hero export includes:

- `raw`: the original Cargo row values for each ability.
- `parsed`: field-specific parser output for stats such as damage, cooldown, ammo, reload time, falloff range, fire rate, duration, projectile speed, radius, spread, DPS, and HPS.
- `parse_warnings`: warnings that explain uncertain, partial, or skipped parsing.
- `fetched_at`: the time the normalized export was produced.
- `source`: the Overwatch Fandom API endpoint.

Each parsed stat has:

- `raw`: the original string.
- `raw_display`: a cleaned display string with wiki markup and tooltip HTML removed. Keep using `raw` when exact source text matters.
- `value`: a single value only when the parser can represent the stat safely.
- `min_value` / `max_value`: range values when a range can be represented safely.
- `unit`: machine-readable normalized unit label such as `seconds`, `shots_per_second`, or `meters_per_second`.
- `display_unit`: UI-readable unit label such as `s`, `shots/s`, or `m/s`.
- `confidence`: one of `high`, `medium`, `low`, or `unparsed`.
- `warnings`: parser-specific warnings.
- `components`: structured sub-values for narrow complex cases, such as `direct` and `splash` damage. The parent stat still keeps `value` empty when there is no safe single value.

Confidence levels:

- `high`: simple value or range with a clear unit/context.
- `medium`: likely useful, but missing an explicit unit or represented with reduced certainty.
- `low`: parsed shape is risky or partial; check `raw` and warnings before using.
- `unparsed`: raw value is blank, unsupported, or too ambiguous to parse.

Complex damage strings keep the raw value and emit explicit warnings instead of pretending the first number is the full damage model. Complex stats may expose `components` while the parent `value` remains empty, so the website can show an intentional breakdown without reducing the stat to one misleading number.

## Cache And Generated Output

Raw API responses are cached in `data\cache` so repeated commands do not hammer the wiki. JSON exports are written to `data\output`.

Both directories are ignored by Git because they are generated locally. Regenerate output with:

```powershell
.\.venv\Scripts\python.exe -m overwatch_stats.cli all
```

Overwatch Fandom is community-maintained. Refresh cached data after patches or wiki updates:

```powershell
.\.venv\Scripts\python.exe -m overwatch_stats.cli --refresh all
```

## Static Website Data

The `web-data` command creates a stable, versioned JSON contract for a future website. It does not build a frontend. Generated files are written under:

```text
site\public\data\v1\
  manifest.json
  heroes.index.json
  audit-summary.json
  quality-report.json
  heroes\
    ashe.json
    ana.json
    ...
```

`manifest.json` includes the schema version, generation timestamp, source API endpoint, hero count, and paths to the other files.

Current website schema version: `3.0.0`. Hero detail files contain a corrected `base`, an empty `ruleset_overrides` object reserved for schema compatibility, and `overrides_applied` provenance. The legacy top-level resolved base fields remain present for simple consumers. The schema retains UI-readable `display_unit` fields, cleaned `raw_display` fields, stat `components`, and original `raw` values.

Schema 3 adds `search.index.json`, a lightweight hero/ability/perk/tag index used by roster search without fetching every hero detail. The standalone `site/src/damage-model.js` calculation model consumes already-resolved ruleset data and is shared by armor, damage/DPS-at-distance, falloff, headshot, breakpoint, and compare features. It intentionally refuses component, pellet, splash, damage-over-time, charge-scaled, and deployable damage.

### Corrections

Programmatic corrections live in `overwatch_stats\overrides.py` and run only while website data is generated. Add a narrowly sourced entry to `HERO_OVERRIDES` with its ruleset, path, replacement value, reason, and source. Corrections never mutate Cargo `raw` rows or the caller's source-derived object; every applied item is copied to `overrides_applied`. The generated `base` is a copy of source data with confirmed corrections for the active ruleset applied.

Ability override selectors must resolve to exactly one existing source ability. Prefer `ability_index`; a name selector may include `slot` and `type` to disambiguate. Generation raises an error for missing or ambiguous selectors, so overrides cannot create abilities and typos cannot become silent frontend no-ops. The viewer resolves the selected mode before rendering.

Ability-level corrections should prefer the stable `ability_index`; `name` with `slot` and `type` is the readable fallback when an index is unavailable:

```python
{
    "ruleset": "5v5",
    "path": ["abilities", {"ability_index": 0}, "stats", "damage", "value"],
    "value": 45,
    "reason": "Confirmed correction",
    "source": "Source reference",
}
```

`heroes.index.json` is lightweight for hero selector/search views. It includes hero identity, role, health, ability count, warning count, confidence counts, and each hero detail path. It does not include full raw ability rows.

Each `heroes\{slug}.json` detail file includes raw and parsed stats for that hero, so a future website can support raw/parsed toggles and warning-aware displays.

Stat objects in hero detail files include both `field` and `label`. `field` is the stable machine-readable stat key, such as `pspeed`; `label` is the human-readable display label, such as `Projectile Speed`. They also include both `unit` and `display_unit`; use `unit` for code and `display_unit` for UI text.

`audit-summary.json` mirrors the `audit all --json` summary shape with totals, confidence counts, source validation, zero-ability heroes, and common parse warnings.

`quality-report.json` summarizes website data coverage, warning counts, empty/not-applicable stat fields, meaningful unparsed fields, field-level warning counts, component stat coverage, machine/display unit usage, and stats missing display units. Its `icons` section audits raw Cargo icon fields for missing, blank, fallback-text, and invalid values. Its `perks` section reports heroes that differ from the expected two current Minor and two current Major perks. Cargo rows explicitly marked `removed` are excluded before current perk counts are calculated; unresolved source anomalies remain visible in the report.

Generated site data should be regenerated after Overwatch patches or wiki updates:

```powershell
.\.venv\Scripts\python.exe -m overwatch_stats.cli web-data --refresh
```

## Static Viewer

The repository includes a minimal plain HTML/CSS/JavaScript viewer that reads the generated JSON data contract. It has no React, Vite, TypeScript, Tailwind, or build step.

The default page is a full-page hero select screen. Heroes are grouped by Tank, Damage, and Support, with portrait tiles when downloaded and clean fallback tiles when portraits are missing.

Generate data and optional images, serve the `site` folder, then open the local URL:

```powershell
.\.venv\Scripts\python.exe -m overwatch_stats.cli web-data
.\.venv\Scripts\python.exe -m overwatch_stats.cli images
.\.venv\Scripts\python.exe -m overwatch_stats.cli ability-icons
cd site
python -m http.server 8000
```

Open:

```text
http://localhost:8000
```

The browser loads data from `site\public\data\v1`. Select a hero to open a dark hero info/stat page with grouped weapons, abilities, passives, ultimates, and perks. Ability rows show detailed stat panels on hover or keyboard focus; mobile users can tap rows to expand details inline. Use the raw value toggle to inspect original wiki strings alongside parsed values, confidence, parser warnings, and stat components.

Hero portraits are downloaded from the Overwatch Fandom `Category:Overwatch 2 hero icons` MediaWiki category into `site\public\assets\heroes`, with a generated `manifest.json` beside the images. The viewer loads that manifest when it exists and falls back to the text-only layout if portraits have not been generated. Downloaded portraits are generated assets and are ignored by Git.

Ability icons are downloaded with the Fandom MediaWiki API into `site\public\assets\abilities`. The command writes both `manifest.json` and `coverage-report.json`: the manifest records hero/ability identity, `ability_index`, slot, type, source metadata, and local path; the coverage report compares final generated assets with every displayed ability, passive, and perk. Matching uses index, slot, type, and name to avoid unsafe duplicate-name guesses. Old manifests without `ability_index` remain supported when their name or key is unambiguous. The downloader first uses Cargo's exact `ability_image` filename, then falls back to matching `Category:Ability icons` and hero-specific icon categories. Generated assets are ignored by Git. Missing icons use a visibly incomplete UI placeholder and never count as real asset coverage. MediaWiki category and image metadata is cached under `data\cache\images`; ordinary reruns reuse both metadata and existing files. `--refresh` deliberately bypasses the cache. Rate-limited requests use bounded retries and honor Fandom's `Retry-After` response when provided.

Selecting a hero updates the browser URL, so links such as `http://localhost:8000/?hero=ashe` still open that hero directly. Use the selected hero's Copy link button to copy a refresh-safe URL, or use All heroes to return to the selector.

You can also double-click `open-website.cmd` from the repo root. It uses existing generated data when available, starts a local server, and opens the website in your browser. Keep the launcher window open while using the site.

## Deployment

Local development still uses:

```powershell
.\.venv\Scripts\python.exe -m overwatch_stats.cli web-data
```

GitHub Pages deployment generates fresh website data in CI, runs tests and Ruff, then publishes the `site` folder. The published site reads the generated `site\public\data\v1` files from the Pages artifact.

The deployment workflow also downloads hero portraits and matched ability icons during CI, so the published artifact includes `site\public\assets\heroes` and `site\public\assets\abilities` without committing downloaded images to the repository.

If Pages is not enabled yet, enable it in the GitHub repository settings and choose GitHub Actions as the Pages source. The workflow uploads and deploys the Pages artifact directly; it does not require a separate branch-based Pages source.

## Tests

Normal tests do not require live network access. Representative Cargo payloads live under `tests\fixtures`, including `tests\fixtures\ashe_cargo_sample.json`, so parser and normalizer behavior can be checked against realistic Cargo-style strings without calling the Fandom API.

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
```

## CI

GitHub Actions runs on `push` and `pull_request`. The workflow installs Python 3.11, installs the package with development dependencies, runs the unit tests, and runs Ruff:

```powershell
.\.venv\Scripts\python.exe -m pip install -e .[dev]
.\.venv\Scripts\python.exe -m unittest discover -s tests
.\.venv\Scripts\python.exe -m ruff check .
```
