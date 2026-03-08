#!/usr/bin/env python3
import logging
import threading
import time

from config import Config
from app import create_app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)

logger = logging.getLogger(__name__)
config = Config()
app = create_app(config)

if __name__ == "__main__":
    # Run Flask in a background thread so the display loop can own the main thread.
    # ST7789 SPI writes must come from the thread that initialised the driver.
    flask_thread = threading.Thread(
        target=lambda: app.run(
            host=config.HOST,
            port=config.PORT,
            debug=False,
            use_reloader=False,
        ),
        daemon=True,
        name="flask",
    )
    flask_thread.start()

    # Display loop runs on the main thread
    display = app.display      # type: ignore[attr-defined]
    state = app.app_state      # type: ignore[attr-defined]

    logger.info("Display loop starting on main thread")
    try:
        while True:
            try:
                display.poll_buttons()
                img, draw = display.blank_canvas()
                state.current_mode.render(draw, display.WIDTH, display.HEIGHT)
                display.update(img)
            except Exception:
                logger.exception("Display render error")
            time.sleep(0.1)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        display.shutdown()
