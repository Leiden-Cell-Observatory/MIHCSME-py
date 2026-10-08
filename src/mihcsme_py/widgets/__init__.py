"""Interactive widgets for the MIHCSME marimo app (requires the ``app`` extra)."""

try:
    from mihcsme_py.widgets.plate_viewer import PlateViewer
except ImportError as e:  # pragma: no cover - depends on optional deps
    raise ImportError(
        "The plate editor needs the optional 'app' dependencies: "
        "pip install 'mihcsme-py[app]'"
    ) from e

__all__ = ["PlateViewer"]
