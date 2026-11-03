// Fuel Finder frontend: asks the API for stations and shows them nearest first.

// Area centres used when someone picks an area instead of sharing their location.
const AREAS = {
  Ajah: [6.4683, 3.5726],
  Apapa: [6.4489, 3.3594],
  Festac: [6.4664, 3.2833],
  Gbagada: [6.556, 3.385],
  Ikeja: [6.6018, 3.3515],
  Ikorodu: [6.6194, 3.5105],
  Lekki: [6.4474, 3.4723],
  Maryland: [6.5711, 3.365],
  Ojota: [6.5866, 3.3797],
  Surulere: [6.5005, 3.3534],
  'Victoria Island': [6.4281, 3.4219],
  Yaba: [6.5095, 3.3711],
};

const els = {
  locate: document.getElementById('locate'),
  area: document.getElementById('area'),
  fuel: document.getElementById('fuel'),
  openOnly: document.getElementById('open-only'),
  where: document.getElementById('where'),
  list: document.getElementById('stations'),
  empty: document.getElementById('empty'),
  status: document.getElementById('status'),
  statusText: document.getElementById('status-text'),
  version: document.getElementById('version'),
  env: document.getElementById('env'),
};

let position = null; // { lat, lng } once known

function setStatus(ok, text) {
  els.status.classList.toggle('ok', ok);
  els.status.classList.toggle('down', !ok);
  els.statusText.textContent = text;
}

async function api(path) {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`Request failed (${res.status})`);
  return res.json();
}

function naira(amount) {
  return '₦' + amount.toLocaleString('en-NG');
}

function directionsUrl(s) {
  return `https://www.google.com/maps/dir/?api=1&destination=${s.lat},${s.lng}`;
}

function render(stations) {
  els.list.replaceChildren();
  for (const s of stations) {
    const li = document.createElement('li');
    li.className = 'station' + (s.is_open ? '' : ' is-closed');

    const main = document.createElement('div');
    main.className = 'station-main';

    const name = document.createElement('p');
    name.className = 'station-name';
    name.textContent = s.name;

    const meta = document.createElement('p');
    meta.className = 'station-meta';
    const open = document.createElement('span');
    open.className = 'badge ' + (s.is_open ? 'open' : 'closed');
    open.textContent = s.is_open ? 'Open' : 'Closed';
    meta.append(open, ' ' + s.area);
    for (const f of s.fuels) {
      const tag = document.createElement('span');
      tag.className = 'tag';
      tag.textContent = f;
      meta.append(' ', tag);
    }

    main.append(name, meta);

    const side = document.createElement('div');
    side.className = 'station-side';
    if (s.distance_km !== undefined) {
      const dist = document.createElement('p');
      dist.className = 'distance';
      dist.textContent = `${s.distance_km.toFixed(1)} km`;
      side.append(dist);
    }
    if (s.petrol_price) {
      const price = document.createElement('p');
      price.className = 'price';
      price.textContent = `Petrol ${naira(s.petrol_price)}/L`;
      side.append(price);
    }
    const link = document.createElement('a');
    link.className = 'directions';
    link.href = directionsUrl(s);
    link.target = '_blank';
    link.rel = 'noopener';
    link.textContent = 'Directions';
    side.append(link);

    li.append(main, side);
    els.list.append(li);
  }
  els.empty.hidden = stations.length > 0;
}

async function refresh() {
  const params = new URLSearchParams();
  if (position) {
    params.set('lat', position.lat);
    params.set('lng', position.lng);
  }
  if (els.fuel.value) params.set('fuel', els.fuel.value);
  if (els.openOnly.checked) params.set('open_only', 'true');

  try {
    render(await api('/api/stations?' + params));
    setStatus(true, 'Connected');
  } catch (err) {
    setStatus(false, 'API unreachable');
    console.error(err);
  }
}

els.locate.addEventListener('click', () => {
  if (!navigator.geolocation) {
    els.where.textContent = 'Your browser cannot share location. Pick an area instead.';
    return;
  }
  els.where.textContent = 'Finding your location…';
  navigator.geolocation.getCurrentPosition(
    (pos) => {
      position = { lat: pos.coords.latitude, lng: pos.coords.longitude };
      els.area.value = '';
      els.where.textContent = 'Sorted by distance from your location.';
      refresh();
    },
    () => {
      els.where.textContent = 'Location not available. Pick an area instead.';
    },
    { timeout: 10000 }
  );
});

els.area.addEventListener('change', () => {
  const coords = AREAS[els.area.value];
  if (coords) {
    position = { lat: coords[0], lng: coords[1] };
    els.where.textContent = `Sorted by distance from ${els.area.value}.`;
  } else {
    position = null;
    els.where.textContent = 'Showing all stations.';
  }
  refresh();
});

els.fuel.addEventListener('change', refresh);
els.openOnly.addEventListener('change', refresh);

async function start() {
  for (const name of Object.keys(AREAS)) els.area.append(new Option(name, name));
  els.fuel.append(new Option('Any fuel', ''));
  try {
    const info = await api('/api/info');
    for (const f of info.fuels) els.fuel.append(new Option(f === 'cng' ? 'CNG' : f[0].toUpperCase() + f.slice(1), f));
    els.version.textContent = `version ${info.version}`;
    els.env.textContent = `${info.environment} · ${info.store}`;
  } catch (err) {
    setStatus(false, 'API unreachable');
    console.error(err);
    return;
  }
  refresh();
}

start();
