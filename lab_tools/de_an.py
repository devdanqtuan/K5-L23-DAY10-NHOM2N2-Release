#!/usr/bin/env python3
"""Prepare the review queue and export the four hidden-round submission files.
Phụ trách: Đặng Gia Tuấn (@tuandg) - Nhóm HMH.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import subprocess
import sys

from handover import findings, write_csv
from trace import trace
from validate import Delivery, read_csv, read_json, validate, write_json


def bind_delivery(delivery, work, preparing):
    release_id = read_json(delivery.path("release.json"))["release_id"]
    marker = work / "release_id.txt"
    if marker.exists():
        if marker.read_text(encoding="utf-8").strip() != release_id:
            raise ValueError("Thư mục review thuộc lô khác. Chọn --work mới.")
    elif preparing and not (work / "review_log.csv").exists():
        work.mkdir(parents=True, exist_ok=True)
        marker.write_text(release_id + "\n", encoding="utf-8")
    else:
        raise ValueError("Chạy prepare trong thư mục làm việc mới cho đúng lô đề.")


def prepare(delivery, work):
    bind_delivery(delivery, work, preparing=True)
    errors, candidates = validate(delivery, generate_candidates=True)
    write_json(work / "rules.json", {"errors": errors})
    write_json(work / "candidates.json", {"candidates": candidates})
    write_json(work / "trace.json", trace(delivery))
    subprocess.run(
        [sys.executable, str(Path(__file__).with_name("review.py")), str(delivery.root),
         str(work / "candidates.json"), "--html", str(work / "review.html"),
         "--log", str(work / "review_log.csv")],
        check=True,
    )
    print(f"{len(errors)} lỗi luật. Hoàn tất verdict và ghi tên người xem trong {work / 'review_log.csv'}.")


def finish(delivery, work, output, only_reviewed):
    bind_delivery(delivery, work, preparing=False)
    errors = findings(work, delivery, require_complete=not only_reviewed)
    write_json(output / "errors.json", {
        "errors": [{"type": kind, "target": target} for kind, target in sorted(errors)]
    })
    for filename in ("candidates.json", "trace.json"):
        shutil.copyfile(work / filename, output / filename)
    review = work / "review_log.csv"
    if only_reviewed:
        rows = read_csv(review)
        fields = ("image", "type", "verdict", "note")
        reviewed = [row for row in rows if row["verdict"].strip()]
        write_csv(output / review.name, fields, [[row[field] for field in fields] for row in reviewed])
        print(f"Đã xuất {len(reviewed)} dòng review. Bỏ {len(rows) - len(reviewed)} dòng chưa kết luận.")
    else:
        shutil.copyfile(review, output / review.name)
    print(f"Đã xuất {len(errors)} lỗi và đủ bốn file vào {output}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("prepare", "finish"))
    parser.add_argument("--delivery", type=Path, default=Path("delivery"))
    parser.add_argument("--work", type=Path, default=Path("runs/de_an"))
    parser.add_argument("--out", type=Path, default=Path("submission/de_an"))
    parser.add_argument("--only-reviewed", action="store_true",
                        help="Khi finish, chỉ xuất verdict đã chốt nếu chưa xem xong cả hàng đợi.")
    args = parser.parse_args()
    if args.only_reviewed and args.phase != "finish":
        parser.error("--only-reviewed chỉ dùng với finish.")
    delivery_root, work, output = (p.resolve() for p in (args.delivery, args.work, args.out))
    if (work == output or work.is_relative_to(delivery_root)
            or output.is_relative_to(delivery_root)):
        parser.error("Đặt thư mục làm việc và nộp bài riêng, bên ngoài delivery.")
    try:
        delivery = Delivery(delivery_root)
        if args.phase == "prepare":
            prepare(delivery, work)
        else:
            finish(delivery, work, output, args.only_reviewed)
    except (OSError, ValueError) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
