/**
 * Smart ventilation controller – Dashboard-Karte.
 *
 * Wird von der Integration selbst ausgeliefert und im Frontend angemeldet.
 * Darstellungen: Bild, Werte, Mini; optional Einstellungen direkt in der Karte.
 * Die Karte findet alle Entitäten über das gewählte Gerät, Messwerte kommen aus
 * den Attributen des Status-Sensors.
 */

const DOMAIN = "smart_ventilation_controller";
const CARD_TYPE = "smart-ventilation-card";
const DEFAULT_IMAGE = `/${DOMAIN}/smart-ventilation-card.webp`;
const INTEGRATION_PAGE = `/config/integrations/integration/${DOMAIN}`;

const DEFAULTS = {
  layout: "image",
  show_absolute_humidity: true,
  show_dew_points: false,
  show_difference_bar: true,
  gray_when_off: true,
  allow_settings: true,
  tap: "more-info",
};

// Schwellwerte, die in der Karte einstellbar sind (Übersetzungsschlüssel der Number-Entitäten)
const SETTINGS = [
  { key: "min_humidity", section: "rh", label: "humidity_on", unit: "%", digits: 0, color: "#57BB8A" },
  { key: "min_humidity_off", section: "rh", label: "humidity_off", unit: "%", digits: 0, color: "#F2A33A" },
  { key: "buffer_on", section: "ah", label: "buffer_on", unit: "g/m³", digits: 1, color: "#57BB8A" },
  { key: "buffer_off", section: "ah", label: "buffer_off", unit: "g/m³", digits: 1, color: "#F2A33A" },
  { key: "dewpoint_margin", section: "ah", label: "margin", unit: "°C", digits: 1, color: "var(--primary-color)" },
  { key: "min_battery", section: "battery", label: "min_battery", unit: "%", digits: 0, color: "#F2A33A" },
];

const TEXTS = {
  de: {
    indoor: "Innen",
    outdoor: "Außen",
    rel: "rel. Feuchte",
    abs: "abs. Feuchte",
    dew: "Taupunkt",
    difference: "Feuchtedifferenz innen – außen",
    on: "ein",
    off: "aus",
    automatic: "Automatik",
    settings: "Einstellungen ein- oder ausblenden",
    quiet_hours: "Nachtruhe",
    runtime: "Laufzeit",
    no_pause: "keine Pause",
    pause_until: "Pause bis",
    since: "seit",
    section_rh: "Relative Feuchte innen",
    section_ah: "Absolute Feuchte (Differenz innen – außen)",
    section_battery: "Batterie",
    humidity_on: "Einschalten ab",
    humidity_off: "Ausschalten unter",
    buffer_on: "Einschalt-Puffer",
    buffer_off: "Ausschalt-Puffer",
    margin: "Taupunkt-Sicherheitsabstand",
    min_battery: "Mindest-Ladezustand",
    more_options: "Laufzeit, Nachtruhe und Benachrichtigungen in der Integration konfigurieren",
    no_device: "Bitte im Karten-Editor ein Gerät des Smart ventilation controller auswählen.",
    not_found: "Für dieses Gerät wurden keine Entitäten des Smart ventilation controller gefunden.",
    error: "Fehler",
    device: "Gerät",
    layout: "Darstellung",
    layout_image: "Bild",
    layout_values: "Werte",
    layout_mini: "Mini",
    image: "Eigenes Hintergrundbild (optional)",
    show_absolute_humidity: "Absolute Feuchte anzeigen",
    show_dew_points: "Taupunkte anzeigen",
    show_difference_bar: "Differenz-Balken mit Schaltschwellen",
    gray_when_off: "Bild grau, wenn der Lüfter steht",
    allow_settings: "Einstellungen in der Karte erlauben",
    tap: "Tippen auf die Karte",
    tap_more_info: "Details öffnen",
    tap_toggle_automatic: "Automatik umschalten",
    tap_none: "Nichts tun",
    card_description: "Lüftung nach absoluter Feuchte: Werte innen und außen, Status und Einstellungen.",
  },
  en: {
    indoor: "Indoor",
    outdoor: "Outdoor",
    rel: "Rel. humidity",
    abs: "Abs. humidity",
    dew: "Dew point",
    difference: "Humidity difference indoor – outdoor",
    on: "on",
    off: "off",
    automatic: "Automatic",
    settings: "Show or hide settings",
    quiet_hours: "Quiet hours",
    runtime: "Runtime",
    no_pause: "no pause",
    pause_until: "Pause until",
    since: "for",
    section_rh: "Indoor relative humidity",
    section_ah: "Absolute humidity (difference indoor – outdoor)",
    section_battery: "Battery",
    humidity_on: "Turn on from",
    humidity_off: "Turn off below",
    buffer_on: "Turn-on buffer",
    buffer_off: "Turn-off buffer",
    margin: "Dew point safety margin",
    min_battery: "Minimum battery level",
    more_options: "Configure runtime, quiet hours and notifications in the integration",
    no_device: "Please select a Smart ventilation controller device in the card editor.",
    not_found: "No Smart ventilation controller entities found for this device.",
    error: "Error",
    device: "Device",
    layout: "Layout",
    layout_image: "Image",
    layout_values: "Values",
    layout_mini: "Mini",
    image: "Custom background image (optional)",
    show_absolute_humidity: "Show absolute humidity",
    show_dew_points: "Show dew points",
    show_difference_bar: "Difference bar with switching thresholds",
    gray_when_off: "Gray image while the fan is off",
    allow_settings: "Allow settings in the card",
    tap: "Tap on the card",
    tap_more_info: "Open details",
    tap_toggle_automatic: "Toggle automatic mode",
    tap_none: "Do nothing",
    card_description: "Ventilation by absolute humidity: indoor and outdoor values, status and settings.",
  },
};

