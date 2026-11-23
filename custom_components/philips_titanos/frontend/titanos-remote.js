// Philips Titan OS TV panel for Home Assistant.
// Plain custom element: no build step and no third-party frontend resource.
// Every command goes through the TV's remote entity, so the same validation and
// safety rules apply as for any other service call.

const TAG = "philips-titanos-remote-panel";

const POWER_LABEL = {
  on: "On",
  playing: "On",
  off: "Standby",
  unknown: "Unknown",
  unavailable: "Unavailable",
};

const STYLE = `
  :host {
    display: block;
    box-sizing: border-box;
    min-height: 100%;
    padding: 16px;
    color: var(--primary-text-color, #212121);
    background: var(--primary-background-color, #fafafa);
    font-family: var(--paper-font-body1_-_font-family, Roboto, sans-serif);
  }
  .wrap { max-width: 420px; margin: 0 auto; }
  h1 { font-size: 20px; margin: 0; font-weight: 500; }
  .status { font-size: 14px; color: var(--secondary-text-color, #727272); margin-top: 2px; }
  h2 {
    font-size: 12px; text-transform: uppercase; letter-spacing: .04em;
    color: var(--secondary-text-color, #727272); margin: 18px 0 6px; font-weight: 500;
  }
  .grid {
    display: grid; gap: 8px;
    grid-template-columns: repeat(var(--cols, 3), minmax(0, 1fr));
  }
  .key {
    min-height: 56px; border: none; border-radius: 12px; padding: 6px 4px;
    display: flex; flex-direction: column; align-items: center; justify-content: center;
    gap: 2px; cursor: pointer; font: inherit; font-size: 12px;
    color: var(--primary-text-color, #212121);
    background: var(--card-background-color, #fff);
    box-shadow: 0 1px 2px rgba(0, 0, 0, .15);
  }
  .key ha-icon { --mdc-icon-size: 24px; }
  .key:active { transform: scale(.97); }
  .key:focus-visible { outline: 2px solid var(--primary-color, #03a9f4); outline-offset: 2px; }
  .key:disabled { opacity: .5; cursor: default; }
  .spacer { visibility: hidden; }
  .colour { color: #fff; font-weight: 500; }
  .colour.red { background: #e53935; }
  .colour.green { background: #43a047; }
  .colour.yellow { background: #fdd835; color: #212121; }
  .colour.blue { background: #1e88e5; }
  .error {
    margin: 14px 0 0; padding: 8px 12px; border-radius: 8px; font-size: 13px;
    background: var(--error-color, #db4437); color: #fff;
  }
  .error:empty { display: none; }
`;

function key({ label, icon, onClick }) {
  const el = document.createElement("button");
  el.type = "button";
  el.className = "key";
  el.setAttribute("aria-label", label);
  el.title = label;
  if (icon) {
    const i = document.createElement("ha-icon");
    i.setAttribute("icon", icon);
    el.appendChild(i);
  }
  const text = document.createElement("span");
  text.textContent = label;
  el.appendChild(text);
  el.addEventListener("click", onClick);
  return el;
}

function spacer() {
  const el = document.createElement("span");
  el.className = "spacer";
  return el;
}

function section(title, columns, children) {
  const wrap = document.createElement("section");
  if (title) {
    const h = document.createElement("h2");
    h.textContent = title;
    wrap.appendChild(h);
  }
  const grid = document.createElement("div");
  grid.className = "grid";
  grid.style.setProperty("--cols", String(columns));
  grid.append(...children);
  wrap.appendChild(grid);
  return wrap;
}

class PhilipsTitanosRemotePanel extends HTMLElement {
  constructor() {
    super();
    this._hass = undefined;
    this._config = {};
    this._built = false;
    this._busy = false;
  }

  set hass(hass) {
    this._hass = hass;
    this._refresh();
  }

  get hass() {
    return this._hass;
  }

  set panel(panel) {
    this._config = (panel && panel.config) || {};
    this._refresh();
  }

  connectedCallback() {
    this._build();
    this._refresh();
  }

