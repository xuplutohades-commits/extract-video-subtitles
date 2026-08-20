#!/usr/bin/env bash
# 情况 E：微信视频号/公众号视频 —— 从本地微信缓存捕获刚播放过的视频。
# 正常下载器（yt-dlp）拿不到视频号链接，本脚本改为：
#   用户在自己的 Mac 微信里打开目标视频并播放 → 微信把媒体缓存到本地 →
#   脚本把"刚出现的这条新缓存"复制出来。
# 用法分两步（中间由用户/Agent 在微信里播放目标视频）：
#   1) capture_wechat_video.sh snapshot --state <state.json>     播放前记录基线
#   2) capture_wechat_video.sh capture --state <state.json> --out <outdir> \
#        --link <原始链接> [--timeout 1800] [--stable-seconds 5]  播放后捕获
# 捕获成功后 outdir 里会有 video.mp4 + metadata.json，可直接交给 transcribe.sh 转写。
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$SCRIPT_DIR/capture_wechat_video.py" "$@"
