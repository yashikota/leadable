from logging import StreamHandler, getLogger

logger = getLogger(__name__)
logger.addHandler(StreamHandler())
logger.setLevel("INFO")
