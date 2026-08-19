#!/usr/bin/env bash
# 下载媒体（或接受本地文件）→ 提取 16kHz 单声道 WAV → Whisper 中文转写输出 txt/srt
# 用法: transcribe.sh <url|本地文件> <输出目录> [small|base|medium]
set -euo pipefail

YTDLP="/Users/qianxu/Library/Python/3.9/bin/yt-dlp"
WHISPER="/opt/homebrew/bin/whisper-cli"
MODELS="/opt/homebrew/opt/whisper-cpp/models"

URL_OR_FILE="${1:?需要音视频链接或本地文件路径}"
OUTDIR="${2:?需要输出目录}"
MODEL="${3:-small}"

mkdir -p "$OUTDIR"
cd "$OUTDIR"

if [[ -f "$URL_OR_FILE" ]]; then
  SRC="$URL_OR_FILE"
else
  # 只下载最佳音轨（不带画面，省流量）；失败时回退最佳整体媒体
  "$YTDLP" -f "bestaudio/best" -o "input.%(ext)s" "$URL_OR_FILE"
  SRC="$(ls -1 input.* | head -1)"
fi

# 转成 16kHz 单声道无压缩 WAV（whisper 输入要求）
ffmpeg -y -v error -i "$SRC" -vn -ac 1 -ar 16000 -c:a pcm_s16le audio.wav

# 中文转写，CPU 模式（-ng），输出纯文本 + srt
"$WHISPER" -ng -m "$MODELS/ggml-$MODEL.bin" -l zh -osrt -otxt -of transcript audio.wav

# 收尾清理：删掉脚本自己下载的媒体(input.*)与提取出的 WAV，只保留小体积文字稿。
# 注意：绝不删除用户传入的原始本地文件（$SRC=$URL_OR_FILE 时保持不动）。
rm -f "$OUTDIR"/input.* "$OUTDIR"/audio.wav

echo "完成 -> $OUTDIR/transcript.txt  (可用 t2s.py 转为简体)"
echo "已自动清理下载媒体与音频中间文件，仅保留 transcript.txt / transcript.srt"
