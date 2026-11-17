"""Arrange the organizers' public dataset for the replay scripts.

Download the dataset first (it is not redistributed here), for example

  huggingface-cli download CarolynJiang/Market-Neutral-Hedging-live-trading \
      --repo-type dataset --local-dir data/hf

then run

  python src/prepare_data.py

which copies every October release folder data/hf/data/<YYYY-MM-DD_HH-MM>_NY/ to
data/raw/<YYYY-MM-DD_HH-MM>/ (price.parquet and news.parquet), the layout the replay reads.
"""

import argparse
import hashlib
import pathlib
import shutil

ROOT = pathlib.Path(__file__).resolve().parents[1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=str(ROOT / "data/hf/data"))
    ap.add_argument("--dst", default=str(ROOT / "data/raw"))
    ap.add_argument("--prefix", default="2026-10", help="release folders to copy (October live phase)")
    a = ap.parse_args()
    src, dst = pathlib.Path(a.src), pathlib.Path(a.dst)
    n = 0
    for d in sorted(src.glob(a.prefix + "*_NY")):
        out = dst / d.name[: -len("_NY")]
        out.mkdir(parents=True, exist_ok=True)
        for name in ("price.parquet", "news.parquet"):
            if (d / name).exists():
                shutil.copy2(d / name, out / name)
                print(out.name, name, hashlib.sha256((out / name).read_bytes()).hexdigest())
        n += 1
    print(f"{n} release folders written to {dst}")


if __name__ == "__main__":
    main()
