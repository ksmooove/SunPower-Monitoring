# Prior art: PVS5/PVS6 local interoperability

Research summary for reuse decisions. Licenses and activity as of 2026-07. **Do not copy code blindly; respect licenses and attribution.**

Sanitize: this file contains no site serials, passwords, or private captures.

---

## SunStrong-Management/pypvs

| Field | Detail |
|-------|--------|
| Repository | https://github.com/SunStrong-Management/pypvs |
| License | MIT |
| Last meaningful activity | Active docs and PyPI package; community notes some open issues go quiet |
| Supported firmware | PVS6 min ~2025.06 build **61839+**; PVS5 newer builds documented separately |
| Data-access method | Authenticated **varserver FCGI** (`/auth`, `/vars`); legacy `dl_cgi` documented |
| Per-panel data | Yes — inverter data via varserver match queries |
| Polling behavior | Docs warn against querying faster than every few seconds; prefer cached queries |
| Known hardware risks | CPU load if polled too fast (especially with ESS); general embedded fragility |
| Useful concepts | Auth cookie flow, cache ids, livedata/meter/inverter variable shapes, public variable CSVs |
| Reuse appropriate? | **Yes — concepts, docs, and optionally the MIT library as a dependency or reference** |
| Decision | Prefer a thin project-owned client with hard rate limits; may wrap or vendor ideas from pypvs with attribution |

---

## SunStrong-Management/pvs-hass

| Field | Detail |
|-------|--------|
| Repository | https://github.com/SunStrong-Management/pvs-hass |
| License | MIT |
| Last meaningful activity | 2026 (HA integration via HACS) |
| Supported firmware | Via pypvs / varserver era |
| Data-access method | Home Assistant + pypvs → varserver |
| Per-panel data | Yes (as HA entities) |
| Polling behavior | HA integration polling patterns |
| Known hardware risks | Same as underlying API usage |
| Useful concepts | Entity mapping, setup UX |
| Reuse appropriate? | **Patterns only** — we are not HA-centric |
| Decision | Reject as core collector; optional later integration |

---

## smcneece/ha-esunpower

| Field | Detail |
|-------|--------|
| Repository | https://github.com/smcneece/ha-esunpower |
| License | Apache-2.0 |
| Last meaningful activity | Very active (2026); discussions on polling and flash |
| Supported firmware | PVS6 build **61840+** (varserver); PVS5 newer builds |
| Data-access method | Direct varserver client (moved away from depending solely on pypvs); optional WebSocket live data |
| Per-panel data | Yes; inverter health features |
| Polling behavior | **300 s recommended**; notes that faster polling does not freshen inverter data; WebSocket for livedata when enabled |
| Known hardware risks | Fast polling linked by community to reboots/instability; flash wear monitoring sensors |
| Useful concepts | Hold-last-value, outlier protection, flash diagnostics, WS live path |
| Reuse appropriate? | **Yes for safety/UX ideas**; Apache-2.0 allows adaptation with attribution; do not fork entire HA component into this repo as the core |
| Decision | Adapt safety guidance; optional HA path later |

---

## krbaker/hass-sunpower

| Field | Detail |
|-------|--------|
| Repository | https://github.com/krbaker/hass-sunpower |
| License | Apache-2.0 |
| Last meaningful activity | Maintained historically; 2025 pushes; less ideal for new firmware alone |
| Supported firmware | Older `dl_cgi` / installer-interface workflows |
| Data-access method | Installer Ethernet + `dl_cgi` device list (slow) |
| Per-panel data | Yes via device list |
| Polling behavior | Can be heavy; device list timeouts common |
| Known hardware risks | **Installer NIC runs DHCP — never bridge straight into home LAN**; eMMC wear reports with heavy `dl_cgi` use historically |
| Useful concepts | NAT/isolated routing to installer port; retry around slow device list |
| Reuse appropriate? | Historical reference; **not primary** for build 61846 on Wi-Fi LAN |
| Decision | Reject as primary path; keep network-isolation warnings |

---

## koleson — PVS6 Notes (gist)

| Field | Detail |
|-------|--------|
| Repository | https://gist.github.com/koleson/5c719620039e0282976a8263c068e85c |
| License | Gist / informal documentation (verify before copying code snippets) |
| Last meaningful activity | Updated into 2026 |
| Supported firmware | Notes span pre- and post-bankruptcy eras |
| Data-access method | Documents `dl_cgi`, MQTT/rooting research, architecture |
| Per-panel data | Discussed via local APIs |
| Polling behavior | Warns about flash wear with long-term `dl_cgi` use |
| Known hardware risks | **eMMC write exhaustion**; partition fill; rooting/control paths are high risk |
| Useful concepts | Risk catalog, system internals orientation |
| Reuse appropriate? | **Risk documentation only** — do not adopt rooting/MQTT control |
| Decision | Cite for safety; reject invasive techniques |

---

## kpfleming/esphome-sunpower

| Field | Detail |
|-------|--------|
| Repository | https://github.com/kpfleming/esphome-sunpower |
| License | GPL-3.0 |
| Last meaningful activity | Archived / limited maintenance after SunPower bankruptcy |
| Supported firmware | Legacy PVS data collection via ESPHome |
| Data-access method | ESP32 intermediary + ESPHome |
| Per-panel data | Configurable sensors |
| Polling behavior | ESPHome-driven |
| Known hardware risks | Extra hardware hop; project archived |
| Useful concepts | Sensor naming, collection notes |
| Reuse appropriate? | **No as core** (GPL copyleft + archived + wrong shape) |
| Decision | Reject |

---

## strawtype/dash-sunpower

| Field | Detail |
|-------|--------|
| Repository | https://github.com/strawtype/dash-sunpower |
| License | Apache-2.0 |
| Last meaningful activity | 2025 |
| Supported firmware | Assumes HA + PVS6 data already collected |
| Data-access method | Dashboard on top of HA/Influx |
| Per-panel data | Visual panel layout / heatmap UX |
| Polling behavior | N/A (presentation layer) |
| Known hardware risks | None directly |
| Useful concepts | Editable panel layout, portrait mobile dashboard |
| Reuse appropriate? | **UX inspiration** for our PWA heatmap |
| Decision | Adapt layout ideas; do not depend on HA |

---

## Other (noted)

- **jschwerdtfeger/pvs6-liberation** — Local-first docs/tooling around official auth and endpoints; useful cross-check for endpoint map; review license before copying.
- **timkatz/pvswatch** — Small proxy/dashboard; reinforces **300 s** refresh and long timeouts for slow calls.

## Summary decision for this project

| Approach | Verdict |
|----------|---------|
| Official varserver + owner auth (build 61846) | **Primary** |
| Continuous legacy `dl_cgi` device-list polling | Avoid as steady-state |
| HA as required runtime | Reject |
| ESPHome bridge | Reject |
| Copying HA integration wholesale | Reject — extract ideas, attribute, implement behind our adapters |
