#!/usr/bin/env python3
"""Capture a newly played WeChat video from the local desktop cache.

Handles both current WeChat 4.x (Group Container) and legacy 3.x containers.
When a normal downloader (yt-dlp) cannot reach a WeChat channel (视频号) link,
the workaround is: the user opens the target video inside the desktop WeChat
app, let it play through, and a NEW copy of that cached media appears on disk.
This script:

  1. snapshot  - records a baseline of cached media files (before playing)
  2. capture   - waits for a new/changed stable media file, verifies it,
                 copies it out and writes metadata.json
  3. adopt     - archives a user-provided local MP4/MOV directly

No proxy, no root certificates, no traffic decryption, no cookies are used.
Default scan roots (newest first) can be overridden with
EXTRACT_WECHAT_FILES_ROOT.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time


MIN_BYTES = 8 * 1024
# A tolerant extension set so the diff-based scan works even if the
# cache layout of WeChat 4.x differs from 3.x.
MEDIA_SUFFIXES = {".mp4", ".mov", ".m4v", ".mkv", ".3gp", ".rmvb", ".flv", ".avi", ".tmp", ".dat"}

DEFAULT_BASE_ROOTS = [
    # WeChat 4.x group container (current default)
    Path.home() / "Library/Group Containers/5A4RE8SF68.com.tencent.xinWeChat",
    # WeChat 3.x container
    Path.home() / "Library/Containers/com.tencent.xinWeChat/Data/Documents/xwechat_files",
]

SKIPPED_DIRS = {"__MACOSX"}


def base_roots() -> list[Path]:
    override = os.environ.get("EXTRACT_WECHAT_FILES_ROOT")
    if override and override.strip():
        return [Path(override).expanduser()]
    return DEFAULT_BASE_ROOTS


def existing_base_roots() -> list[Path]:
    return [root for root in base_roots() if root.is_dir()]


def _iter_candidate_files(root: Path):
    """Yield candidate media files under *root* (bounded, depth-first walk)."""
    if not root.is_dir():
        return
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIPPED_DIRS and not d.startswith(".")]
        base = Path(dirpath)
        for name in filenames:
            if Path(name).suffix.lower() in MEDIA_SUFFIXES:
                yield base / name


def candidate_paths() -> list[Path]:
    found: dict[str, Path] = {}
    roots = existing_base_roots()
    if not roots:
        return []
    for root in roots:
        for path in _iter_candidate_files(root):
            found[str(path)] = path
    return list(found.values())


def looks_like_media(path: Path) -> bool:
    try:
        if path.stat().st_size < MIN_BYTES:
            return False
        with path.open("rb") as handle:
            head = handle.read(16)
    except OSError:
        return False
    return len(head) >= 12 and head[4:8] == b"ftyp"


def inventory(*, newer_than_ns: int | None = None, verify_media: bool = True) -> dict[str, dict[str, int]]:
    result: dict[str, dict[str, int]] = {}
    for path in candidate_paths():
        try:
            stat = path.stat()
        except OSError:
            continue
        if newer_than_ns is not None and stat.st_mtime_ns <= newer_than_ns:
            continue
        if verify_media and not looks_like_media(path):
            continue
        result[str(path)] = {"size": stat.st_size, "mtime_ns": stat.st_mtime_ns}
    return result


def ffprobe(path: Path) -> dict[str, object]:
    command = shutil.which("ffprobe")
    if not command:
        raise RuntimeError("ffprobe is required; install ffmpeg")
    result = subprocess.run(
        [
            command, "-v", "error", "-show_entries",
            "format=duration,size,format_name:stream=index,codec_type,codec_name,width,height",
            "-of", "json", str(path),
        ],
        text=True, capture_output=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "ffprobe could not read the cached video")
    data = json.loads(result.stdout)
    duration = float(data.get("format", {}).get("duration") or 0)
    if duration <= 0:
        raise RuntimeError("Cached media has no readable duration")
    video_stream = next((item for item in data.get("streams", []) if item.get("codec_type") == "video"), {})
    audio_stream = next((item for item in data.get("streams", []) if item.get("codec_type") == "audio"), {})
    return {
        "duration_seconds": duration,
        "format_name": data.get("format", {}).get("format_name", ""),
        "width": video_stream.get("width"),
        "height": video_stream.get("height"),
        "video_codec": video_stream.get("codec_name", ""),
        "audio_codec": audio_stream.get("codec_name", ""),
        "has_audio": bool(audio_stream),
    }


def create_cover(video: Path, destination: Path, duration: float) -> bool:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return False
    seek = min(1.0, max(0.0, duration * 0.1))
    result = subprocess.run(
        [ffmpeg, "-hide_banner", "-loglevel", "error", "-ss", f"{seek:.3f}",
         "-i", str(video), "-frames:v", "1", "-q:v", "2", "-y", str(destination)],
        text=True, capture_output=True,
    )
    return result.returncode == 0 and destination.exists()


def adopt(source: Path, out_dir: Path, source_link: str = "") -> dict[str, object]:
    source = source.expanduser().resolve()
    if not source.is_file() or not looks_like_media(source):
        raise RuntimeError(f"Not a readable MP4-family media file: {source}")
    probe = ffprobe(source)
    out_dir.mkdir(parents=True, exist_ok=True)
    destination = out_dir / "video.mp4"
    shutil.copy2(source, destination)
    copied_probe = ffprobe(destination)
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    copied_hash = hashlib.sha256(destination.read_bytes()).hexdigest()
    if source_hash != copied_hash:
        raise RuntimeError("Video copy checksum mismatch")
    cover = out_dir / "cover.jpg"
    if not create_cover(destination, cover, float(copied_probe["duration_seconds"])) and cover.exists():
        cover.unlink()
    metadata: dict[str, object] = {
        "status": "captured",
        "captured_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "source_link": source_link,
        "source_cache_path": str(source),
        "video_path": "video.mp4",
        "cover_path": "cover.jpg" if cover.exists() else "",
        "sha256": copied_hash,
        **probe,
    }
    (out_dir / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return metadata


def snapshot(state_file: Path) -> dict[str, object]:
    roots = existing_base_roots()
    if not roots:
        raise RuntimeError(
            "找不到微信本地缓存目录。请先安装并登录桌面版微信（WeChat），"
            "并用它播放过一次视频后再试。"
        )
    created_ns = time.time_ns()
    current = inventory(verify_media=False)
    data: dict[str, object] = {
        "created_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "created_at_ns": created_ns,
        "roots": [str(root) for root in roots],
        "candidate_count": len(current),
        "files": current,
    }
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return data


def changed_candidates(baseline: dict[str, dict[str, int]], current: dict[str, dict[str, int]]) -> list[Path]:
    changed: list[tuple[int, int, Path]] = []
    for value, state in current.items():
        previous = baseline.get(value)
        if previous is None or state["size"] != previous.get("size") or state["mtime_ns"] != previous.get("mtime_ns"):
            changed.append((state["mtime_ns"], state["size"], Path(value)))
    changed.sort(reverse=True)
    return [item[2] for item in changed]


def wait_for_capture(state_file: Path, out_dir: Path, source_link: str,
                     timeout: int, stable_seconds: int) -> dict[str, object]:
    if not state_file.is_file():
        raise RuntimeError("未找到基线文件；请先运行 snapshot，再在微信里播放视频。")
    baseline_data = json.loads(state_file.read_text(encoding="utf-8"))
    baseline: dict[str, dict[str, int]] = baseline_data.get("files", {})
    created_at_ns = int(baseline_data.get("created_at_ns") or 0)
    deadline = time.monotonic() + timeout
    observed: dict[str, tuple[int, float]] = {}
    last_error = ""

    while time.monotonic() < deadline:
        current = inventory(newer_than_ns=created_at_ns or None)
        for path in changed_candidates(baseline, current):
            state = current[str(path)]
            previous = observed.get(str(path))
            now = time.monotonic()
            if previous is None or previous[0] != state["size"]:
                observed[str(path)] = (state["size"], now)
                continue
            if now - previous[1] < stable_seconds:
                continue
            try:
                return adopt(path, out_dir, source_link)
            except Exception as exc:
                last_error = str(exc)
        time.sleep(1)
    detail = f" 最近一次媒体校验错误：{last_error}" if last_error else ""
    raise RuntimeError(
        f"在 {timeout} 秒内没有等到新的微信视频缓存。"
        "请确认已经在微信里完整播放过目标视频。"
        f"{detail}"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    snap = sub.add_parser("snapshot", help="播放前记录微信缓存基线")
    snap.add_argument("--state", required=True, type=Path)
    capture = sub.add_parser("capture", help="等待微信里出现新视频缓存并复制出来")
    capture.add_argument("--state", required=True, type=Path)
    capture.add_argument("--out", required=True, type=Path)
    capture.add_argument("--link", default="")
    capture.add_argument("--timeout", type=int, default=1800)
    capture.add_argument("--stable-seconds", type=int, default=5)
    local = sub.add_parser("adopt", help="直接归档用户提供的本地视频")
    local.add_argument("video", type=Path)
    local.add_argument("--out", required=True, type=Path)
    local.add_argument("--link", default="")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.command == "snapshot":
            result = snapshot(args.state.expanduser().resolve())
            payload = {
                "status": "snapshot",
                "files": result["candidate_count"],
                "roots": result["roots"],
                "state": str(args.state.expanduser().resolve()),
            }
        elif args.command == "capture":
            result = wait_for_capture(
                args.state.expanduser().resolve(),
                args.out.expanduser().resolve(),
                args.link,
                args.timeout,
                args.stable_seconds,
            )
            payload = {
                "status": "captured",
                "out": str(args.out.expanduser().resolve()),
                "duration_seconds": result["duration_seconds"],
            }
        else:
            result = adopt(args.video, args.out.expanduser().resolve(), args.link)
            payload = {
                "status": "captured",
                "out": str(args.out.expanduser().resolve()),
                "duration_seconds": result["duration_seconds"],
            }
    except Exception as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
