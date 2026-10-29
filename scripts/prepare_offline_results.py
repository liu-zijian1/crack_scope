"""Precompute offline demo predictions into static site assets."""
import json
import os
import sys

_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _HERE)
from src import crackscope


def main():
    out_dir = os.path.join(_HERE, "assets", "offline_results")
    os.makedirs(out_dir, exist_ok=True)
    results = []
    for sample in crackscope.OFFLINE_SAMPLES:
        raw_img = crackscope.load_offline_sample(sample)
        payload = crackscope.build_offline_payload(sample, raw_img, stream=False)
        results.append(payload)
        print(sample["file"], payload["result"]["width_mm"], payload["result"]["message"])
    out_path = os.path.join(out_dir, "offline_results.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False)
    print("wrote", out_path)


if __name__ == "__main__":
    main()
