"""Plate editor widget: view a plate layout and edit wells by selection."""

from pathlib import Path
from typing import Callable, Optional

import anywidget
import pandas as pd
import traitlets

from mihcsme_py import plate_ops


class PlateViewer(anywidget.AnyWidget):
    """Interactive 96/384-well plate editor.

    Python owns the data: call :meth:`set_data` with the well dataframe and
    register :meth:`on_change` to receive the edited dataframe.
    """

    _esm = Path(__file__).with_name("plate_viewer.js")

    plates = traitlets.List(traitlets.Unicode()).tag(sync=True)
    plate_format = traitlets.Unicode("96").tag(sync=True)
    fields = traitlets.List(traitlets.Unicode()).tag(sync=True)
    color_field = traitlets.Unicode("").tag(sync=True)
    values = traitlets.Dict().tag(sync=True)
    detail = traitlets.Dict().tag(sync=True)
    current_plate = traitlets.Unicode("").tag(sync=True)
    selection = traitlets.List(traitlets.Unicode()).tag(sync=True)
    edit_request = traitlets.Dict().tag(sync=True)
    can_undo = traitlets.Bool(False).tag(sync=True)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._df = pd.DataFrame()
        self._previous: Optional[pd.DataFrame] = None
        self._callback: Optional[Callable[[pd.DataFrame], None]] = None
        self.observe(self._on_color_field, names=["color_field"])
        self.observe(self._on_current_plate, names=["current_plate"])
        self.observe(self._on_edit_request, names=["edit_request"])

    @property
    def data(self) -> pd.DataFrame:
        """The current well dataframe."""
        return self._df

    def on_change(self, callback: Callable[[pd.DataFrame], None]) -> None:
        """Register a callback that receives the dataframe after each edit/undo."""
        self._callback = callback

    def set_data(self, df: pd.DataFrame) -> None:
        """Show ``df``. A different dataframe object clears the undo step."""
        if df is not self._df:
            self._previous = None
            self.can_undo = False
        self._df = df
        wells = df["Well"].tolist() if "Well" in df.columns else []
        self.plate_format = plate_ops.detect_format(wells)
        fields = [c for c in df.columns if c not in ("Plate", "Well")]
        if self.color_field not in fields:
            self.color_field = fields[0] if fields else ""
        self._push_values()
        if self.current_plate not in self.plates:
            self.current_plate = self.plates[0] if self.plates else ""
        self._push_detail()

    def _push_values(self) -> None:
        payload = plate_ops.widget_payload(self._df, self.color_field or None, self.plate_format)
        self.fields = payload["fields"]
        self.values = payload["values"]
        self.plates = payload["plates"]

    def _push_detail(self) -> None:
        self.detail = plate_ops.detail_payload(self._df, self.current_plate)

    def _on_color_field(self, _change) -> None:
        self._push_values()

    def _on_current_plate(self, _change) -> None:
        self.selection = []
        self._push_detail()

    def _on_edit_request(self, change) -> None:
        request = change["new"] or {}
        action = request.get("action")
        if action == "undo":
            if self._previous is None:
                return
            new_df, self._previous = self._previous, None
        elif action == "set":
            new_df = plate_ops.apply_edit(
                self._df,
                request["plate"],
                request.get("wells", []),
                request["field"],
                request.get("value"),
            )
            self._previous = self._df
        else:
            return
        self._df = new_df
        self.can_undo = self._previous is not None
        self._push_values()
        self._push_detail()
        if self._callback is not None:
            self._callback(new_df)
