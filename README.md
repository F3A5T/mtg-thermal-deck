# MTG Console

Thermal card printer for Magic: The Gathering, running on a Raspberry Pi Zero 2W with a Pimoroni Display HAT Mini. Navigate modes with physical buttons, print cards on an ESC/POS thermal printer, and control everything from a web UI on your phone or browser.

## Hardware

| Component | Notes |
|---|---|
| Raspberry Pi Zero 2W | |
| Pimoroni Display HAT Mini | 320×240 IPS LCD + 4 buttons (A/B/X/Y) |
| PiSugar Mini | Battery |
| Thermal printer | Any ESC/POS serial printer (58mm recommended) |

**Wiring (serial printer):**
- Printer TX → Pi RX (GPIO 15 / pin 10)
- Printer RX → Pi TX (GPIO 14 / pin 8)
- GND → GND
- Power printer from its own supply (not Pi 5V)

## Setup

```bash
# Copy the repo to the Pi (no git required on the Pi)
rsync -av --exclude='.git' --exclude='data/' mtg-console/ pi:/home/dev/mtg-console/

# On the Pi — first-time setup (enables SPI/UART, installs venv, installs systemd service)
bash scripts/setup.sh

sudo reboot
```

After reboot the service starts automatically.

### Download card database (recommended: run locally, then rsync)

The Pi Zero is slow at downloading thousands of images. Run `fetch_cards.py` on your
development machine, then rsync the `data/` folder over:

```bash
# On this machine — install deps if needed
pip install requests ijson

# Full card + token database (all types: creatures, instants, sorceries,
# enchantments, artifacts, planeswalkers, lands)
python scripts/fetch_cards.py

# Tokens only (faster)
python scripts/fetch_cards.py --tokens-only

# Quick test — 3 cards per CMC, no tokens
python scripts/fetch_cards.py --max-per-cmc 3 --no-tokens

# Rsync data to Pi after download
rsync -av data/ pi:/home/dev/mtg-console/data/

# Reload the running service so it picks up the new data
ssh pi "curl -s -X POST http://localhost:5000/api/reload"
```

To fetch on the Pi directly:

```bash
cd ~/mtg-console && source .venv/bin/activate
python scripts/fetch_cards.py
```

### WiFi hotspot setup

The Pi can act as a WiFi hotspot while staying connected to your router simultaneously (AP+STA mode). Run once on the Pi:

```bash
bash scripts/setup_hotspot.sh [SSID] [PASSWORD]
# defaults: SSID=mtg-console, PASSWORD=mtgprinter
```

This creates a virtual `uap0` interface alongside `wlan0`, installs a systemd service to recreate it on boot, creates the NetworkManager connection profile, and adds a passwordless sudoers rule for `nmcli`. After setup, the hotspot can be toggled on/off from the Info screen (X button) or the web UI System panel.

- `wlan0` → stays on your router (SSH and internet unaffected)
- `uap0` → hotspot at `10.42.0.1`, web UI at `http://10.42.0.1:5000`
- The AP and your router must be on the same WiFi channel

## Service management

The app runs as a systemd service and starts on every boot.

```bash
sudo systemctl status mtg-console    # check status
sudo journalctl -u mtg-console -f    # live logs
sudo systemctl restart mtg-console   # restart (e.g. after updating files)
sudo systemctl stop mtg-console      # stop
```

## Modes

Press **Y** to cycle through modes. **Hold Y** on any mode to show its help overlay. The display blanks and backlight turns off after **30 seconds** of inactivity to prevent burn-in; any button press wakes it (the wake press is swallowed).

Card Browser and Decklist are **web UI only** — they do not appear in the physical display rotation.

### Momir Basic

Pick a CMC and print a random creature at that cost. The card count shown is creatures only, regardless of how many non-creature cards are in the database.

| Button | Action |
|---|---|
| A | Increment CMC |
| B | Decrement CMC |
| X | Print a random creature at the current CMC |
| Y | Cycle to next mode |
| Hold Y | Help overlay |

### Token Printer

Scroll through every paper token sorted alphabetically, then by P/T. Switching to this mode automatically opens the letter filter.

| Button | Action |
|---|---|
| A | Next token |
| B | Previous token |
| X | Print selected token |
| Hold X | Enter letter-filter mode |
| Y | Cycle to next mode |
| Hold Y | Help overlay |

**Letter-filter mode** — jump straight to a letter of the alphabet:

| Button | Action |
|---|---|
| A | Next letter |
| B | Previous letter |
| X | Jump to first token under this letter |
| Hold X | Cancel, go back without jumping |

