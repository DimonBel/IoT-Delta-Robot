"""Unit tests for vision.tracker.FruitTracker.

Pure stdlib, no cv2 / ZED / numpy required. Synthetic detection dicts feed
the tracker frame by frame; assertions check that IDs stay stable when a
fruit moves a little, that big jumps spawn a new ID, that different labels
don't merge, and that stale tracks get pruned.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest

from vision.tracker import FruitTracker


def _det(label, x, y, *, dt="produce", track_id=None, quality=None):
    d = {
        "label": label,
        "detection_type": dt,
        "bbox_xyxy": [int(x) - 10, int(y) - 10, int(x) + 10, int(y) + 10],
        "board_xy_mm": {"x": float(x), "y": float(y), "inside_zone": True},
    }
    if quality is not None:
        d["quality"] = {"grade": quality}
    return d


class FruitTrackerTests(unittest.TestCase):
    def test_new_detection_creates_track(self):
        tr = FruitTracker()
        d = _det("orange", 10.0, 10.0)
        events = tr.update([d], frame_index=0, now_ts=0.0)
        self.assertEqual(d["track_id"], 1)
        self.assertEqual(len(tr.tracks), 1)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event"], "new")
        self.assertEqual(events[0]["track_id"], 1)

    def test_close_detection_keeps_same_id(self):
        tr = FruitTracker(match_radius_mm=40.0)
        d1 = _det("orange", 0.0, 0.0)
        tr.update([d1], frame_index=0, now_ts=0.0)
        d2 = _det("orange", 10.0, -5.0)  # 11 mm away
        events = tr.update([d2], frame_index=1, now_ts=0.1)
        self.assertEqual(d2["track_id"], d1["track_id"])
        self.assertEqual(len(tr.tracks), 1)
        self.assertEqual(events, [])  # match, no new/lost

    def test_far_detection_creates_new_id(self):
        tr = FruitTracker(match_radius_mm=40.0)
        d1 = _det("orange", 0.0, 0.0)
        tr.update([d1], frame_index=0, now_ts=0.0)
        d2 = _det("orange", 100.0, 0.0)  # well beyond radius
        events = tr.update([d2], frame_index=1, now_ts=0.1)
        self.assertNotEqual(d2["track_id"], d1["track_id"])
        # Old track still alive (not yet stale), so two tracks now.
        self.assertEqual(len(tr.tracks), 2)
        self.assertTrue(any(e["event"] == "new" for e in events))

    def test_different_label_creates_new_id(self):
        tr = FruitTracker(match_radius_mm=40.0)
        d_orange = _det("orange", 0.0, 0.0)
        d_apple = _det("apple", 0.0, 0.0)
        tr.update([d_orange, d_apple], frame_index=0, now_ts=0.0)
        self.assertNotEqual(d_orange["track_id"], d_apple["track_id"])
        self.assertEqual(len(tr.tracks), 2)

    def test_track_pruned_after_max_age(self):
        tr = FruitTracker(match_radius_mm=40.0, max_age_frames=3)
        d = _det("orange", 0.0, 0.0)
        tr.update([d], frame_index=0, now_ts=0.0)
        # 4 empty frames -> exceeds max_age_frames=3.
        events_lost = []
        for f in range(1, 5):
            events_lost.extend(tr.update([], frame_index=f, now_ts=float(f)))
        self.assertEqual(len(tr.tracks), 0)
        self.assertTrue(any(e["event"] == "lost" for e in events_lost))

    def test_snapshot_round_trip(self):
        tr = FruitTracker()
        d = _det("orange", 0.0, 0.0, quality="good")
        tr.update([d], frame_index=0, now_ts=0.0)
        snap = tr.to_snapshot()
        self.assertEqual(snap["frame"], 0)
        self.assertEqual(len(snap["tracks"]), 1)
        t = snap["tracks"][0]
        self.assertEqual(t["label"], "orange")
        self.assertEqual(t["track_id"], 1)
        self.assertEqual(t["board_xy_mm"], {"x": 0.0, "y": 0.0})
        self.assertEqual(t["quality_grade"], "good")
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "snap.json")
            tr.write_snapshot(path)
            with open(path) as f:
                loaded = json.load(f)
            self.assertEqual(loaded, snap)

    def test_event_log_round_trip(self):
        tr = FruitTracker(max_age_frames=1)
        d1 = _det("orange", 0.0, 0.0)
        tr.update([d1], frame_index=0, now_ts=0.0)
        events = tr.update([], frame_index=2, now_ts=2.0)  # prune
        self.assertTrue(events)
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "events.jsonl")
            for ev in events:
                tr.append_event(path, ev)
            with open(path) as f:
                lines = [json.loads(line) for line in f if line.strip()]
        self.assertEqual(len(lines), len(events))
        self.assertEqual(lines[0]["event"], "lost")

    def test_non_produce_ignored(self):
        tr = FruitTracker()
        person = _det("person", 0.0, 0.0, dt="human")
        events = tr.update([person], frame_index=0, now_ts=0.0)
        self.assertNotIn("track_id", person)
        self.assertEqual(len(tr.tracks), 0)
        self.assertEqual(events, [])

    def test_missing_board_xy_skipped(self):
        tr = FruitTracker()
        d = {"label": "orange", "detection_type": "produce",
             "bbox_xyxy": [0, 0, 20, 20]}
        events = tr.update([d], frame_index=0, now_ts=0.0)
        self.assertNotIn("track_id", d)
        self.assertEqual(len(tr.tracks), 0)
        self.assertEqual(events, [])

    def test_greedy_picks_closest(self):
        tr = FruitTracker(match_radius_mm=40.0)
        # Two oranges 50 mm apart established as tracks.
        a = _det("orange", 0.0, 0.0)
        b = _det("orange", 50.0, 0.0)
        tr.update([a, b], frame_index=0, now_ts=0.0)
        # New frame: two detections that should each match the closer track.
        a2 = _det("orange", 5.0, 0.0)
        b2 = _det("orange", 55.0, 0.0)
        tr.update([a2, b2], frame_index=1, now_ts=0.1)
        self.assertEqual(a2["track_id"], a["track_id"])
        self.assertEqual(b2["track_id"], b["track_id"])
        self.assertEqual(len(tr.tracks), 2)


if __name__ == "__main__":
    unittest.main()
