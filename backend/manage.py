#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys
import warnings

# drf_yasg currently imports pkg_resources, which emits a global deprecation
# warning on startup. Suppress this one noisy warning to keep local CLI output
# focused on actionable errors.
warnings.filterwarnings(
    "ignore",
    message=r"pkg_resources is deprecated as an API.*",
    category=UserWarning,
    module=r"drf_yasg",
)


def _extract_settings_module(argv: list[str]) -> str:
    """Resolve the Django settings module from CLI args/environment."""

    for index, arg in enumerate(argv):
        if arg == "--settings" and index + 1 < len(argv):
            return argv[index + 1]
        if arg.startswith("--settings="):
            return arg.split("=", 1)[1]

    return os.environ.get("DJANGO_SETTINGS_MODULE", "app.settings")


def _should_run_local_auto_migrate(argv: list[str], settings_module: str) -> bool:
    """Only auto-migrate in localhost debug profiles when running the server."""

    if len(argv) < 2 or argv[1] not in {"runserver", "runserver_plus"}:
        return False

    if not settings_module.startswith("app.localhost_debug_"):
        return False

    flag = os.getenv("LOCALHOST_AUTO_MIGRATE", "1").strip().lower()
    return flag in {"1", "true", "yes", "on"}


def main():
    """Run administrative tasks."""
    settings_module = _extract_settings_module(sys.argv)
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", settings_module)

    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc

    if _should_run_local_auto_migrate(sys.argv, settings_module):
        migrate_argv = [
            sys.argv[0],
            "migrate",
            "--noinput",
            f"--settings={settings_module}",
        ]
        execute_from_command_line(migrate_argv)

    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