### Life Tracker

4-player life totals starting at 40. The display splits into four quadrants, one per player. The selected player is highlighted with a gold border.

| Button | Action |
|---|---|
| A | Select next player (cycles 1→2→3→4→1) |
| B | Selected player −1 life |
| X | Selected player +1 life |
| Hold B | Selected player −5 life (repeats) |
| Hold X | Selected player +5 life (repeats) |
| Hold A | Reset all players to 40 |
| Y | Cycle to next mode |
| Hold Y | Help overlay |

Life total turns red at 10 or below.

### Info

Shows WiFi IP (`wlan0`), hotspot IP (`10.42.0.1`, green when active), hostname, and uptime. X toggles the hotspot on/off; the button hint updates to show the current action (`X:HOT ON` or `X:HOT OFF`).

| Button | Action |
|---|---|
| X | Toggle WiFi hotspot on/off |
| Y | Cycle to next mode |
| Hold Y | Help overlay |

Requires `scripts/setup_hotspot.sh` to have been run once to create the connection profile.

## Web UI

Available at `http://<pi-ip>:5000` (or `http://10.42.0.1:5000` when hotspot is on) from any device on the network. The Info screen shows both IPs.

### Panels

- **Momir Basic** — CMC spinner, quick-select buttons 0–16, Print
- **Token Printer** — live search, A–Z letter-jump bar, Prev/Next, Print
- **Life Tracker** — 2×2 grid, per-player −5/−1/+1/+5 buttons, Reset All
- **System** — cycle mode, reload card database, hotspot toggle (ON/OFF button updates live)
- **Card Browser** — filter by CMC/colour/type, Random, Print; **Art** checkbox skips artwork when unchecked
- **Decklist** — paste a Moxfield or Archidekt URL, view matched cards grouped by category, Print individual cards or Print All mainboard+commanders; **Art** checkbox applies to all prints

### Art toggle

Every print action (Card Browser, Decklist per-card, Decklist Print All) has an **Art** checkbox. Uncheck it to print text only — faster and uses less paper. On the physical display, **Hold B** in Card Browser toggles art on/off (status shown on screen).

### Decklist

1. Paste a Moxfield (`moxfield.com/decks/...`) or Archidekt (`archidekt.com/decks/...`) URL
2. Click **Load** — the app fetches the decklist and resolves each card name against the local database
3. Cards show ✓ (found) or ✗ (not in local DB)
4. Print individual cards (all copies printed) or **Print All** to print the full mainboard + commanders
5. Progress bar shown during Print All

## Print format

Each printed card outputs:
1. **Art crop** — full-width artwork image (skipped if Art is off)
2. **Card name** — bold, centred
3. **Mana cost** — e.g. `{3}{G}{G}`
4. **Type line** — e.g. `Legendary Creature — Elf Warrior`
5. **Rules text** — word-wrapped at 42 characters
6. **Power / Toughness** — centred, bold (creatures only)

## Development without hardware

```bash
MOCK_PRINTER=true MOCK_DISPLAY=true python run.py
```

`MOCK_PRINTER=true` logs print jobs to console instead of the serial port.
`MOCK_DISPLAY=true` skips Display HAT initialisation (no GPIO needed).

## Configuration

All settings in [config.py](config.py) can be overridden with environment variables:

| Variable | Default | Description |
|---|---|---|
| `PRINTER_PORT` | `/dev/serial0` | Serial device |
| `PRINTER_BAUDRATE` | `9600` | Baud rate |
| `PRINTER_PROFILE` | `POS-5890` | escpos printer profile |
| `PRINTER_WIDTH_PX` | `384` | Printable width in pixels (384=58mm, 576=80mm) |
| `DISPLAY_BRIGHTNESS` | `0.8` | Backlight brightness (0.0–1.0) |
| `PORT` | `5000` | Flask web port |
| `MOCK_PRINTER` | `false` | Dry-run printer |
| `MOCK_DISPLAY` | `false` | Skip Display HAT init |

Screensaver timeout is set in [app/display_hat.py](app/display_hat.py) as `SCREENSAVER_TIMEOUT` (default 30 seconds).

## Adding a new mode

1. Create `app/modes/your_mode.py` subclassing `BaseMode`
2. Implement `name`, `render()`, `handle_button()`, and `get_status()`
3. Optionally override `on_activate()` to reset state when the mode is switched to
4. Set `display_in_rotation = False` if the mode should only be accessible via the web UI
5. Register an instance in the `modes = [...]` list in `app/__init__.py`
