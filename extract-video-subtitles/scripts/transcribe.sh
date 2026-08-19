#!/usr/bin/env bash
# 优先：提取可用的字幕轨（在线字幕 / 内嵌字幕）→ 纯文本
# 回退：下载媒体 → 提取音频 → Whisper 中文转写
# 用法: transcribe.sh <url|本地文件> <输出目录> [small|base|medium]
set -euo pipefail

YTDLP="/Users/qianxu/Library/Python/3.9/bin/yt-dlp"
WHISPER="/opt/homebrew/bin/whisper-cli"
MODELS="/opt/homebrew/opt/whisper-cpp/models"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

URL_OR_FILE="${1:?需要音视频链接或本地文件路径}"
OUTDIR="${2:?需要输出目录}"
MODEL="${3:-small}"

mkdir -p "$OUTDIR"
cd "$OUTDIR"
MODE=""

# 从已下载的字幕文件里挑一个最好的（优先中文，其次 srt/vtt/ass）
pick_sub() {
  local f chosen=""
  for f in subs.*; do
    [[ -e "$f" ]] || continue
    [[ "$f" == *.json || "$f" == *info.json ]] && continue
    if [[ "$f" == *zh* ]]; then chosen="$f"; break; fi
  done
  if [[ -z "$chosen" ]]; then
    chosen="$(ls subs.* 2>/dev/null | grep -vi json | head -1 || true)"
  fi
  printf '%s' "$chosen"
}

# ===== 情况 A：本地文件，有内嵌字幕轨时直接提取 =====
if [[ -f "$URL_OR_FILE" ]]; then
  if ffprobe -v error -select_streams s -show_entries stream=index -of csv=p=0 "$URL_OR_FILE" | grep -q .; then
    ffmpeg -y -v error -i "$URL_OR_FILE" -map 0:s:0 -c:s srt subtitle.srt
    python3 "$SCRIPT_DIR/subs2txt.py" subtitle.srt subs.txt
    MODE="local-embedded-sub"
  fi

# ===== 情况 B：在线链接，先试直接下载字幕轨（不下载媒体） =====
else
  "$YTDLP" --skip-download --write-subs --write-auto-subs \
    --sub-langs "all" -o "subs.%(ext)s" "$URL_OR_FILE" >/dev/null 2>&1 || true
  SUB="$(pick_sub)"
  if [[ -n "$SUB" ]]; then
    cp "$SUB" "subtitle.$(sed 's/.*\.//' <<<"$SUB")"
    python3 "$SCRIPT_DIR/subs2txt.py" "$SUB" subs.txt
    MODE="online-sub: $SUB"
  else
    rm -f subs.* 2>/dev/null || true
  fi
fi

# ===== 有字幕：走字幕 → 纯文本，结束 =====
if [[ -n "$MODE" ]]; then
  echo "字幕轨可用（$MODE）→ 已生成 subs.txt，无需语音识别。"
  echo "完成 -> $OUTDIR/subs.txt"
  exit 0
fi

# ===== 情况 C：回退——下载音频 → Whisper 语音识别 =====
if [[ -f "$URL_OR_FILE" ]]; then
  SRC="$URL_OR_FILE"
else
  "$YTDLP" -f "bestaudio/best" -o "input.%(ext)s" "$URL_OR_FILE"
  SRC="$(ls -1 input.* | head -1)"
fi

ffmpeg -y -v error -i "$SRC" -vn -ac 1 -ar 16000 -c:a pcm_s16le audio.wav
"$WHISPER" -ng -m "$MODELS/ggml-$MODEL.bin" -l zh -osrt -otxt -of transcript audio.wav

# 收尾清理：只删脚本自己下载的媒体与 WAV，绝不删用户原始本地文件。
rm -f "$OUTDIR"/input.* "$OUTDIR"/audio.wav

echo "无可用字幕轨，已回退语音识别 -> $OUTDIR/transcript.txt（可用 t2s.py 转简体）"
echo "已自动清理下载媒体与音频中间文件，仅保留文字稿。"
