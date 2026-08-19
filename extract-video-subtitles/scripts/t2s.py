#!/usr/bin/env python3
"""繁体文本 → 简体文本。
用法: t2s.py <输入.txt> [<输出.txt>]   （省略输出时打印到 stdout）
依赖: opencc-python-reimplemented
  pip3 install --user --break-system-packages opencc-python-reimplemented
"""
import sys

try:
    from opencc import OpenCC
except ImportError:
    sys.stderr.write(
        "缺少 opencc。请先运行: "
        "pip3 install --user --break-system-packages opencc-python-reimplemented\n"
    )
    sys.exit(1)

def main():
    if len(sys.argv) < 2:
        sys.stderr.write(__doc__)
        sys.exit(2)
    src_path = sys.argv[1]
    dst_path = sys.argv[2] if len(sys.argv) > 2 else None
    cc = OpenCC("t2s")
    with open(src_path, encoding="utf-8") as f:
        text = f.read()
    out = cc.convert(text)
    if dst_path:
        with open(dst_path, "w", encoding="utf-8") as f:
            f.write(out)
    else:
        sys.stdout.write(out)

if __name__ == "__main__":
    main()
