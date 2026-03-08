#!/usr/bin/env python3
import logging
from config import Config
from app import create_app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)

config = Config()
app = create_app(config)

if __name__ == "__main__":
    app.run(
        host=config.HOST,
        port=config.PORT,
        debug=config.DEBUG,
        use_reloader=False,  # reloader conflicts with background GPIO/display threads
    )
