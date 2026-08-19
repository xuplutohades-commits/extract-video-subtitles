# extract-video-subtitles

一个 Codex / AI Agent 技能（skill）：粘贴任意音视频链接，自动转成简体中文**文章**（不是时间轴字幕）。

把链接丢给 AI，它就会自动完成：**优先提取字幕轨**（在线/内嵌字幕），**没有字幕时才回退 Whisper 语音识别**，再统一做**繁体转简体 → 修正常识性同音错字 → 按内容切段整理成文**，任务结束还会自动清掉占空间的中间文件，只留文字稿。

## 功能

- 支持常见站点与直链：B站、央视、百度、腾讯、YouTube、mp4/mp3 等
- **智能选路**：有字幕轨就直接提取（更快更准省资源），无字幕才走语音识别
- 高准确率中文识别（Whisper small 模型，作为回退方案）
- 自动繁体转简体 + 召唤 AI 基于常识修正人名/地名的同音错字（如“谷牧”误听成“古墓”会改回）
- 输出为连贯段落文章，不是 srt 时间轴
- 跑完自动删除下载的媒体与音频中间文件，不占磁盘

## 安装

解压本项目，把 `extract-video-subtitles` 文件夹整个放进：

```
~/.codex/skills/
```

即 `~/.codex/skills/extract-video-subtitles/` 下应包含 `SKILL.md`、`agents/`、`scripts/`。重启/进入下次对话即可使用。

## 依赖（需在一台普通电脑上装一次）

- [yt-dlp](https://github.com/yt-dlp/yt-dlp)
- [whisper.cpp](https://github.com/ggerganov/whisper.cpp)（`whisper-cli`，CPU 模式，仅回退路线用）
- [ffmpeg](https://ffmpeg.org/)
- Python + [opencc-python-reimplemented](https://pypi.org/project/opencc-python-reimplemented/)（繁转简）
- Whisper 中文模型：`ggml-small.bin`（推荐）或 `ggml-base.bin`

各工具的具体安装与模型下载方法都写在 `extract-video-subtitles/SKILL.md` 的“环境”一节，照着做即可。

## 使用示例

把下面这句发给配好这个 skill 的 AI：

> 请把 https://example.com/video.mp4 转成简体中文文章

操作封装在 `scripts/transcribe.sh`（自动走字幕或语音两条路线）：

```bash
bash <skill_dir>/scripts/transcribe.sh "<url 或本地文件路径>" "<输出目录>"
python3 <skill_dir>/scripts/t2s.py transcript.txt transcript_simplified.txt
```

## 目录结构

```
extract-video-subtitles/
├── SKILL.md            # skill 说明与完整流水线
├── agents/openai.yaml  # 界面显示名与触发提示词
└── scripts/
    ├── transcribe.sh   # 优先字幕→回退语音；下载→提音频→Whisper 转写（自动清理大文件）
    ├── subs2txt.py     # srt/vtt/ass 字幕 → 纯文本
    └── t2s.py          # 繁体转简体
```

## 说明

- 多数在线视频**没有内嵌字幕轨道**时只能走语音识别；有字幕轨（含自动字幕）的会优先直接提取，跳过识别。
- 自动生成字幕同样可能有同音/乱序错误，所以无论哪种来源，后处理都会做常识性修正。
