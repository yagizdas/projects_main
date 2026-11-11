const $ = (selector) => document.querySelector(selector);
const state = { unit: 'c', place: null, weather: null, searchTimer: null };
const MUNICH = { name: 'Munich', country: 'Germany', latitude: 48.1374, longitude: 11.5755 };

const codes = {
  0: ['Clear sky', '☀️', 'clear'], 1: ['Mainly clear', '🌤️', 'clear'], 2: ['Partly cloudy', '⛅', 'cloud'], 3: ['Overcast', '☁️', 'cloud'],
  45: ['Foggy', '🌫️', 'cloud'], 48: ['Rime fog', '🌫️', 'cloud'], 51: ['Light drizzle', '🌦️', 'rain'], 53: ['Drizzle', '🌦️', 'rain'],
  55: ['Heavy drizzle', '🌧️', 'rain'], 56: ['Freezing drizzle', '🌧️', 'rain'], 57: ['Freezing drizzle', '🌧️', 'rain'], 61: ['Light rain', '🌦️', 'rain'],
  63: ['Rain', '🌧️', 'rain'], 65: ['Heavy rain', '🌧️', 'rain'], 66: ['Freezing rain', '🌧️', 'rain'], 67: ['Freezing rain', '🌧️', 'rain'],
  71: ['Light snow', '🌨️', 'snow'], 73: ['Snow', '❄️', 'snow'], 75: ['Heavy snow', '❄️', 'snow'], 77: ['Snow grains', '❄️', 'snow'],
  80: ['Rain showers', '🌦️', 'rain'], 81: ['Rain showers', '🌧️', 'rain'], 82: ['Heavy showers', '⛈️', 'rain'], 85: ['Snow showers', '🌨️', 'snow'],
  86: ['Heavy snow showers', '🌨️', 'snow'], 95: ['Thunderstorm', '⛈️', 'rain'], 96: ['Storm with hail', '⛈️', 'rain'], 99: ['Storm with hail', '⛈️', 'rain']
};
const describe = (code, day = true) => { const item = codes[code] || ['Weather', '🌤️', 'clear']; return [item[0], !day && code < 3 ? '🌙' : item[1], item[2]]; };
const cToF = (c) => c * 9 / 5 + 32;
const temp = (value) => `${Math.round(state.unit === 'f' ? cToF(value) : value)}°`;
const safeStore = {
  get() { try { return JSON.parse(localStorage.getItem('atmos-place')); } catch { return null; } },
  set(value) { try { localStorage.setItem('atmos-place', JSON.stringify(value)); } catch { /* Storage may be disabled. */ } }
};

async function request(url) {
  if (!navigator.onLine) throw new Error('You appear to be offline. Reconnect and try again.');
  const response = await fetch(url);
  if (!response.ok) throw new Error('The weather service is unavailable right now.');
  return response.json();
}

async function loadWeather(place, save = true) {
  state.place = place; showLoading();
  const params = new URLSearchParams({ latitude: place.latitude, longitude: place.longitude, timezone: 'auto', forecast_days: '8',
    current: 'temperature_2m,relative_humidity_2m,apparent_temperature,is_day,precipitation,weather_code,wind_speed_10m',
    hourly: 'temperature_2m,weather_code,is_day,precipitation_probability', daily: 'weather_code,temperature_2m_max,temperature_2m_min' });
  try {
    state.weather = await request(`https://api.open-meteo.com/v1/forecast?${params}`);
    if (save) safeStore.set(place);
    render();
  } catch (error) { showError(error.message); }
}