  _build() {
    if (this._built) return;
    this._built = true;
    const root = this.attachShadow({ mode: "open" });
    const style = document.createElement("style");
    style.textContent = STYLE;
    root.appendChild(style);

    const wrap = document.createElement("div");
    wrap.className = "wrap";

    const title = document.createElement("h1");
    title.textContent = "TV";
    this._status = document.createElement("div");
    this._status.className = "status";
    this._error = document.createElement("p");
    this._error.className = "error";
    this._error.setAttribute("role", "alert");

    const send = (command) => () => this._send(command);
    const cmd = (label, icon, command) =>
      key({ label, icon, onClick: send(command) });
    const digit = (n) => cmd(String(n), null, `Digit${n}`);

    const power = section("Power", 4, [
      key({ label: "Wake", icon: "mdi:power-on", onClick: () => this._wake() }),
      key({ label: "Standby", icon: "mdi:power-standby", onClick: () => this._standby() }),
      cmd("Source", "mdi:video-input-hdmi", "Source"),
      cmd("Home", "mdi:home", "Home"),
    ]);

    const navigate = section("Navigate", 3, [
      cmd("Back", "mdi:arrow-u-left-top", "Back"),
      cmd("Up", "mdi:chevron-up", "CursorUp"),
      spacer(),
      cmd("Left", "mdi:chevron-left", "CursorLeft"),
      cmd("OK", "mdi:checkbox-marked-circle-outline", "Confirm"),
      cmd("Right", "mdi:chevron-right", "CursorRight"),
      spacer(),
      cmd("Down", "mdi:chevron-down", "CursorDown"),
      spacer(),
    ]);

    const volume = section("Volume and channel", 3, [
      cmd("Vol −", "mdi:volume-minus", "VolumeDown"),
      cmd("Mute", "mdi:volume-mute", "Mute"),
      cmd("Vol +", "mdi:volume-plus", "VolumeUp"),
      cmd("Ch −", "mdi:minus", "ChannelStepDown"),
      cmd("Ch +", "mdi:plus", "ChannelStepUp"),
    ]);

    const playback = section("Playback", 3, [
      cmd("Play", "mdi:play", "Play"),
      cmd("Pause", "mdi:pause", "Pause"),
      cmd("Live TV", "mdi:television", "WatchTV"),
    ]);

    const digits = section("Channels", 3, [
      digit(1), digit(2), digit(3),
      digit(4), digit(5), digit(6),
      digit(7), digit(8), digit(9),
      spacer(), digit(0), spacer(),
    ]);

    const colours = section("Colours", 4, [
      ["Red", "red", "RedColour"],
      ["Green", "green", "GreenColour"],
      ["Yellow", "yellow", "YellowColour"],
      ["Blue", "blue", "BlueColour"],
    ].map(([label, colour, command]) => {
      const el = cmd(label, null, command);
      el.classList.add("colour", colour);
      return el;
    }));

    wrap.append(
      title,
      this._status,
      power,
      navigate,
      volume,
      playback,
      digits,
      colours,
      this._error
    );
    root.appendChild(wrap);
    this._controls = [...root.querySelectorAll("button")];
  }

  _playerState() {
    const player = this._config.player;
    const state = this._hass && player ? this._hass.states[player] : undefined;
    return state ? state.state : "unknown";
  }

  _refresh() {
    if (!this._built) return;
    const state = this._playerState();
    this._status.textContent = `Status: ${POWER_LABEL[state] || state}`;
    const ready = Boolean(this._hass && this._config.remote);
    this._controls.forEach((b) => {
      b.disabled = !ready || this._busy;
    });
  }

  async _call(service, data) {
    this._error.textContent = "";
    this._busy = true;
    this._refresh();
    try {
      await this._hass.callService("remote", service, {
        entity_id: this._config.remote,
        ...data,
      });
    } catch (err) {
      this._error.textContent = (err && err.message) || String(err);
    } finally {
      this._busy = false;
      this._refresh();
    }
  }

  _send(command) {
    return this._call("send_command", { command: [command] });
  }

  _wake() {
    if (window.confirm("Wake the TV?")) this._call("turn_on", {});
  }

  _standby() {
    if (window.confirm("Put the TV into standby?")) this._call("turn_off", {});
  }
}

if (!customElements.get(TAG)) {
  customElements.define(TAG, PhilipsTitanosRemotePanel);
}
