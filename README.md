## IoT Delta Robot

***

## Vision Coordinates Logic 

The vision module now contains additive ZED 3D coordinate detection logic copied from the detection project.

Included capabilities:

- Object detection with ZED camera fallback initialization presets.
- 3D coordinate extraction in meters (`x`, `y`, `z`) with finite-value fallback from point cloud center sampling.
- Optional backend JSON streaming hooks using HTTP POST.
- Frame payload schema with per-frame detections.

Payload example:

```json
{
	"timestamp_unix": 1712581200.123,
	"frame_index": 25,
	"detections": [
		{
			"id": 1,
			"label": "PERSON",
			"confidence": 92.0,
			"position_m": {
				"x": 0.42,
				"y": -0.1,
				"z": 1.85
			},
			"distance_m": 1.9
		}
	]
}
```

### Notes

- `pyzed` is provided by the ZED SDK installer and is typically not installed from pip.
- Added Python package requirements are listed in `requirements.txt`.