const STATUS_COLORS = {
  running: "#57BB8A",
  night: "#8AB4F8",
  pause: "#8AB4F8",
  disabled: "#9AA0A6",
  condensation: "#F2A33A",
  battery_low: "#F2A33A",
  battery_unknown: "#F2A33A",
};
const STATUS_COLOR_DEFAULT = "#F28B82";

const FAN_PATH =
  "M12,11A1,1 0 0,0 11,12A1,1 0 0,0 12,13A1,1 0 0,0 13,12A1,1 0 0,0 12,11M12.5,2C17,2 17.11,5.57 14.75,6.75C13.76,7.24 13.32,8.29 13.13,9.22C13.61,9.42 14.03,9.73 14.35,10.13C18.05,8.13 22.03,8.92 22.03,12.5C22.03,17 18.46,17.1 17.28,14.73C16.78,13.74 15.72,13.3 14.79,13.11C14.59,13.59 14.28,14 13.88,14.34C15.87,18.03 15.08,22 11.5,22C7,22 6.91,18.42 9.27,17.24C10.25,16.75 10.69,15.71 10.89,14.79C10.4,14.59 9.97,14.27 9.65,13.87C5.96,15.85 2,15.07 2,11.5C2,7 5.56,6.89 6.74,9.26C7.24,10.25 8.29,10.68 9.22,10.87C9.41,10.39 9.73,9.97 10.14,9.65C8.15,5.96 8.94,2 12.5,2Z";
const GEAR_SVG =
  '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"></path></svg>';

const fanSvg = (size, color) =>
  `<svg width="${size}" height="${size}" viewBox="0 0 24 24" aria-hidden="true" style="color:${color}"><path fill="currentColor" d="${FAN_PATH}"></path></svg>`;

const escapeHtml = (value) =>
  String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

const language = (hass) => ((hass && (hass.locale?.language || hass.language)) || "en").split("-")[0];
const texts = (hass) => (language(hass) === "de" ? TEXTS.de : TEXTS.en);

