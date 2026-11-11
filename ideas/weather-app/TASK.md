# Task: weather app v0

## Goal
A polished, working weather web app that runs as a static site on GitHub Pages at
https://yagizdas.github.io/projects_main/ideas/weather-app/

## Details
- Pure static site inside `ideas/weather-app/` (index.html + CSS + JS). No build step, no server, no API keys: it must work when served straight from the repo by GitHub Pages ("deploy from branch").
- Use Open-Meteo (forecast + geocoding APIs, free, no key) for data.
- Features:
  - City search with autocomplete; "use my location" button (browser geolocation).
  - Default to Munich on first load; remember the last city in localStorage (wrap in try/catch).
  - Current conditions: temperature, feels-like, condition with icon, wind, humidity, precipitation.
  - Hourly forecast for the next 24h (horizontally scrollable) and a 7-day forecast with min/max.
  - °C default with a °C/°F toggle.
- Design: make it genuinely nice. Clean, modern, distinctive; background/accent adapts to condition and day/night; smooth but light animations; responsive and great on a phone.
- Loading and error states (no results, offline, location denied).
- Use relative paths only so it works under the `/projects_main/ideas/weather-app/` subpath.

## Done when
- Opening `index.html` via a local static server (e.g. `python3 -m http.server`) shows Munich weather, search works, and the unit toggle works.
- No console errors; layout works at 375px and desktop widths.
- `ideas/weather-app/README.md` explains what it is, how to run locally, and the Pages URL.

## Notes
- Do NOT add GitHub Actions workflows or touch anything outside `ideas/weather-app/`.
- Delete this TASK.md in your final commit.
