# OW Hero Stats

Small Python tool for exporting Overwatch hero metadata and ability stats from the Overwatch Fandom Wiki Cargo API.

## Setup

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install requests
```

## Usage

```powershell
.\.venv\Scripts\python.exe -m overwatch_stats.cli hero Ashe
.\.venv\Scripts\python.exe -m overwatch_stats.cli raw Ashe
.\.venv\Scripts\python.exe -m overwatch_stats.cli refresh Ashe
.\.venv\Scripts\python.exe -m overwatch_stats.cli all
```

The tool caches raw API responses in `data\cache` and writes normalized exports to `data\output`.

## Tests

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
```
