import logging
import threading
import time

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
    from app.state import AppState

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

    # Register modes here. Add more modes to this list in the future
    # (e.g. TokenMode, DecklistMode) and they'll appear in Y-button cycling.
    modes = [
        MomirMode(card_manager, printer),
        # TokenMode(card_manager, printer),     # future
        # DecklistMode(card_manager, printer),  # future
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
    display.start()

    def _display_loop():
        while True:
            img, draw = display.blank_canvas()
            state.current_mode.render(draw, display.WIDTH, display.HEIGHT)
            display.update(img)
            time.sleep(0.05)  # ~20 fps

    threading.Thread(target=_display_loop, daemon=True, name="display-render").start()

    logger.info(
        "MTG Console started — mode: %s | printer mock=%s | display mock=%s",
        state.current_mode.name,
        config.MOCK_PRINTER,
        config.MOCK_DISPLAY,
    )
    return app
