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

## Output Model

Each normalized hero export includes:

- `raw`: the original Cargo row values for each ability.
- `parsed`: field-specific parser output for stats such as damage, cooldown, ammo, reload time, falloff range, fire rate, duration, projectile speed, radius, spread, DPS, and HPS.
- `parse_warnings`: warnings that explain uncertain, partial, or skipped parsing.
- `fetched_at`: the time the normalized export was produced.
- `source`: the Overwatch Fandom API endpoint.

Each parsed stat has:

- `raw`: the original string.
- `value`: a single value only when the parser can represent the stat safely.
- `min_value` / `max_value`: range values when a range can be represented safely.
- `unit`: normalized unit label such as `seconds`, `damage`, or `meters`.
- `confidence`: one of `high`, `medium`, `low`, or `unparsed`.
- `warnings`: parser-specific warnings.

Confidence levels:

- `high`: simple value or range with a clear unit/context.
- `medium`: likely useful, but missing an explicit unit or represented with reduced certainty.
- `low`: parsed shape is risky or partial; check `raw` and warnings before using.
- `unparsed`: raw value is blank, unsupported, or too ambiguous to parse.

Complex damage strings such as direct plus splash damage keep the raw value and emit explicit warnings instead of pretending the first number is the full damage model.

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
  heroes\
    ashe.json
    ana.json
    ...
```

`manifest.json` includes the schema version, generation timestamp, source API endpoint, hero count, and paths to the other files.

`heroes.index.json` is lightweight for hero selector/search views. It includes hero identity, role, health, ability count, warning count, confidence counts, and each hero detail path. It does not include full raw ability rows.

Each `heroes\{slug}.json` detail file includes raw and parsed stats for that hero, so a future website can support raw/parsed toggles and warning-aware displays.

Stat objects in hero detail files include both `field` and `label`. `field` is the stable machine-readable stat key, such as `pspeed`; `label` is the human-readable display label, such as `Projectile Speed`.

`audit-summary.json` mirrors the `audit all --json` summary shape with totals, confidence counts, source validation, zero-ability heroes, and common parse warnings.

Generated site data should be regenerated after Overwatch patches or wiki updates:

```powershell
.\.venv\Scripts\python.exe -m overwatch_stats.cli web-data --refresh
```

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
