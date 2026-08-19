#!/usr/bin/env bash
# 把转写/解析结果存入本地知识库（每次交付后自动调用）。
# 用法: kb_save.sh "<来源(URL或文件路径)>" "<路线: subtitles|voice|text>" "<短标题>" "<文字文件.md>"
# 环境变量 KB_ROOT 可覆盖知识库目录（默认 ~/Documents/字幕知识库），测试时用。
set -euo pipefail

KB_ROOT="${KB_ROOT:-$HOME/Documents/字幕知识库}"
SOURCE="$1"
MODE="$2"
TITLE="$3"
TEXTFILE="$4"

[[ -f "$TEXTFILE" ]] || { echo "错误：文字文件不存在: $TEXTFILE" >&2; exit 1; }
mkdir -p "$KB_ROOT"

DATE="$(date +%Y-%m-%d)"
WORDS="$(wc -m < "$TEXTFILE" | tr -d ' ')"
SLUG="$(printf '%s' "$TITLE" | tr -s '[:space:] ' '-' | sed 's/[\\/:*?"<>|]//g' | cut -c1-40)"
SLUG="${SLUG:-untitled}"

# 同一来源（相同 URL/路径）覆盖：按头部第 3 行 "来源: <...>" 精确匹配
TARGET=""
for f in "$KB_ROOT"/*.md; do
  [[ -f "$f" ]] || continue
  if awk -v s="$SOURCE" 'NR==3 && $0=="来源: <" s ">" {found=1} END{exit found?0:1}' "$f"; then
    TARGET="$f"
    break
  fi
done

# 不同来源：新建文件；同日同标题冲突时自动加 -2/-3 后缀
if [[ -z "$TARGET" ]]; then
  BASE="$KB_ROOT/${DATE}_${SLUG}"
  TARGET="$BASE.md"
  N=2
  while [[ -e "$TARGET" ]]; do
    TARGET="${BASE}-${N}.md"
    N=$((N+1))
  done
fi

{
  echo "---"
  echo "标题: $TITLE"
  echo "来源: <$SOURCE>"
  echo "日期: $DATE"
  echo "路线: $MODE"
  echo "字数: $WORDS"
  echo "---"
  echo ""
  cat "$TEXTFILE"
} > "$TARGET"

# 知识库 README（首次入库时自动创建）
if [[ ! -f "$KB_ROOT/README.md" ]]; then
  cat > "$KB_ROOT/README.md" <<'EOREADME'
# 字幕/文字知识库

由 extract-video-subtitles skill 自动维护：每次转写或文字解析的结果都会存入本目录。

## 文件命名

`YYYY-MM-DD_短标题.md`

## 文件头部

每篇开头 5 行元信息：标题 / 来源（URL 或文件路径）/ 日期 / 处理路线 / 字数。
路线取值：subtitles=字幕轨，voice=语音识别，text=本地文字文件直接解析。

## 覆盖规则

同一来源（相同 URL 或相同本地路径）再次处理时覆盖原条目，避免重复入库。

## 使用

- 浏览：直接打开本目录下的 md 文件。
- 检索：终端运行 `rg "关键词" ~/Documents/字幕知识库`，或在对话中让 AI 检索。
EOREADME
fi

echo "已入库: $TARGET"
