#!/usr/bin/env python3
"""Interactively label the blinded Chapter-4 flight-phase candidate windows.

Drag a time interval in the altitude panel, then press ``t`` (transition), ``s``
(search), or ``c`` (climb).  Use the arrow keys for candidates and ``u`` to undo.  The
CSV is saved after every edit, so closing the window never loses completed labels.
"""

from __future__ import annotations

import argparse
import sys
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

if TYPE_CHECKING:
    from matplotlib.widgets import SpanSelector

ROOT = Path(__file__).resolve().parents[1]
_SRC = str(ROOT / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from soaring.analysis.segmentation.labels import (  # noqa: E402
    ANNOTATION_COLUMNS,
    validate_annotations,
)

PALETTE = {"transition": "#3477A8", "search": "#B5482A", "climb": "#4E8A5B"}


class AnnotationApp:
    """Small Matplotlib span-labeler that writes the canonical interval schema."""

    def __init__(
        self,
        candidates: pd.DataFrame,
        windows: pd.DataFrame,
        output: Path,
        annotator: str,
    ) -> None:
        """Load candidate state and construct the interactive figure widgets."""
        import matplotlib.pyplot as plt
        from matplotlib.widgets import Button

        self.candidates = candidates
        self.windows = windows.reset_index(drop=True)
        self.output = output
        self.annotator = annotator
        self.index = 0
        self.selection: tuple[float, float] | None = None
        self.annotations = self._load_annotations()
        self.figure, axes = plt.subplots(3, 2, figsize=(13.5, 8.7))
        self.axes = axes.ravel()
        self.figure.subplots_adjust(bottom=0.13, hspace=0.42, wspace=0.30)
        button_specs = [
            ("Transition [t]", "transition", 0.10),
            ("Search [s]", "search", 0.25),
            ("Climb [c]", "climb", 0.40),
            ("Undo [u]", "undo", 0.55),
            ("Previous [←]", "previous", 0.68),
            ("Next [→]", "next", 0.81),
        ]
        self.buttons = []
        for label, action, left in button_specs:
            button = Button(self.figure.add_axes((left, 0.035, 0.12, 0.045)), label)
            button.on_clicked(partial(self._button_action, action))
            self.buttons.append(button)
        self.status = self.figure.text(0.10, 0.095, "", fontsize=9)
        self.span: SpanSelector | None = None
        self.figure.canvas.mpl_connect("key_press_event", self._key)
        self._draw()

    def _load_annotations(self) -> pd.DataFrame:
        if not self.output.is_file() or self.output.stat().st_size == 0:
            return pd.DataFrame(columns=ANNOTATION_COLUMNS)
        frame = pd.read_csv(self.output)
        if frame.empty:
            return pd.DataFrame(columns=ANNOTATION_COLUMNS)
        return validate_annotations(frame)

    def _current(self) -> tuple[pd.Series, pd.DataFrame]:
        row = self.windows.iloc[self.index]
        points = self.candidates.loc[
            self.candidates["candidate_id"] == row.candidate_id
        ].sort_values("t", kind="stable")
        return row, points

    def _matching_annotations(self, row: pd.Series) -> pd.DataFrame:
        if self.annotations.empty:
            return self.annotations
        return self.annotations.loc[
            (self.annotations["source"].astype(str) == str(row.source))
            & (self.annotations["flight_id"].astype(str) == str(row.flight_id))
            & (self.annotations["segment_id"] == int(row.segment_id))
            & (self.annotations["split"] == row["split"])
        ]

    def _draw(self) -> None:
        row, points = self._current()
        for axis in self.axes:
            axis.clear()
        time = points["t"]
        self.axes[0].plot(points["E"], points["N"], color="#303030", linewidth=0.9)
        self.axes[0].scatter(
            points["E"].iloc[0], points["N"].iloc[0], color="#4E8A5B", s=25
        )
        self.axes[0].set(
            xlabel="east (m)", ylabel="north (m)", aspect="equal", title="Plan view"
        )
        self.axes[1].plot(time, points["z"], color="#303030")
        self.axes[1].set(
            xlabel="processed time t (s)",
            ylabel="altitude (m)",
            title="Drag the interval here",
        )
        self.axes[2].plot(time, points["mean_v_z"], color="#4E8A5B")
        self.axes[2].axhline(0.0, color="black", linewidth=0.6)
        self.axes[2].set(
            xlabel="t (s)", ylabel=r"$\bar v_z$ (m/s)", title="Vertical speed"
        )
        self.axes[3].plot(time, points["mean_v_h"], color="#3477A8")
        self.axes[3].set(
            xlabel="t (s)", ylabel=r"$\bar v_h$ (m/s)", title="Horizontal speed"
        )
        self.axes[4].plot(
            time, np.degrees(points["mean_abs_turn_rate"]), color="#B5482A"
        )
        self.axes[4].set(
            xlabel="t (s)",
            ylabel="absolute turn rate (deg/s)",
            title="Turning intensity",
        )
        self.axes[5].plot(time, points["turn_coherence"], color="#4D4D4D")
        self.axes[5].set(
            xlabel="t (s)",
            ylabel=r"$C_\omega$",
            ylim=(-0.03, 1.03),
            title="Turn coherence",
        )
        labels = self._matching_annotations(row)
        for label in labels.itertuples(index=False):
            for axis in self.axes[1:]:
                axis.axvspan(
                    label.t_start, label.t_end, color=PALETTE[label.state], alpha=0.22
                )
        self.selection = None
        self.figure.suptitle(
            f"{self.index + 1}/{len(self.windows)} — {row.candidate_id} — "
            f"{row.discipline} / {row['split']} — flight {row.flight_id}, "
            f"segment {int(row.segment_id)} — [{row.window_start:.0f}, "
            f"{row.window_end:.0f}) s"
        )
        self.status.set_text(
            f"Saved intervals for this candidate: {len(labels)}. "
            "Drag in altitude, then press t/s/c; leave genuinely ambiguous "
            "regions blank."
        )
        # ``Axes.clear`` removes the selector's patch. Recreate the selector after
        # every candidate/save redraw so interval two works exactly like interval one.
        if self.span is not None:
            self.span.disconnect_events()
        from matplotlib.widgets import SpanSelector

        self.span = SpanSelector(
            self.axes[1],
            self._select,
            "horizontal",
            useblit=True,
            props={"facecolor": "#777777", "alpha": 0.25},
            interactive=True,
            drag_from_anywhere=True,
        )
        self.figure.canvas.draw_idle()

    def _select(self, minimum: float, maximum: float) -> None:
        row, _ = self._current()
        start = max(float(row.window_start), 10.0 * round(min(minimum, maximum) / 10.0))
        end = min(float(row.window_end), 10.0 * round(max(minimum, maximum) / 10.0))
        self.selection = (start, end) if end > start else None
        self.status.set_text(
            f"Selected [{start:.0f}, {end:.0f}) s — press t, s, or c."
            if self.selection
            else "Selection is shorter than one 10-s decision interval."
        )
        self.figure.canvas.draw_idle()

    def _save(self) -> None:
        checked = (
            validate_annotations(self.annotations)
            if not self.annotations.empty
            else self.annotations
        )
        checked.to_csv(self.output, index=False, columns=ANNOTATION_COLUMNS)

    def _add(self, state: str) -> None:
        if self.selection is None:
            self.status.set_text("Select an interval in the altitude panel first.")
            self.figure.canvas.draw_idle()
            return
        row, _ = self._current()
        start, end = self.selection
        existing = self._matching_annotations(row)
        overlap = (existing["t_start"] < end) & (existing["t_end"] > start)
        if overlap.any():
            self.status.set_text(
                "That interval overlaps an existing label; undo it first."
            )
            self.figure.canvas.draw_idle()
            return
        new = pd.DataFrame(
            [
                {
                    "source": row.source,
                    "flight_id": str(row.flight_id),
                    "segment_id": int(row.segment_id),
                    "t_start": start,
                    "t_end": end,
                    "state": state,
                    "split": row["split"],
                    "annotator": self.annotator,
                }
            ]
        )
        self.annotations = pd.concat([self.annotations, new], ignore_index=True)
        self.annotations = self.annotations.sort_values(
            ["source", "flight_id", "segment_id", "t_start"]
        ).reset_index(drop=True)
        self._save()
        self._draw()

    def _undo(self) -> None:
        row, _ = self._current()
        matching = self._matching_annotations(row)
        if matching.empty:
            return
        self.annotations = self.annotations.drop(matching.index[-1]).reset_index(
            drop=True
        )
        self._save()
        self._draw()

    def _action(self, action: str) -> None:
        if action in PALETTE:
            self._add(action)
        elif action == "undo":
            self._undo()
        elif action == "previous":
            self.index = (self.index - 1) % len(self.windows)
            self._draw()
        elif action == "next":
            self.index = (self.index + 1) % len(self.windows)
            self._draw()

    def _button_action(self, action: str, _event: object) -> None:
        """Adapt a Matplotlib button callback to the action dispatcher."""
        self._action(action)

    def _key(self, event) -> None:
        actions = {
            "t": "transition",
            "s": "search",
            "c": "climb",
            "u": "undo",
            "left": "previous",
            "right": "next",
        }
        if event.key in actions:
            self._action(actions[event.key])

    def show(self) -> None:
        """Block in the GUI event loop until the user closes the labeler."""
        import matplotlib.pyplot as plt

        plt.show()


def main(argv: list[str] | None = None) -> int:
    """Open a prepared pack and persist manual interval labels."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--pack-dir",
        type=Path,
        default=ROOT / "annotations" / "phase_labeling",
    )
    parser.add_argument("--annotator", required=True)
    args = parser.parse_args(argv)
    app = AnnotationApp(
        pd.read_parquet(args.pack_dir / "annotation_candidates.parquet"),
        pd.read_csv(args.pack_dir / "annotation_windows.csv"),
        args.pack_dir / "phase_annotations.csv",
        args.annotator,
    )
    app.show()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