function showLoading() { $('#status').hidden = false; $('#error').hidden = true; $('#weather').hidden = true; }
function showError(message) { $('#status').hidden = true; $('#weather').hidden = true; $('#error-message').textContent = message; $('#error').hidden = false; }
function render() {
  const { current, hourly, daily, timezone_abbreviation: zone } = state.weather;
  const [label, icon, theme] = describe(current.weather_code, current.is_day);
  document.body.dataset.weather = theme; document.body.dataset.night = String(!current.is_day);
  $('meta[name="theme-color"]').content = getComputedStyle(document.body).getPropertyValue('--sky-1');
  $('#place').textContent = [state.place.name, state.place.country_code || state.place.country].filter(Boolean).join(', ');
  $('#local-time').textContent = `${new Date(current.time).toLocaleString([], { weekday: 'long', hour: 'numeric', minute: '2-digit' })} · ${zone}`;
  $('#condition').textContent = label; $('#condition-icon').textContent = icon; $('#temperature').textContent = temp(current.temperature_2m).slice(0, -1);
  $('#temperature-unit').textContent = state.unit === 'c' ? '°C' : '°F'; $('#feels').textContent = temp(current.apparent_temperature);
  $('#wind').textContent = `${Math.round(current.wind_speed_10m)} km/h`; $('#humidity').textContent = `${current.relative_humidity_2m}%`; $('#precipitation').textContent = `${current.precipitation} mm`;
  const start = Math.max(0, hourly.time.findIndex((time) => time >= current.time));
  $('#hourly').innerHTML = hourly.time.slice(start, start + 24).map((time, index) => `<article class="hour ${index === 0 ? 'now' : ''}"><small>${index === 0 ? 'Now' : new Date(time).toLocaleTimeString([], { hour: 'numeric' })}</small><span class="weather-icon" aria-label="${describe(hourly.weather_code[start + index], hourly.is_day[start + index])[0]}">${describe(hourly.weather_code[start + index], hourly.is_day[start + index])[1]}</span><strong>${temp(hourly.temperature_2m[start + index])}</strong><small>💧 ${hourly.precipitation_probability[start + index]}%</small></article>`).join('');
  $('#daily').innerHTML = daily.time.slice(0, 7).map((date, index) => { const desc = describe(daily.weather_code[index]); return `<article class="day"><div><strong>${index === 0 ? 'Today' : new Date(`${date}T12:00`).toLocaleDateString([], { weekday: 'long' })}</strong><div class="day-date">${new Date(`${date}T12:00`).toLocaleDateString([], { month: 'short', day: 'numeric' })}</div></div><div class="day-condition"><span class="weather-icon">${desc[1]}</span><span>${desc[0]}</span></div><div class="temp-bar"></div><div class="day-temp"><strong>${temp(daily.temperature_2m_max[index])}</strong><span>${temp(daily.temperature_2m_min[index])}</span></div></article>`; }).join('');
  $('#status').hidden = true; $('#error').hidden = true; $('#weather').hidden = false;
}

async function searchCities(query) {
  if (query.trim().length < 2) { $('#suggestions').hidden = true; return; }
  try {
    const data = await request(`https://geocoding-api.open-meteo.com/v1/search?name=${encodeURIComponent(query)}&count=6&language=en&format=json`);
    const results = data.results || []; $('#suggestions').innerHTML = results.length ? results.map((place, i) => `<li><button type="button" data-index="${i}" role="option"><strong>${place.name}</strong> · ${[place.admin1, place.country].filter(Boolean).join(', ')}</button></li>`).join('') : '<li><button type="button" disabled>No matching places found</button></li>';
    $('#suggestions').hidden = false; $('#suggestions').querySelectorAll('[data-index]').forEach((button) => button.onclick = () => { const place = results[button.dataset.index]; $('#city-search').value = place.name; $('#suggestions').hidden = true; loadWeather(place); });
  } catch (error) { showError(error.message); }
}

$('#city-search').addEventListener('input', (event) => { clearTimeout(state.searchTimer); state.searchTimer = setTimeout(() => searchCities(event.target.value), 280); });
$('#search-form').addEventListener('submit', async (event) => { event.preventDefault(); const query = $('#city-search').value.trim(); if (!query) return; try { const data = await request(`https://geocoding-api.open-meteo.com/v1/search?name=${encodeURIComponent(query)}&count=1&language=en&format=json`); if (!data.results?.length) return showError(`No results found for “${query}”.`); $('#suggestions').hidden = true; loadWeather(data.results[0]); } catch (error) { showError(error.message); } });
document.addEventListener('click', (event) => { if (!event.target.closest('.search-wrap')) $('#suggestions').hidden = true; });
document.querySelectorAll('.unit').forEach((button) => button.addEventListener('click', () => { state.unit = button.dataset.unit; document.querySelectorAll('.unit').forEach((item) => { const active = item === button; item.classList.toggle('active', active); item.setAttribute('aria-pressed', active); }); if (state.weather) render(); }));
$('#locate').addEventListener('click', () => { if (!navigator.geolocation) return showError('Location is not supported by this browser.'); showLoading(); navigator.geolocation.getCurrentPosition((position) => loadWeather({ name: 'Your location', latitude: position.coords.latitude, longitude: position.coords.longitude }), (error) => showError(error.code === 1 ? 'Location access was denied. You can still search for a city.' : 'Your location could not be determined.'), { timeout: 10000 }); });
$('#retry').addEventListener('click', () => loadWeather(state.place || MUNICH));
window.addEventListener('offline', () => showError('You appear to be offline. Reconnect and try again.'));

loadWeather(safeStore.get() || MUNICH, false);
