#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""为无标点的语音转写文本补全中文标点（流式合并打底，供模型复核修正）。

用法:
  python3 punctuate.py <输入.txt> [输出.txt] [--join]

输入:
  - 每行 = 一个语音/字幕片段（whisper 的 transcript.txt、subs2txt.py 产物均可）。
  - 字幕轨文本通常自带标点：某行已以标点结尾时原样保留，不重复添加。
  - 繁体文本请先经 scripts/t2s.py 转简体再调用本脚本。

v2 关键变化:
  旧版逐行判断、按"行长≥12字就加句号"兜底，whisper 恰好在句中切行时会
  把一句拦腰截断（如 "采访过的|最年轻的一位嘉宾" 被断成两句）。
  新版先把所有片段拼成连续文本流，逐边界判断；判断依据是"这段是否明显
  是完整一句/一个停顿"，而不是"这行有多长"。

打底规则:
  1. 问句证据: 段尾 吗/呢/么/吧(短段)，或短段(≤16字)含 是不是/有没有/能不能/
     会不会/为什么/怎么/什么/哪里/多少/谁/啥/干嘛 等 → ？
  2. 感叹证据: 段首感叹词(哇/哎呀/天哪/哈喽/嗨/哟/嚯) 且整段 ≤12 字 → ！
  3. 纯回馈词(嗯/哦/噢/对/好/是/行/可以/对对/嗯嗯…)单独立段 → 。
  4. 强句尾语气词(了/啦/哦/嘛/呗/着呢/啊/呀/吧/吼/哟/喽/唉) → 大概率句终，加 。
     例外: 下段以顺接/递进成分开头（因为/然后/所以/但是/不过/而且/如果/其实/
     就是/再/又/还/也/都/更/最/一/像/被/把/在/到/从/跟/和/与/对/让/给/是/有/
     没/不/挺/很/真/就/那/这 等）且整段偏短时，改用逗号衔接，避免把话切断。
  5. 弱句尾(的/过/着/得/地/个/成…)或一般中短段 → 默认逗号；极短(≤3字)且无
     任何证据 → 不标点、直接与下句并连。
  6. 已有标点的段尾原样保留。
  7. 兜底原则: 宁可多用逗号，绝不拦腰断句——不再按"长度≥12加句号"。

--join 分段:
  在句号/问号/叹号之后、累计 180–450 字处分段；段首若以承接连词开头，
  强制并入上一段，保证段落不从小词起头。
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
STRONG_END = ("了呢", "着呢", "了吧", "了吗", "了吗", "了呀", "了啦",
              "了", "啦", "哦", "嘛", "呗", "吧", "啊", "呀", "哟", "呦",
              "吼", "喽", "唉", "诶", "哈")
WEAK_END = ("的", "过", "着", "得", "地", "个", "成", "完", "住", "走", "来",
            "去", "上", "下", "出", "进", "回", "起", "开", "到", "给", "出")
CONTINUE_START = (
    "因为", "然后", "所以", "但是", "可是", "不过", "而且", "如果", "虽然",
    "其实", "就是", "再说", "另外", "还有", "再说", "后来", "接着", "于是",
    "然而", "就算", "哪怕", "只要", "除了", "包括", "以及", "并且", "或者",
    "同时", "何况", "当然", "确实", "反正", "毕竟", "到底", "终于", "结果",
    "之后", "再", "又", "还", "也", "都", "更", "最", "很", "挺", "真",
    "就", "一", "像", "被", "把", "在", "到", "从", "往", "跟", "和", "与",
    "对", "让", "给", "是", "有", "没", "不", "那", "这", "它", "她", "他",
)
BACKCHANNEL = ("嗯", "哦", "噢", "对", "好", "是", "嗯嗯", "对对", "行", "可以",
               "对对对", "嗯嗯嗯", "好吧", "好的", "是啊", "对啊", "没错", "当然")


def clean_ws(s: str) -> str:
    """去掉中文行内空格（数字之间保留）。"""
    s = s.replace("\u3000", " ")
    s = re.sub(r"(?<=\d) (?=\d)", "\x00", s)
    s = s.replace(" ", "")
    return s.replace("\x00", " ")


def decide_end(s: str, nxt: str) -> str:
    """根据当前段与下一段，决定段尾标点。返回 '' 表示不标点。"""
    if not s:
        return ""
    if s[-1] in "。？！，、；：…—～!?.,;:!?":
        return ""
    # 1) 问句
    if s.endswith(QUES_END):
        return "？"
    if s.endswith("吧") and len(s) <= 8:
        return "？"
    if len(s) <= 16 and any(w in s for w in QUES_MID):
        return "？"
    # 2) 感叹
    if s.startswith(EXCL_START) and len(s) <= 12:
        return "！"
    # 3) 纯回馈
    if s in BACKCHANNEL and len(s) <= 4:
        return "。"
    # 4) 强句尾语气词
    if s.endswith(STRONG_END):
        if nxt and nxt.startswith(CONTINUE_START) and len(s) <= 20:
            return "，"
        return "。"
    # 5) 弱句尾 / 一般段
    if s.endswith(WEAK_END):
        # 弱句尾绝不加句号；下一段若小词顺接则直接用逗号，否则也不标点
        if len(s) >= 5:
            return "，"
        return ""
    if len(s) >= 5:
        return "，"
    return ""


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

    segs = []
    for ln in text.splitlines():
        s = clean_ws(ln).strip()
        if s:
            segs.append(s)

    # 拼接为连续文本流：逐段决定尾标点，下一段原样衔接
    parts = []
    for i, s in enumerate(segs):
        nxt = segs[i + 1] if i + 1 < len(segs) else ""
        punct = decide_end(s, nxt)
        parts.append(s + punct)
    stream = "".join(parts)

    if join_mode:
        # 分段: 在句号/问号/叹号之后成段，180–450 字一档
        paras, cur = [], ""
        for seg in re.split(r"(?<=[。？！])", stream):
            piece = seg
            if not piece:
                continue
            if cur and len(cur) >= 180 and piece.rstrip("。？！") and not piece.startswith(CONTINUE_START):
                paras.append(cur)
                cur = piece
            elif cur and len(cur) + len(piece) > 450:
                paras.append(cur)
                cur = piece
            else:
                cur += piece
        if cur.strip():
            paras.append(cur)
        result = "\n\n".join(p.strip() for p in paras if p.strip()) + "\n"
    else:
        result = stream + "\n"

    if dst:
        with open(dst, "w", encoding="utf-8") as f:
            f.write(result)
    else:
        sys.stdout.write(result)


if __name__ == "__main__":
    main()
