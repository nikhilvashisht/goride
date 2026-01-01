import logging
from pathlib import Path


def configure_logging(log_file: str | None = None, level: int = logging.DEBUG):
    """Configure simple file logging for the application.

    Writes logs to `app/logs/goride.log` by default.
    """
    base = Path(__file__).resolve().parent
    logs_dir = base / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    if log_file is None:
        log_file = logs_dir / "goride.log"
    else:
        log_file = Path(log_file)
        if not log_file.is_absolute():
            log_file = logs_dir / log_file

    # Basic file configuration
    logging.basicConfig(
        filename=str(log_file),
        level=level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )


def get_logger(name: str):
    return logging.getLogger(name)
