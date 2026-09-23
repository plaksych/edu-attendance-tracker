"""Real CPU execution with a pinned local model; never downloads weights."""

import hashlib
import json
import os
from pathlib import Path


def main():
    import numpy as np
    from ultralytics import YOLO

    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((root / "recognition/model-manifest.json").read_text())
    model = Path(os.environ["MODEL_PATH"])
    with model.open("rb") as handle:
        checksum = hashlib.file_digest(handle, "sha256").hexdigest()
    if checksum != manifest["sha256"]:
        raise SystemExit("Model checksum differs from reviewed manifest")
    result = YOLO(str(model)).predict(
        np.zeros((640, 640, 3), dtype=np.uint8), device="cpu", verbose=False
    )
    if len(result) != 1 or result[0].boxes is None:
        raise SystemExit("Inference returned an invalid result")
    print(
        json.dumps(
            {
                "status": "passed",
                "model_sha256": checksum,
                "device": "cpu",
                "input": "synthetic black frame",
                "quality_evaluation": False,
            }
        )
    )


if __name__ == "__main__":
    main()
