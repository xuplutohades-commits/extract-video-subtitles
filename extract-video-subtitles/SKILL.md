---
name: extract-video-subtitles
description: 从视频或音频链接提取文字内容并输出为中文文章。当用户粘贴一个音视频链接（B站、央视、百度、腾讯、YouTube，或直链 mp4/mp3 等）希望"转成字幕/文字稿/文章/报告"、或要求对链接直接做语音转写时使用。核心是下载媒体 → 提取音频 → Whisper 中文转写 → 繁体转简体 → 整理成连贯段落。也适用于对已在本机的音视频文件直接转写。
---

# 视频字幕提取

从音视频链接提取文字。注意：多数视频**没有内嵌字幕轨道**，yt-dlp 的 `--write-subs` 抓不到字幕，只能靠语音识别从音频转写。本 skill 固定执行一条已验证的流水线。

## 环境（本机已验证）

- yt-dlp：`/Users/qianxu/Library/Python/3.9/bin/yt-dlp`（不在 PATH，用完整路径）
- whisper-cli：`/opt/homebrew/bin/whisper-cli`（whisper.cpp）。**必须加 `-ng` 用 CPU**——Metal/GPU 在本机部分场景会分配缓冲区失败。
- 模型目录：`/opt/homebrew/opt/whisper-cpp/models/`（已装 `ggml-base.bin`、`ggml-small.bin`）
- ffmpeg/ffprobe：`/opt/homebrew/bin/`
- opencc（繁转简）：Python 3.14 用户目录已装 `opencc-python-reimplemented`，见 `scripts/t2s.py`

**网络注意**：沙盒默认拦截外网。下载媒体、模型等每个联网命令都需 `sandbox_permissions: require_escalated`。国内访问 huggingface.co 会超时，模型镜像用 `https://hf-mirror.com`。

## 工作流程

第 1–3 步（下载 → 提音频 → Whisper 转写）用 `scripts/transcribe.sh` 一键完成：

```bash
bash <skill_dir>/scripts/transcribe.sh "<url 或本地文件路径>" "<输出目录>" [small|base|medium]
```

- 默认 `small` 模型，中文准确率明显优于 base；要更高准确率可换 `medium`（更慢、更占内存）。
- 产出 `transcript.txt`（纯文本）与 `transcript.srt`（带时间轴）于输出目录。
- **脚本末尾会自动清理大文件**：删除它自己下载的媒体（`input.*`）和提取出的 `audio.wav`，只保留小体积（几十 KB）的文字稿。若输入的是用户本地文件，原始文件一概不动。

第 4 步，繁转简，用 `scripts/t2s.py`：

```bash
python3 <skill_dir>/scripts/t2s.py transcript.txt transcript_simplified.txt
```

第 5–6 步由语言模型手工完成，不写死在脚本里：

1. 丢弃空白、纯音乐/歌词标记行（如 `(音樂)`、`(詞曲:...)`）。
2. 用**常识与上下文**修正同音/近音错字，重点是**人名、地名、固定成语、专有词**。举例：`古墓`→`谷牧`、`坑槍`→`踉蹌`、`十一屆三中懸會`→`十一屆三中全會`、`波蘭壯闊`→`波瀾壯闊`。只有当正确写法十分确定时才改，保留原句措辞，不改写句子内容。
3. 把相邻短句按语义合并成段，按内容节点（时间、地点、话题切换）切分段落，去掉时间轴，组织成一篇连贯的中文文章或报告。
4. 交给用户一篇简体中文文稿；用户需要时可另存 `.md`。

第 7 步（强制收尾）——**清理工作目录**：

- 交给用户文章后，检查输出目录里是否还残留**大体积**的中间文件：下载的媒体（`input.*`/`*.mp4`/`*.mp3`/`*.m4a` 等）、`audio.wav`、其他视频/音频拷贝。**一律删除**，只保留文字产物（`transcript.txt`、`transcript.srt`、`*_simplified.txt`、以及交付的 `.md` 文章）。
- 这是**每次任务必做**的固定步骤，防止反复下载的视频/音频占满磁盘。
- 删之前用 `ls -lh` 确认只清理目标目录里的中间文件，绝不 `rm -rf` 用户原始素材或工作区根目录。

## 输出约定

- 用户只要"文字"时，默认输出为连贯的**简体中文文章**（段落式），不是 srt 时间轴。
- 保留原话内容与信息，只做简体化和明显错字修正，不自行添加观点。
- 整段纯音乐或与内容无关的占位标记直接剔除。
- 任务结束前完成临时文件清理并简要告知用户删了哪些。