const formatNumber = (hass, value, digits) => {
  if (value === null || value === undefined || value === "" || Number.isNaN(Number(value))) return "–";
  return new Intl.NumberFormat(language(hass), {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(Number(value));
};

/** Geräte des Smart ventilation controller (eines pro Eintrag, erkannt am Status-Sensor). */
const findDevices = (hass) => {
  const devices = new Set();
  for (const entity of Object.values(hass?.entities || {})) {
    if (entity.platform === DOMAIN && entity.translation_key === "status" && entity.device_id) {
      devices.add(entity.device_id);
    }
  }
  return [...devices];
};

/** Entitäten eines Geräts, nach Übersetzungsschlüssel (z. B. status, automatic, min_humidity). */
const findEntities = (hass, deviceId) => {
  const result = {};
  for (const entity of Object.values(hass?.entities || {})) {
    if (entity.platform === DOMAIN && entity.device_id === deviceId && entity.translation_key) {
      result[entity.translation_key] = entity.entity_id;
    }
  }
  return result;
};

const fireEvent = (node, type, detail) => {
  node.dispatchEvent(new CustomEvent(type, { detail, bubbles: true, composed: true }));
};

const navigate = (path) => {
  window.history.pushState(null, "", path);
  window.dispatchEvent(new CustomEvent("location-changed", { detail: { replace: false } }));
};

const STYLE = `
  :host { display: block; }
  ha-card { overflow: hidden; color: var(--primary-text-color); }
  .message { padding: 16px; color: var(--secondary-text-color); }
  .error { margin: 0 16px 12px; color: var(--error-color, #F28B82); font-size: 13px; }
  .clickable { cursor: pointer; }

  /* Bild */
  .scene { position: relative; aspect-ratio: 3 / 2; background: #1C1E22; }
  .scene img { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; transition: filter 0.6s; }
  .overlay { position: absolute; color: #fff; font-weight: 500; text-shadow: 0 0 3px #000, 0 0 8px #000; }
  .chip { display: flex; align-items: center; gap: 6px; padding: 4px 10px 4px 8px; border-radius: 999px;
          background: rgba(17, 19, 24, 0.72); font-size: 13px; text-shadow: none; }
  .name { left: 2.5%; top: 3.7%; }
  .badge { left: 42.75%; top: 34.5%; padding: 3px 9px; border-radius: 999px; background: rgba(17, 19, 24, 0.78);
           font-size: 12px; font-weight: 700; color: #8AB4F8; text-shadow: none; white-space: nowrap; }
  .block { display: flex; flex-direction: column; gap: 4px; font-size: 15px; }
  .block .caption { font-size: 11px; letter-spacing: 0.08em; text-transform: uppercase; color: #E3E6EA; }
  .indoor { left: 5.5%; bottom: 52px; }
  .outdoor { right: 4.5%; top: 6.7%; align-items: flex-end; }
  .statusbar { position: absolute; left: 0; right: 0; bottom: 0; min-height: 40px; display: flex; align-items: center;
               gap: 8px; padding: 0 6px 0 14px; background: rgba(17, 19, 24, 0.86); color: #fff; font-size: 13px; font-weight: 500; }
  .statusbar .text { flex: 1; min-width: 0; padding: 8px 0; }
  .dot { width: 9px; height: 9px; border-radius: 50%; flex: none; }
  .icon-button { width: 40px; height: 40px; border: 0; border-radius: 50%; background: transparent; color: inherit;
                 display: flex; align-items: center; justify-content: center; cursor: pointer; flex: none; }
  .icon-button:hover, .icon-button.active { background: rgba(255, 255, 255, 0.12); }

  /* Werte */
  .content { padding: 16px; display: flex; flex-direction: column; gap: 14px; }
  .header { display: flex; align-items: center; gap: 12px; }
  .fan { width: 42px; height: 42px; border-radius: 50%; display: flex; align-items: center; justify-content: center; flex: none; }
  .title { display: flex; flex-direction: column; gap: 2px; flex: 1; min-width: 0; }
  .title .name-text { font-size: 16px; font-weight: 500; }
  .title .status { font-size: 13px; color: var(--secondary-text-color); }
  .switch { display: flex; align-items: center; gap: 8px; font-size: 12px; color: var(--secondary-text-color); }
  .switch input { width: 18px; height: 18px; accent-color: var(--primary-color); }
  .columns { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
  .tile { padding: 12px; border-radius: 10px; background: var(--secondary-background-color, rgba(127, 127, 127, 0.12));
          display: flex; flex-direction: column; gap: 8px; }
  .tile .caption { font-size: 11px; letter-spacing: 0.08em; text-transform: uppercase; color: var(--secondary-text-color); }
  .tile .big { font-size: 26px; font-weight: 500; }
  .row { display: flex; justify-content: space-between; gap: 8px; font-size: 13px; }
  .row .label { color: var(--secondary-text-color); }
  .chips { display: flex; flex-wrap: wrap; gap: 6px; font-size: 12px; }
  .chips span { padding: 4px 10px; border-radius: 999px; background: var(--secondary-background-color, rgba(127, 127, 127, 0.12)); }
  .chips span.active { color: #8AB4F8; }

  /* Differenz-Balken */
  .diff { display: flex; flex-direction: column; gap: 6px; }
  .scene ~ .diff { padding: 12px 16px 14px; }
  .diff .value { font-weight: 700; color: var(--primary-color); }
  .bar { position: relative; height: 10px; border-radius: 5px; background: var(--divider-color, rgba(127, 127, 127, 0.3)); }
  .bar .fill { position: absolute; left: 0; top: 0; height: 10px; border-radius: 5px; background: var(--primary-color); }
  .bar .mark { position: absolute; top: -3px; width: 2px; height: 16px; }
  .scale { position: relative; height: 14px; font-size: 11px; color: var(--secondary-text-color); }
  .scale span { position: absolute; white-space: nowrap; }

  /* Mini */
  .mini { display: flex; align-items: center; gap: 12px; padding: 12px 14px; }
  .mini .fan { width: 40px; height: 40px; }
  .mini .delta { display: flex; flex-direction: column; align-items: flex-end; gap: 2px; }
  .mini .delta .value { font-size: 18px; font-weight: 700; color: var(--primary-color); }
  .mini .delta .sub { font-size: 11px; color: var(--secondary-text-color); white-space: nowrap; }

  /* Einstellungen */
  .panel { display: flex; flex-direction: column; gap: 12px; padding: 12px 16px 16px; }
  .content .panel { padding: 12px 0 0; border-top: 1px solid var(--divider-color, rgba(127, 127, 127, 0.3)); }
  .panel .section { font-size: 11px; letter-spacing: 0.08em; text-transform: uppercase; color: var(--secondary-text-color); padding-top: 4px; }
  .panel label.slider { display: flex; flex-direction: column; gap: 4px; font-size: 13px; }
  .panel label.slider .line { display: flex; justify-content: space-between; }
  .panel label.slider .val { font-weight: 700; }
  .panel input[type="range"] { width: 100%; }
  .panel a { color: var(--primary-color); font-size: 13px; }
`;

class SmartVentilationCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._open = false;
    this._dragging = false;
    this._error = null;
    this._signature = null;
  }

  static getConfigElement() {
    return document.createElement(`${CARD_TYPE}-editor`);
  }

  static getStubConfig(hass) {
    return { device: findDevices(hass)[0] || "" };
  }

  setConfig(config) {
    if (!config || typeof config !== "object") throw new Error("Invalid configuration");
    this._config = { ...DEFAULTS, ...config };
    this._signature = null;
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  getCardSize() {
    if (this._config?.layout === "mini") return 1;
    return this._config?.layout === "values" ? 5 : 4;
  }

  // --- Daten -----------------------------------------------------------------------

  _data() {
    const hass = this._hass;
    const entities = findEntities(hass, this._config.device);
    const statusState = entities.status ? hass.states[entities.status] : undefined;
    const device = hass.devices?.[this._config.device];
    return {
      entities,
      status: statusState,
      attrs: statusState?.attributes || {},
      name: device?.name_by_user || device?.name || "Smart ventilation",
    };
  }

  _statusText(state) {
    // Das Emoji am Anfang ersetzt die Karte durch einen farbigen Punkt
    return String(state?.state ?? "–").replace(/^[^\p{L}\p{N}]+/u, "");
  }

  // --- Rendern ---------------------------------------------------------------------

  _render() {
    if (!this._config || !this._hass || this._dragging) return;
    const hass = this._hass;
    const t = texts(hass);

    if (!this._config.device) {
      this._paint(`<ha-card><div class="message">${escapeHtml(t.no_device)}</div></ha-card>`, null);
      return;
    }
    const data = this._data();
    const ids = Object.values(data.entities);
    const signature = JSON.stringify([
      this._config,
      this._open,
      this._error,
      language(hass),
      data.name,
      ids.map((id) => [id, hass.states[id]?.state, hass.states[id]?.last_updated]),
    ]);
    if (signature === this._signature) return;

    if (!data.status) {
      this._paint(`<ha-card><div class="message">${escapeHtml(t.not_found)}</div></ha-card>`, signature);
      return;
    }

    const layout = this._config.layout;
    let body;
    if (layout === "mini") body = this._renderMini(data, t);
    else if (layout === "values") body = this._renderValues(data, t);
    else body = this._renderImage(data, t);

    const error = this._error ? `<div class="error">${escapeHtml(t.error)}: ${escapeHtml(this._error)}</div>` : "";
    this._paint(`<ha-card>${body}${error}</ha-card>`, signature);
    this._bind(data);
  }

  _paint(html, signature) {
    this.shadowRoot.innerHTML = `<style>${STYLE}</style>${html}`;
    this._signature = signature;
  }

  _valueLines(data, t, side) {
    const a = data.attrs;
    const hass = this._hass;
    const prefix = side === "indoor" ? "indoor" : "outdoor";
    const lines = [
      [t.rel, `${formatNumber(hass, a[`${prefix}_humidity`], 1)} %`],
    ];
    if (this._config.show_absolute_humidity) {
      lines.push([t.abs, `${formatNumber(hass, a[`absolute_humidity_${prefix}`], 2)} g/m³`]);
    }
    if (this._config.show_dew_points) {
      lines.push([t.dew, `${formatNumber(hass, a[`dew_point_${prefix}`], 1)} °C`]);
    }
    return { temperature: `${formatNumber(hass, a[`${prefix}_temperature`], 1)} °C`, lines };
  }

  _statusDot(data) {
    const color = STATUS_COLORS[data.attrs.code] || STATUS_COLOR_DEFAULT;
    return `<span class="dot" style="background:${color}"></span>`;
  }

  _gearButton(t) {
    if (!this._config.allow_settings) return "";
    return `<button type="button" class="icon-button${this._open ? " active" : ""}" data-action="settings"
      aria-label="${escapeHtml(t.settings)}" aria-expanded="${this._open}">${GEAR_SVG}</button>`;
  }

  _renderImage(data, t) {
    const a = data.attrs;
    const hass = this._hass;
    const image = this._config.image || DEFAULT_IMAGE;
    const filter = this._config.gray_when_off && !a.fan_on ? "grayscale(85%) brightness(80%)" : "none";
    const fanColor = a.fan_on ? "#8AB4F8" : "#C9CDD2";
    const block = (side, cls) => {
      const v = this._valueLines(data, t, side);
      const caption = side === "indoor" ? t.indoor : t.outdoor;
      return `<div class="overlay block ${cls}"><span class="caption">${escapeHtml(caption)}</span>
        <span>${escapeHtml(v.temperature)}</span>${v.lines.map(([, value]) => `<span>${escapeHtml(value)}</span>`).join("")}</div>`;
    };
    const panel = this._open && this._config.allow_settings ? this._renderPanel(data, t) : "";
    const bar = this._config.show_difference_bar ? this._renderDifferenceBar(data, t) : "";
    return `
      <div class="scene clickable" data-action="tap">
        <img src="${escapeHtml(image)}" alt="" style="filter:${filter}">
        <div class="overlay chip name">${fanSvg(16, fanColor)}<span>${escapeHtml(data.name)}</span></div>
        <div class="overlay badge">Δ ${escapeHtml(formatNumber(hass, a.difference, 1))} g/m³</div>
        ${block("indoor", "indoor")}
        ${block("outdoor", "outdoor")}
        <div class="statusbar">${this._statusDot(data)}<span class="text">${escapeHtml(this._statusText(data.status))}</span>${this._gearButton(t)}</div>
      </div>
      ${bar}${panel}`;
  }

  _renderValues(data, t) {
    const a = data.attrs;
    const hass = this._hass;
    const fanBg = a.fan_on ? "rgba(138, 180, 248, 0.18)" : "var(--secondary-background-color, rgba(127, 127, 127, 0.15))";
    const fanColor = a.fan_on ? "#8AB4F8" : "var(--secondary-text-color)";
    const tile = (side) => {
      const v = this._valueLines(data, t, side);
      return `<div class="tile"><span class="caption">${escapeHtml(side === "indoor" ? t.indoor : t.outdoor)}</span>
        <span class="big">${escapeHtml(v.temperature)}</span>
        ${v.lines.map(([label, value]) => `<div class="row"><span class="label">${escapeHtml(label)}</span><span>${escapeHtml(value)}</span></div>`).join("")}</div>`;
    };
    const automatic = data.entities.automatic
      ? `<label class="switch">${escapeHtml(t.automatic)}<input type="checkbox" data-action="automatic" ${hass.states[data.entities.automatic]?.state === "on" ? "checked" : ""}></label>`
      : "";
    const chips = [];
    if (a.night_enabled) {
      chips.push(`<span class="${a.night_active ? "active" : ""}">${escapeHtml(t.quiet_hours)} ${escapeHtml(a.night_start)}–${escapeHtml(a.night_end)}</span>`);
    }
    chips.push(`<span>${escapeHtml(t.runtime)} ${escapeHtml(formatNumber(hass, a.runtime_minutes, 0))} min</span>`);
    chips.push(a.pause_until
      ? `<span class="active">${escapeHtml(t.pause_until)} ${escapeHtml(this._time(a.pause_until))}</span>`
      : `<span>${escapeHtml(t.no_pause)}</span>`);
    const panel = this._open && this._config.allow_settings ? this._renderPanel(data, t) : "";
    return `
      <div class="content">
        <div class="header">
          <div class="fan clickable" data-action="tap" style="background:${fanBg}">${fanSvg(24, fanColor)}</div>
          <div class="title clickable" data-action="tap"><span class="name-text">${escapeHtml(data.name)}</span>
            <span class="status">${escapeHtml(this._statusText(data.status))}</span></div>
          ${automatic}${this._gearButton(t)}
        </div>
        <div class="columns">${tile("indoor")}${tile("outdoor")}</div>
        ${this._config.show_difference_bar ? this._renderDifferenceBar(data, t) : ""}
        <div class="chips">${chips.join("")}</div>
        ${panel}
      </div>`;
  }

  _renderMini(data, t) {
    const a = data.attrs;
    const hass = this._hass;
    const fanBg = a.fan_on ? "rgba(138, 180, 248, 0.18)" : "var(--secondary-background-color, rgba(127, 127, 127, 0.15))";
    const fanColor = a.fan_on ? "#8AB4F8" : "var(--secondary-text-color)";
    const status = a.fan_on && a.runtime_minutes
      ? `${this._statusText(data.status)} · ${t.since} ${formatNumber(hass, a.runtime_minutes, 0)} min`
      : this._statusText(data.status);
    return `
      <div class="mini clickable" data-action="tap">
        <div class="fan" style="background:${fanBg}">${fanSvg(22, fanColor)}</div>
        <div class="title"><span class="name-text">${escapeHtml(data.name)}</span><span class="status">${escapeHtml(status)}</span></div>
        <div class="delta"><span class="value">Δ ${escapeHtml(formatNumber(hass, a.difference, 1))}</span>
          <span class="sub">g/m³ · ${escapeHtml(formatNumber(hass, a.indoor_humidity, 1))} % ${escapeHtml(t.indoor.toLowerCase())}</span></div>
      </div>`;
  }

  _renderDifferenceBar(data, t) {
    const a = data.attrs;
    const hass = this._hass;
    const bufferOn = Number(a.buffer_on) || 0;
    const bufferOff = Number(a.buffer_off) || 0;
    const diff = Number(a.difference);
    const max = Math.max(5, Math.ceil(Math.max(bufferOn * 2, Number.isNaN(diff) ? 0 : diff)));
    const pct = (v) => `${Math.min(100, Math.max(0, (v / max) * 100))}%`;
    return `
      <div class="diff">
        <div class="row"><span class="label">${escapeHtml(t.difference)}</span>
          <span class="value">${escapeHtml(formatNumber(hass, a.difference, 1))} g/m³</span></div>
        <div class="bar">
          <div class="fill" style="width:${Number.isNaN(diff) ? "0%" : pct(diff)}"></div>
          <div class="mark" style="left:${pct(bufferOff)};background:#F2A33A"></div>
          <div class="mark" style="left:${pct(bufferOn)};background:#57BB8A"></div>
        </div>
        <div class="scale">
          <span style="left:0">0</span>
          <span style="left:${pct(bufferOff)};transform:translateX(-50%)">${escapeHtml(t.off)} ${escapeHtml(formatNumber(hass, bufferOff, 1))}</span>
          <span style="left:${pct(bufferOn)};transform:translateX(-50%)">${escapeHtml(t.on)} ${escapeHtml(formatNumber(hass, bufferOn, 1))}</span>
          <span style="right:0">${max} g/m³</span>
        </div>
      </div>`;
  }

  _renderPanel(data, t) {
    const hass = this._hass;
    const parts = [];
    if (data.entities.automatic) {
      const on = hass.states[data.entities.automatic]?.state === "on";
      parts.push(`<label class="row" style="font-size:14px;align-items:center"><span>${escapeHtml(t.automatic)}</span>
        <input type="checkbox" data-action="automatic" ${on ? "checked" : ""} style="width:20px;height:20px;accent-color:var(--primary-color)"></label>`);
    }
    let section = null;
    for (const setting of SETTINGS) {
      const entityId = data.entities[setting.key];
      const state = entityId && hass.states[entityId];
      if (!state) continue;
      if (setting.section !== section) {
        section = setting.section;
        parts.push(`<span class="section">${escapeHtml(t[`section_${section}`])}</span>`);
      }
      const attrs = state.attributes || {};
      parts.push(`<label class="slider"><span class="line"><span>${escapeHtml(t[setting.label])}</span>
          <span class="val" data-value-for="${escapeHtml(entityId)}">${escapeHtml(formatNumber(hass, state.state, setting.digits))} ${escapeHtml(setting.unit)}</span></span>
        <input type="range" data-entity="${escapeHtml(entityId)}" data-digits="${setting.digits}" data-unit="${escapeHtml(setting.unit)}"
          min="${attrs.min ?? 0}" max="${attrs.max ?? 100}" step="${attrs.step ?? 1}" value="${escapeHtml(state.state)}"
          style="accent-color:${setting.color}"></label>`);
    }
    parts.push(`<a href="${INTEGRATION_PAGE}" data-action="integration">${escapeHtml(t.more_options)}</a>`);
    return `<div class="panel">${parts.join("")}</div>`;
  }

  _time(iso) {
    const date = new Date(iso);
    if (Number.isNaN(date.getTime())) return "–";
    return new Intl.DateTimeFormat(language(this._hass), { hour: "2-digit", minute: "2-digit" }).format(date);
  }

  // --- Bedienung -------------------------------------------------------------------

  _bind(data) {
    const root = this.shadowRoot;
    root.querySelectorAll('[data-action="tap"]').forEach((el) =>
      el.addEventListener("click", (ev) => {
        if (ev.target.closest("button, input, a")) return;
        this._tap(data);
      })
    );
    root.querySelectorAll('[data-action="settings"]').forEach((el) =>
      el.addEventListener("click", (ev) => {
        ev.stopPropagation();
        this._open = !this._open;
        this._render();
      })
    );
    root.querySelectorAll('[data-action="automatic"]').forEach((el) =>
      el.addEventListener("change", (ev) => {
        ev.stopPropagation();
        this._toggleAutomatic(data);
      })
    );
    root.querySelectorAll('[data-action="integration"]').forEach((el) =>
      el.addEventListener("click", (ev) => {
        ev.preventDefault();
        navigate(INTEGRATION_PAGE);
      })
    );
    root.querySelectorAll("input[type=range][data-entity]").forEach((input) => {
      const label = root.querySelector(`[data-value-for="${CSS.escape(input.dataset.entity)}"]`);
      input.addEventListener("input", () => {
        this._dragging = true;
        if (label) label.textContent = `${formatNumber(this._hass, input.value, Number(input.dataset.digits))} ${input.dataset.unit}`;
      });
      input.addEventListener("change", () => {
        this._dragging = false;
        this._setNumber(input.dataset.entity, Number(input.value));
      });
    });
  }

  _tap(data) {
    const action = this._config.tap;
    if (action === "none") return;
    if (action === "toggle_automatic") {
      this._toggleAutomatic(data);
      return;
    }
    fireEvent(this, "hass-more-info", { entityId: data.entities.status });
  }

  async _toggleAutomatic(data) {
    const entityId = data.entities.automatic;
    if (!entityId) return;
    const on = this._hass.states[entityId]?.state === "on";
    await this._call("switch", on ? "turn_off" : "turn_on", { entity_id: entityId });
  }

  async _setNumber(entityId, value) {
    await this._call("number", "set_value", { entity_id: entityId, value });
  }

  async _call(domain, service, data) {
    try {
      this._error = null;
      await this._hass.callService(domain, service, data);
    } catch (err) {
      // z. B. Ausschalt-Feuchte über Einschalt-Feuchte: Meldung der Integration anzeigen
      this._error = err?.message || String(err);
    }
    this._signature = null;
    this._render();
  }
}

class SmartVentilationCardEditor extends HTMLElement {
  setConfig(config) {
    this._config = { ...DEFAULTS, ...config };
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  _schema(t) {
    return [
      { name: "device", required: true, selector: { device: { filter: { integration: DOMAIN } } } },
      {
        name: "layout",
        selector: {
          select: {
            mode: "list",
            options: [
              { value: "image", label: t.layout_image },
              { value: "values", label: t.layout_values },
              { value: "mini", label: t.layout_mini },
            ],
          },
        },
      },
      { name: "image", selector: { text: {} } },
      { name: "show_absolute_humidity", selector: { boolean: {} } },
      { name: "show_dew_points", selector: { boolean: {} } },
      { name: "show_difference_bar", selector: { boolean: {} } },
      { name: "gray_when_off", selector: { boolean: {} } },
      { name: "allow_settings", selector: { boolean: {} } },
      {
        name: "tap",
        selector: {
          select: {
            mode: "dropdown",
            options: [
              { value: "more-info", label: t.tap_more_info },
              { value: "toggle_automatic", label: t.tap_toggle_automatic },
              { value: "none", label: t.tap_none },
            ],
          },
        },
      },
    ];
  }

  _render() {
    if (!this._hass || !this._config) return;
    const t = texts(this._hass);
    if (!this._form) {
      this._form = document.createElement("ha-form");
      this._form.addEventListener("value-changed", (ev) => {
        this._config = { ...this._config, ...ev.detail.value };
        fireEvent(this, "config-changed", { config: this._config });
      });
      this.appendChild(this._form);
    }
    this._form.hass = this._hass;
    this._form.data = this._config;
    this._form.schema = this._schema(t);
    this._form.computeLabel = (schema) => t[schema.name] ?? schema.name;
  }
}

if (!customElements.get(CARD_TYPE)) {
  customElements.define(CARD_TYPE, SmartVentilationCard);
  customElements.define(`${CARD_TYPE}-editor`, SmartVentilationCardEditor);
  window.customCards = window.customCards || [];
  window.customCards.push({
    type: CARD_TYPE,
    name: "Smart ventilation controller",
    description: texts(document.querySelector("home-assistant")?.hass).card_description,
    preview: true,
    documentationURL: "https://github.com/berwil84afk/ha-smart-ventilation",
  });
}
