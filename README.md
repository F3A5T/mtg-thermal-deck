# mtg-thermal-deck

A small device to help with MTG related tasks. Starting with Momir Vig Basic.

---

# MTG Console

Momir Basic thermal card printer for Raspberry Pi Zero 2W with Pimoroni Display HAT Mini.

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
git clone <this-repo> ~/mtg-console
cd ~/mtg-console
bash scripts/setup.sh
sudo reboot
```

After reboot, fetch card data (downloads ~10 GB of images — takes a while):

```bash
cd ~/mtg-console
source .venv/bin/activate
python scripts/fetch_cards.py
```

For a quick test with just a handful of cards:

```bash
python scripts/fetch_cards.py --max-per-cmc 3
```

Start the app:

```bash
python run.py
```

Or install the systemd service so it starts on boot:

```bash
sudo cp scripts/mtg-console.service /etc/systemd/system/
sudo systemctl enable --now mtg-console
```

## Using the console

The **Display HAT Mini** shows the current mode UI. In **Momir Basic** mode:

| Button | Action |
|---|---|
| A | Increment CMC |
| B | Decrement CMC |
| X | Print a random creature at the current CMC |
| Y | Cycle to next mode |

The **web UI** is also available at `http://<pi-ip>:5000` from any device on the network. It mirrors all button functions and lets you jump directly to a CMC.

## Print format

Each printed card has:
1. **Art crop** — full-width artwork image
2. **Card name** — bold, double-width
3. **Mana cost** — text (e.g. `{3}{G}{G}`)
4. **Type line** — (e.g. `Legendary Creature — Elf Warrior`)
5. **Power / Toughness** — centred, bold

## Development without hardware

Set environment variables to run mock hardware on any machine:

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

## Adding future modes

1. Create `app/modes/your_mode.py` subclassing `BaseMode`
2. Implement `name`, `render()`, `handle_button()`, and `get_status()`
3. Register an instance in the `modes = [...]` list in `app/__init__.py`

Planned future modes:
- **Token mode** — print specific token cards by name
- **Decklist mode** — import a Moxfield deck URL and print cards from it

