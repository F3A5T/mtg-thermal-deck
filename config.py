import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


class Config:
    # --- Thermal Printer ---
    PRINTER_PORT = os.getenv("PRINTER_PORT", "/dev/serial0")
    PRINTER_BAUDRATE = int(os.getenv("PRINTER_BAUDRATE", "9600"))
    # escpos printer profile — "POS-5890" works for most 58mm printers
    PRINTER_PROFILE = os.getenv("PRINTER_PROFILE", "POS-5890")
    # Printable width in pixels (384 = 58mm paper, 576 = 80mm paper)
    PRINTER_WIDTH_PX = int(os.getenv("PRINTER_WIDTH_PX", "384"))

    # --- Data ---
    DATA_DIR = os.getenv("DATA_DIR", os.path.join(BASE_DIR, "data"))
    CARDS_DIR = os.path.join(DATA_DIR, "cards")

    # --- Flask ---
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-key-change-me")
    DEBUG = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", "5000"))

    # --- Display ---
    DISPLAY_BRIGHTNESS = float(os.getenv("DISPLAY_BRIGHTNESS", "0.8"))

    # --- Mock modes (set to "true" for dev without hardware) ---
    MOCK_PRINTER = os.getenv("MOCK_PRINTER", "false").lower() == "true"
    MOCK_DISPLAY = os.getenv("MOCK_DISPLAY", "false").lower() == "true"
