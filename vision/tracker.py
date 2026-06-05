"""Lightweight centroid-based ID tracker for produce detections.

Operates in board-frame millimetres (from `detection["board_xy_mm"]`), so the
match radius is in real-world units and stays stable when fruits or the
camera shake a little. Greedy nearest-neighbour matching, label-locked
(an "orange" never merges with an "apple"). No external deps beyond stdlib.

Typical use inside the live loop:

    tracker = FruitTracker()
    for frame in stream:
        events = tracker.update(frame.detections, frame.index, time.time())
        if frame.index % 5 == 0:
            tracker.write_snapshot("outputs/latest_tracks.json")
        for ev in events:
            tracker.append_event("outputs/track_events.jsonl", ev)

Each call to `update` mutates the detection dicts in place to add
`detection["track_id"]`, and returns a list of `(new | lost)` events that
happened in this frame.
"""

from __future__ import annotations

import json
import math
import os
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable, List, Mapping, MutableMapping, Optional


@dataclass
class Track:
    track_id: int
    label: str
    x_mm: float
    y_mm: float
    quality_grade: Optional[str]
    first_frame: int
    last_frame: int
    last_seen_ts: float
    hits: int = 1

    def to_dict(self, current_frame: Optional[int] = None) -> dict:
        out = {
            "track_id": self.track_id,
            "label": self.label,
            "board_xy_mm": {"x": self.x_mm, "y": self.y_mm},
            "quality_grade": self.quality_grade,
            "first_frame": self.first_frame,
            "last_frame": self.last_frame,
            "last_seen_ts": self.last_seen_ts,
            "hits": self.hits,
        }
        if current_frame is not None:
            out["age_frames"] = max(0, current_frame - self.first_frame)
        return out


def _finite(x: Any) -> bool:
    try:
        return math.isfinite(float(x))
    except (TypeError, ValueError):
        return False


class FruitTracker:
    """Greedy centroid tracker in board-frame mm. Label-locked matching."""

    DEFAULT_MATCH_RADIUS_MM = 40.0
    DEFAULT_MAX_AGE_FRAMES = 60       # ~2 s at 30 fps

    def __init__(
        self,
        match_radius_mm: float = DEFAULT_MATCH_RADIUS_MM,
        max_age_frames: int = DEFAULT_MAX_AGE_FRAMES,
    ):
        self._tracks: dict[int, Track] = {}
        self._next_id: int = 1
        self._last_frame: int = -1
        self.match_radius_mm = float(match_radius_mm)
        self.max_age_frames = int(max_age_frames)

    # -- public API --------------------------------------------------

    def update(
        self,
        detections: Iterable[MutableMapping],
        frame_index: int,
        now_ts: float,
    ) -> List[dict]:
        """Match detections to tracks, mutate them with `track_id`, prune stale tracks.

        Returns a list of event dicts emitted this frame:
          {"event": "new"|"lost", "track_id", "label", "x_mm", "y_mm", "frame", "ts"}
        """
        self._last_frame = frame_index
        events: List[dict] = []

        produce: List[tuple[MutableMapping, str, float, float]] = []
        for d in detections:
            if not isinstance(d, MutableMapping):
                continue
            if d.get("detection_type") != "produce":
                continue
            board = d.get("board_xy_mm") or {}
            x, y = board.get("x"), board.get("y")
            if not (_finite(x) and _finite(y)):
                continue
            label = str(d.get("label") or "produce")
            produce.append((d, label, float(x), float(y)))

        # Greedy: build all candidate (detection, track, distance) within radius,
        # sort, lock detections and tracks as they get paired.
        candidates: List[tuple[float, int, int]] = []
        det_index_by_id = {id(p[0]): i for i, p in enumerate(produce)}
        for di, (_d, label, x, y) in enumerate(produce):
            for tid, t in self._tracks.items():
                if t.label != label:
                    continue
                dist = math.hypot(x - t.x_mm, y - t.y_mm)
                if dist <= self.match_radius_mm:
                    candidates.append((dist, di, tid))
        candidates.sort(key=lambda c: c[0])

        used_detections: set[int] = set()
        used_tracks: set[int] = set()
        for dist, di, tid in candidates:
            if di in used_detections or tid in used_tracks:
                continue
            used_detections.add(di)
            used_tracks.add(tid)
            d, label, x, y = produce[di]
            t = self._tracks[tid]
            t.x_mm = x
            t.y_mm = y
            t.last_frame = frame_index
            t.last_seen_ts = now_ts
            t.hits += 1
            t.quality_grade = (d.get("quality") or {}).get("grade") or t.quality_grade
            d["track_id"] = tid

        # New tracks for unmatched detections.
        for di, (d, label, x, y) in enumerate(produce):
            if di in used_detections:
                continue
            tid = self._next_id
            self._next_id += 1
            quality_grade = (d.get("quality") or {}).get("grade")
            t = Track(
                track_id=tid,
                label=label,
                x_mm=x,
                y_mm=y,
                quality_grade=quality_grade,
                first_frame=frame_index,
                last_frame=frame_index,
                last_seen_ts=now_ts,
                hits=1,
            )
            self._tracks[tid] = t
            d["track_id"] = tid
            events.append({
                "event": "new", "track_id": tid, "label": label,
                "x_mm": x, "y_mm": y, "frame": frame_index, "ts": now_ts,
            })

        # Prune stale tracks. A track that has gone `max_age_frames` without a
        # match is considered lost.
        stale: List[int] = []
        for tid, t in self._tracks.items():
            if frame_index - t.last_frame > self.max_age_frames:
                stale.append(tid)
        for tid in stale:
            t = self._tracks.pop(tid)
            events.append({
                "event": "lost", "track_id": tid, "label": t.label,
                "x_mm": t.x_mm, "y_mm": t.y_mm,
                "frame": frame_index, "ts": now_ts, "hits": t.hits,
            })

        return events

    def to_snapshot(self) -> dict:
        return {
            "frame": self._last_frame,
            "ts": max((t.last_seen_ts for t in self._tracks.values()), default=0.0),
            "tracks": [t.to_dict(current_frame=self._last_frame)
                       for t in self._tracks.values()],
        }

    def write_snapshot(self, path: str) -> None:
        parent = os.path.dirname(os.path.abspath(path)) or "."
        os.makedirs(parent, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_snapshot(), f, indent=2)

    def append_event(self, path: str, event: Mapping) -> None:
        parent = os.path.dirname(os.path.abspath(path)) or "."
        os.makedirs(parent, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(dict(event)) + "\n")

    # -- accessors useful for tests / debugging ----------------------

    @property
    def tracks(self) -> dict[int, Track]:
        return self._tracks

    def __len__(self) -> int:
        return len(self._tracks)
