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

After reboot the service starts automatically. Fetch card data before first use:

```bash
cd ~/mtg-console
source .venv/bin/activate

# Full card + token database (downloads artwork — takes a while on Pi Zero)
python scripts/fetch_cards.py

# Tokens only (much faster)
python scripts/fetch_cards.py --tokens-only

# Quick test — 3 cards per CMC, no tokens
python scripts/fetch_cards.py --max-per-cmc 3 --no-tokens
```

## Service management

The app runs as a systemd service and starts on every boot.

```bash
sudo systemctl status mtg-console    # check status
sudo journalctl -u mtg-console -f    # live logs
sudo systemctl restart mtg-console   # restart (e.g. after updating files)
sudo systemctl stop mtg-console      # stop
```

## Modes

Press **Y** to cycle through modes. **Hold Y** on any mode to show its help overlay.

### Momir Basic

Pick a CMC and print a random creature at that cost.

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

Shows the Pi's IP address, hostname, and uptime. Useful for finding the web UI address after a fresh boot.

| Button | Action |
|---|---|
| Y | Cycle to next mode |
| Hold Y | Help overlay |

## Web UI

Available at `http://<pi-ip>:5000` from any device on the network. The **Info** screen on the display shows the IP address.

- **Momir Basic** — CMC spinner, quick-select buttons 0–16, Print
- **Token Printer** — live search, A–Z letter-jump bar, Prev/Next, Print
- **Life Tracker** — 2×2 grid, per-player −5/−1/+1/+5 buttons, Reset All
- **System** — cycle mode, reload card database

## Print format

Each printed card has:
1. **Art crop** — full-width artwork image
2. **Card name** — bold, centred
3. **Mana cost** — text (e.g. `{3}{G}{G}`)
4. **Type line** — (e.g. `Legendary Creature — Elf Warrior`)
5. **Rules text** — word-wrapped
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

## Adding a new mode

1. Create `app/modes/your_mode.py` subclassing `BaseMode`
2. Implement `name`, `render()`, `handle_button()`, and `get_status()`
3. Optionally override `on_activate()` to reset state when the mode is switched to
4. Register an instance in the `modes = [...]` list in `app/__init__.py`

Planned future modes:
- **Decklist mode** — import a Moxfield deck URL and print cards from it
