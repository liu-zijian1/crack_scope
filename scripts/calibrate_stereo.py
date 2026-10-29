"""Calibrate a side-by-side stereo camera from paired checkerboard images."""
import argparse
import json
from pathlib import Path

import cv2
import numpy as np


def image_files(folder):
    files = []
    for pattern in ("*.png", "*.jpg", "*.jpeg", "*.bmp"):
        files.extend(Path(folder).glob(pattern))
    return {path.stem: path for path in files}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--left", required=True, help="Folder of left checkerboard images")
    parser.add_argument("--right", required=True, help="Folder of right checkerboard images")
    parser.add_argument("--output", default="calibration/stereo_calibration.npz")
    parser.add_argument("--corners", nargs=2, type=int, default=(8, 6), metavar=("COLS", "ROWS"))
    parser.add_argument("--square-mm", type=float, default=25.0)
    args = parser.parse_args()

    left_files = image_files(args.left)
    right_files = image_files(args.right)
    pairs = [(left_files[key], right_files[key]) for key in sorted(left_files.keys() & right_files.keys())]
    if len(pairs) < 10:
        raise SystemExit(f"Need at least 10 paired checkerboard views; found {len(pairs)}.")

    cols, rows = args.corners
    object_template = np.zeros((rows * cols, 3), np.float32)
    object_template[:, :2] = np.mgrid[0:cols, 0:rows].T.reshape(-1, 2) * args.square_mm
    object_points, image_points_left, image_points_right = [], [], []
    image_size = None
    accepted = []
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)

    for left_path, right_path in pairs:
        left = cv2.imread(str(left_path), cv2.IMREAD_GRAYSCALE)
        right = cv2.imread(str(right_path), cv2.IMREAD_GRAYSCALE)
        if left is None or right is None or left.shape != right.shape:
            print(f"Skip unreadable or mismatched pair: {left_path.name}")
            continue
        size = (left.shape[1], left.shape[0])
        if image_size is not None and size != image_size:
            raise SystemExit("All checkerboard images must have the same resolution.")
        image_size = size
        found_left, corners_left = cv2.findChessboardCorners(
            left, (cols, rows), cv2.CALIB_CB_ADAPTIVE_THRESH | cv2.CALIB_CB_NORMALIZE_IMAGE
        )
        found_right, corners_right = cv2.findChessboardCorners(
            right, (cols, rows), cv2.CALIB_CB_ADAPTIVE_THRESH | cv2.CALIB_CB_NORMALIZE_IMAGE
        )
        if not (found_left and found_right):
            print(f"Skip pair where checkerboard was not found in both images: {left_path.name}")
            continue
        corners_left = cv2.cornerSubPix(left, corners_left, (11, 11), (-1, -1), criteria)
        corners_right = cv2.cornerSubPix(right, corners_right, (11, 11), (-1, -1), criteria)
        object_points.append(object_template.copy())
        image_points_left.append(corners_left)
        image_points_right.append(corners_right)
        accepted.append(left_path.stem)

    if len(object_points) < 10:
        raise SystemExit(f"Need at least 10 valid paired views; found {len(object_points)}.")

    rms_left, k1, d1, _, _ = cv2.calibrateCamera(object_points, image_points_left, image_size, None, None)
    rms_right, k2, d2, _, _ = cv2.calibrateCamera(object_points, image_points_right, image_size, None, None)
    rms_stereo, k1, d1, k2, d2, rotation, translation, _, _ = cv2.stereoCalibrate(
        object_points, image_points_left, image_points_right,
        k1, d1, k2, d2, image_size, criteria=criteria,
        flags=cv2.CALIB_FIX_INTRINSIC,
    )
    r1, r2, p1, p2, q, _, _ = cv2.stereoRectify(
        k1, d1, k2, d2, image_size, rotation, translation, alpha=0
    )
    baseline_mm = float(np.linalg.norm(translation))

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        output,
        K1=k1, D1=d1, R1=r1, P1=p1,
        K2=k2, D2=d2, R2=r2, P2=p2,
        Q=q, image_size=np.asarray(image_size, dtype=np.int32),
        baseline_mm=np.asarray(baseline_mm),
    )
    summary = {
        "image_size": list(image_size),
        "pattern_inner_corners": [cols, rows],
        "square_mm": args.square_mm,
        "used_pairs": accepted,
        "rms_left": float(rms_left),
        "rms_right": float(rms_right),
        "rms_stereo": float(rms_stereo),
        "baseline_mm": baseline_mm,
        "output_npz": str(output),
    }
    output.with_suffix(".json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
