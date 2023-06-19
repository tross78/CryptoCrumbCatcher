import logging
from logging.handlers import RotatingFileHandler

# Set up a logger
logger = logging.getLogger("my_logger")
logger.setLevel(logging.INFO)

# Set up a formatter
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

# Set up a rotating file handler
handler = RotatingFileHandler("logs/app.log", maxBytes=1048576, backupCount=5)
handler.setFormatter(formatter)  # Apply the formatter to the handler
logger.addHandler(handler)
