import logging

from flask import Flask

logger = logging.getLogger(__name__)


def create_app(config=None) -> Flask:
    from config import Config

    if config is None:
        config = Config()

    app = Flask(__name__)
    app.secret_key = config.SECRET_KEY

    # ----------------------------------------------------------------
    # Component initialisation
    # ----------------------------------------------------------------

    from app.card_manager import CardManager
    from app.printer import Printer
    from app.display_hat import DisplayHat
    from app.modes.momir import MomirMode
    from app.modes.token import TokenMode
    from app.modes.browser import CardBrowserMode
    from app.modes.info import InfoMode
    from app.modes.life import LifeMode
    from app.state import AppState
    import os

    card_manager = CardManager(config.CARDS_DIR)

    printer = Printer(
        port=config.PRINTER_PORT,
        baudrate=config.PRINTER_BAUDRATE,
        profile=config.PRINTER_PROFILE,
        width_px=config.PRINTER_WIDTH_PX,
        mock=config.MOCK_PRINTER,
    )

    display = DisplayHat(
        mock=config.MOCK_DISPLAY,
        brightness=config.DISPLAY_BRIGHTNESS,
    )

    tokens_path = os.path.join(config.CARDS_DIR, "tokens.json")

    # Y-button cycles through modes in order.
    # Add new modes here as they are implemented.
    modes = [
        MomirMode(card_manager, printer),
        TokenMode(tokens_path, printer),
        CardBrowserMode(card_manager, printer),
        LifeMode(),
        InfoMode(),
    ]
    state = AppState(modes)

    # Attach to app so blueprints can access via current_app
    app.card_manager = card_manager  # type: ignore[attr-defined]
    app.printer = printer  # type: ignore[attr-defined]
    app.display = display  # type: ignore[attr-defined]
    app.app_state = state  # type: ignore[attr-defined]

    # ----------------------------------------------------------------
    # Routes
    # ----------------------------------------------------------------

    from app.routes import bp
    app.register_blueprint(bp)

    # ----------------------------------------------------------------
    # Background threads
    # ----------------------------------------------------------------

    def _on_button(button: str):
        if button == "Y":
            state.next_mode()
        else:
            state.current_mode.handle_button(button)

    display.set_button_callback(_on_button)
    # Display loop is run by the caller (run.py) on the main thread.
    # ST7789 SPI requires display() to be called from the thread that opened the device.

    logger.info(
        "MTG Console started — mode: %s | printer mock=%s | display mock=%s",
        state.current_mode.name,
        config.MOCK_PRINTER,
        config.MOCK_DISPLAY,
    )
    return app
