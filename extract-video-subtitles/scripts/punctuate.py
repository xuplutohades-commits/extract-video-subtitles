#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""为无标点的语音转写文本补全中文标点（规则打底，供模型复核修正）。

用法:
  python3 punctuate.py <输入.txt> [输出.txt] [--join]

参数:
  --join    补标点后按停顿合并为自然段（每段约 140–420 字）

输入约定:
  - 每行 = 一个语音/字幕片段（whisper 的 transcript.txt、subs2txt.py 产物均可）。
  - 字幕轨文本通常自带标点：某行已以标点结尾时原样保留，不重复添加。
  - 繁体文本请先经 scripts/t2s.py 转简体再调用本脚本。

标点规则（第一遍打底，最终由模型在整理段落时按语义复核修正）:
  1. 疑问：句尾 吗/呢/么，或短句含 是不是/有没有/为什么/怎么/什么/哪里/多少 等 → ？
  2. 感叹：句首 哇/哎呀/天哪/哈喽/嗨 等 → ！
  3. 句尾语气词（了/的/啦/哦/嘛/呗/着/过…）→ 。
  4. 句首承接连词（但是/然后/所以/因为/其实…）→ 前面补 ，
  5. 默认：片段较长（≥12字）→ 。；中等（6–11字）→ ，；过短（≤5字）→ 不标点、与下句衔接。
"""
import re
import sys

QUES_END = ("吗", "呢", "么")
QUES_MID = (
    "是不是", "有没有", "能不能", "要不要", "会不会", "该不该", "对不对",
    "为什么", "怎么", "什么", "哪里", "哪儿", "多少", "干啥", "为啥",
    "谁", "啥", "干嘛", "干什么",
)
EXCL_START = ("哇", "哎呀", "哎呦", "哎哟", "天哪", "天呐", "天啊",
              "哈喽", "嗨", "哟", "呦", "嚯", "哇塞")
END_PARTICLE = ("了", "的", "吧", "啊", "呀", "啦", "哦", "嘛", "呗",
                "着", "过", "而已", "罢了", "才行", "得了")
CONNECTOR = (
    "但是", "可是", "不过", "然后", "所以", "因为", "而且", "如果", "虽然",
    "其实", "毕竟", "反正", "后来", "接着", "另外", "还有", "再说", "比如",
    "例如", "总之", "因此", "于是", "然而", "就算", "即使", "哪怕", "只要",
    "只有", "除了", "包括", "以及", "并且", "或者", "同时", "况且", "何况",
    "当然", "确实", "说实话", "实际上", "终究", "到底", "终于", "难怪",
    "怪不得", "结果", "之后", "也就是说", "换句话说",
)
BACKCHANNEL = ("嗯", "哦", "噢", "对", "好", "是", "嗯嗯", "对对", "行", "可以")


def clean_ws(s: str) -> str:
    """去掉中文行内空格（数字之间保留）。"""
    s = s.replace("\u3000", " ")
    s = re.sub(r"(?<=\d) (?=\d)", "\x00", s)
    s = s.replace(" ", "")
    return s.replace("\x00", " ")


def end_punct(seg: str, prev_end: str):
    """返回 (补标点后的行文本, 行尾标点或'')。"""
    s = clean_ws(seg).strip()
    if not s:
        return "", ""
    if s[-1] in "。？！，、；：…—～!?.,;:!?":
        return s, s[-1]
    tail = ""
    # 疑问
    if s.endswith(QUES_END):
        tail = "。" if s.endswith("着呢") else "？"
    elif s.endswith("吧") and len(s) <= 6:
        tail = "？"
    elif len(s) <= 14 and any(w in s for w in QUES_MID):
        tail = "？"
    # 感叹
    elif s.startswith(EXCL_START):
        tail = "！"
    # 句尾语气词
    elif s.endswith(END_PARTICLE):
        tail = "。"
    # 单字/双字回馈
    elif s in BACKCHANNEL:
        tail = "。"
    # 默认长度规则
    else:
        if len(s) >= 12:
            tail = "。"
        elif len(s) >= 6:
            tail = "，"
        else:
            tail = ""
    # 句首承接连词 → 前缀逗号（仅当上句无任何标点、纯顺接时才补，避免“，，”双逗号）
    prefix = ""
    if s.startswith(CONNECTOR) and prev_end == "":
        prefix = "，"
    return prefix + s + tail, tail


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    join_mode = "--join" in sys.argv
    if not args:
        sys.stderr.write(__doc__)
        sys.exit(2)
    src = args[0]
    dst = args[1] if len(args) > 1 else None
    with open(src, encoding="utf-8") as f:
        text = f.read()

    out_lines = []
    prev_end = ""
    for ln in text.splitlines():
        out, prev_end = end_punct(ln, prev_end)
        if out:
            out_lines.append(out)

    if join_mode:
        paras, cur = [], ""
        for ln in out_lines:
            if cur and len(cur) >= 140 and ln.endswith(("。", "！", "？")):
                paras.append(cur)
                cur = ln
            elif cur and len(cur) + len(ln) > 420:
                paras.append(cur)
                cur = ln
            else:
                cur += ln
        if cur:
            paras.append(cur)
        result = "\n\n".join(paras) + "\n"
    else:
        result = "\n".join(out_lines) + "\n"

    if dst:
        with open(dst, "w", encoding="utf-8") as f:
            f.write(result)
    else:
        sys.stdout.write(result)


if __name__ == "__main__":
    main()
