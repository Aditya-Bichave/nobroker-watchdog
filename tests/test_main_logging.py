import logging
import sys


def test_import_main_does_not_configure_logging():
    root = logging.getLogger()
    # Remove existing handlers to detect unintended configuration
    for h in list(root.handlers):
        root.removeHandler(h)
    root.setLevel(logging.WARNING)
    handlers_before = list(root.handlers)
    level_before = root.level

    if "nobroker_watchdog.main" in sys.modules:
        del sys.modules["nobroker_watchdog.main"]
    import nobroker_watchdog.main  # noqa: F401

    assert list(root.handlers) == handlers_before
    assert root.level == level_before
