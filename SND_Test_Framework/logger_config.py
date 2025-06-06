import logging
import os

def setup_logging(log_file: str = "testExecOutput.log", level: int = logging.INFO):
    '''
    Configures the root logger to write to both console and a single log file.
    - log_file: path to the global testExecOutput.log.
    - level: default log level (INFO).
    '''
    # Ensure the directory exists
    log_dir = os.path.dirname(log_file) or "."
    os.makedirs(log_dir, exist_ok=True)

    # Create a root logger
    logger = logging.getLogger()
    logger.setLevel(level)
    # Avoid duplicate handlers if re-called
    if logger.hasHandlers():
        logger.handlers.clear()

    # File handler
    fh = logging.FileHandler(log_file)
    fh.setLevel(level)
    file_formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(module)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )
    fh.setFormatter(file_formatter)
    logger.addHandler(fh)

    # Console handler
    ch = logging.StreamHandler()
    ch.setLevel(level)
    console_formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S"
    )
    ch.setFormatter(console_formatter)
    logger.addHandler(ch)

    return logger
