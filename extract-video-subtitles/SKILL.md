---
name: extract-video-subtitles
description: 从视频或音频链接提取文字内容并输出为中文文章。当用户粘贴一个音视频链接（B站、央视、百度、腾讯、YouTube，或直链 mp4/mp3 等）希望"转成字幕/文字稿/文章/报告"、或要求对链接直接做语音转写时使用。核心流程：(1) 优先提取内嵌/在线字幕轨；(2) 无字幕时才回退 Whisper 语音识别；(3) 统一做繁体转简体、修正同音错字、整理成连贯段落文章。也适用于对已在本机的音视频文件直接处理。
---

# 视频字幕提取

从音视频链接提取文字。**优先使用字幕轨**（在线字幕或内嵌字幕），只有确认**没有字幕**时才回退到 Whisper 语音识别。两条路线之后都做同样的后处理：繁转简 → 常识性错字修正 → 按内容切段整理成文。

## 环境（本机已验证）

- yt-dlp：`/Users/qianxu/Library/Python/3.9/bin/yt-dlp`（不在 PATH，用完整路径）
- whisper-cli：`/opt/homebrew/bin/whisper-cli`（whisper.cpp）。**必须加 `-ng` 用 CPU**——Metal/GPU 在本机部分场景会分配缓冲区失败。
- 模型目录：`/opt/homebrew/opt/whisper-cpp/models/`（已装 `ggml-base.bin`、`ggml-small.bin`）
- ffmpeg/ffprobe：`/opt/homebrew/bin/`
- opencc（繁转简）：Python 3.14 用户目录已装 `opencc-python-reimplemented`，见 `scripts/t2s.py`

**网络注意**：沙盒默认拦截外网。下载媒体、模型、抓字幕等每个联网命令都需 `sandbox_permissions: require_escalated`。国内访问 huggingface.co 会超时，模型镜像用 `https://hf-mirror.com`。

## 工作流程

第 1–3 步用 `scripts/transcribe.sh` 一键完成（脚本内部自动判断走字幕还是语音）：

```bash
bash <skill_dir>/scripts/transcribe.sh "<url 或本地文件路径>" "<输出目录>" [small|base|medium]
```

### 优先路线 A：字幕轨（更快、更准、省资源）

脚本先尝试拿字幕，不下载视频本体：

- **在线链接**：用 yt-dlp 的 `--skip-download --write-subs --write-auto-subs --sub-langs all` 直接抓字幕轨（含自动生成字幕），不下载媒体。抓到后 `subs2txt.py` 转成纯文本 `subs.txt`。
- **本地文件**：用 ffprobe 探测内嵌字幕流，有则用 ffmpeg 提取为 `subtitle.srt`，再转纯文本 `subs.txt`。

有字幕时**产出**：`subs.txt`（纯文本，供后处理）＋ 原始字幕文件。此时**不跑语音识别**。

### 回退路线 B：语音识别

只有确认**没有任何字幕轨**时才走到这步：

1. 下载最佳音轨（`bestaudio`，不带画面省流量）
2. ffmpeg 转 16kHz 单声道 WAV
3. Whisper 中文转写（`-ng -l zh`），产出 `transcript.txt` + `transcript.srt`
4. 脚本末尾自动删除它自己下载的媒体与 WAV，只留文字稿；用户传入的本地文件一概不动

### 统一后处理（第 4–6 步，两种路线共用）

1. **繁转简**：`python3 <skill_dir>/scripts/t2s.py <文本> <简体输出>`（OpenCC）。
2. **修正同音/近音错字**：用**常识与上下文**修正，重点是**人名、地名、固定成语、专有词**。举例：`古墓`→`谷牧`、`坑槍`→`踉蹌`、`十一屆三中懸會`→`十一屆三中全會`、`波蘭壯闊`→`波瀾壯闊`。字幕轨的错字通常比语音识别少，但**自动生成字幕（auto-caption）也会有同音/乱序错误**，仍需此步。只有在正确写法十分确定时才改，保留原句措辞，不改写内容。
3. **整理成文**：把相邻短句按语义合并成段，按内容节点（时间、地点、话题切换）切分段落，去掉时间轴，组织成一篇连贯的中文文章或报告。
4. 交给用户一篇简体中文文稿；需要时可另存 `.md`。

### 第 7 步（强制收尾）——清理工作目录

- 交付文章后检查输出目录，**删除所有大体积中间文件**：下载的媒体（`input.*`/`*.mp4`/`*.mp3`/`*.m4a` 等）、`audio.wav`。只保留文字产物（`subs.txt`、`transcript.txt/.srt`、`*_simplified.txt`、交付的 `.md`）。
- 字幕文件（srt/vtt/ass）体积小，可保留作参考。
- 删前用 `ls -lh` 确认只清理目标目录，绝不 `rm -rf` 用户原始素材或工作区根目录。

## 输出约定

- 用户只要"文字"时，默认输出为连贯的**简体中文文章**（段落式），不是 srt 时间轴。
- 保留原话内容与信息，只做简体化和明显错字修正，不自行添加观点。
- 整段纯音乐或与内容无关的占位标记直接剔除。
- 交付时说明本次走的是**字幕轨**还是**语音识别**（语音识别结果更需人工校对）。
- 任务结束前完成临时文件清理并简要告知用户删了哪些。
