#!/usr/bin/env python3
"""字幕文件(srt/vtt/ass) → 纯文本。
用法: subs2txt.py <输入字幕> [<输出.txt>]   （省略输出时打印到 stdout）
自动识别 srt / vtt / ass，去掉时间轴与样式标记，合并成连续文本。
"""
import re
import sys

def clean_inline(text: str) -> str:
    # 去掉 vtt 的 <c>...</c>、<v Speaker>、<b>/<i>、ass 的 {\an8}、vtt 的 {\an8}
    text = re.sub(r"\{[^}]*\}", "", text)
    text = re.sub(r"<[^>]+>", "", text)
    # ass 换行符
    text = text.replace(r"\N", "\n").replace(r"\n", "\n")
    return text.strip()

def parse_srt(raw: str):
    for block in re.split(r"\n\s*\n", raw):
        lines = [l for l in block.split("\n") if l.strip()]
        if not lines:
            continue
        # 去掉区块序号与时间轴行
        lines = [l for l in lines if "-->" not in l and not l.strip().isdigit()]
        txt = clean_inline("\n".join(lines))
        if txt:
            yield txt

def parse_vtt(raw: str):
    for block in re.split(r"\n\s*\n", raw):
        lines = [l for l in block.split("\n") if l.strip()]
        if not lines:
            continue
        head = lines[0]
        if head.startswith(("WEBVTT", "STYLE", "NOTE", "REGION")):
            continue
        # 去掉 cue 时间轴（可能多行时间轴）
        while lines and "-->" in lines[0]:
            lines.pop(0)
        lines = [l for l in lines if "-->" not in l]
        txt = clean_inline("\n".join(lines))
        if txt:
            yield txt

def parse_ass(raw: str):
    for line in raw.split("\n"):
        if not line.startswith("Dialogue:"):
            continue
        fields = line[len("Dialogue:"):].split(",", 9)
        if len(fields) < 10:
            continue
        txt = clean_inline(fields[9])
        if txt:
            yield txt

def main():
    if len(sys.argv) < 2:
        sys.stderr.write(__doc__)
        sys.exit(2)
    src = sys.argv[1]
    dst = sys.argv[2] if len(sys.argv) > 2 else None
    with open(src, "r", encoding="utf-8-sig", errors="replace") as f:
        raw = f.read()
    first = raw.strip()
    if first.startswith("WEBVTT"):
        items = list(parse_vtt(raw))
    elif "Dialogue:" in raw:
        items = list(parse_ass(raw))
    else:
        items = list(parse_srt(raw))
    out = "\n".join(items).strip() + "\n"
    if dst:
        with open(dst, "w", encoding="utf-8") as f:
            f.write(out)
    else:
        sys.stdout.write(out)

if __name__ == "__main__":
    main()
