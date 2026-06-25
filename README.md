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

Audit all heroes and compare Fandom source sets:

```powershell
.\.venv\Scripts\python.exe -m overwatch_stats.cli audit all
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

## Tests

Normal tests do not require live network access. Representative Cargo payloads live under `tests\fixtures`.

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
```
