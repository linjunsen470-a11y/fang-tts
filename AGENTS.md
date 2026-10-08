# Fish Audio 本地工具项目规则

## 当前工作流

本地压缩视频 → 用户上传到 ChatGPT Project 看画面、写稿、审核 → 本地整段 TTS。
用户已授权以主动运行合成命令作为台词确认；不再使用 approved、jobs.yaml 或分镜审批流水线。

- `compress.bat` / `compress_videos.py` 只在本地压缩，不上传、不分析内容，不读取或混合原片音轨。
- `synthesize.bat` / `cli.py` 只合成用户提供的整段 YAML，不自动改稿、分段拼接、生成字幕或对齐视频。
- 除非用户明确要求，Agent 不查看视频、不抽帧、不撰写台词、不调用真实 TTS。
- 按任务读取必要源码。默认不读 input、output（包括 _legacy 历史归档）、.env 或其他房源历史资料；它们是用户数据。
- 不删除或覆盖原片、历史配音、密钥、虚拟环境。生成文件默认防覆盖；覆盖需显式 --overwrite。

## Fish 与文档

- 固定模型 `s2.1-pro-free`，通过 model 请求头发送；默认音色 `5c353fdb312f4888836a9a5680099ef0`，允许用户通过 YAML 的 reference_id 更换单说话人音色。未提供新 ID 时不自行猜测或切换。
- 完整标签、参数和 ChatGPT 指令位于 `chatgpt_project/`，代码标签清单位于 `tag_catalog.py`。
- 使用 S2 方括号语法；未知标签、S1 圆括号标签和不支持的参数在联网前报错，不静默改写文本。
- 口播不要靠停顿标签留白。`tts.breaths` 只在本地把句号、问号、叹号处的气口收到约 0.50 秒，请求前从参数里去掉。
- 标签/参数变更先核对官方文档，同步更新参考文档、代码和测试。不得凭记忆添加参数或自定义标签。
- 密钥只从本地环境读取；不打印、提交或写入 Project 文档。测试默认使用模拟 API。

## 验证

`python -m unittest discover -s tests -v`；文档 YAML 示例纳入离线检查。
FFmpeg 集成测试只使用测试生成的素材，不访问用户原片或真实 API。

官方来源（核对 2026-09-27）：
- https://docs.fish.audio/developer-guide/core-features/emotions
- https://docs.fish.audio/api-reference/endpoint/openapi-v1/text-to-speech
- https://docs.fish.audio/features/text-to-speech
- https://docs.fish.audio/developer-guide/models-pricing/choosing-a-model
- https://fish.audio/zh-CN/blog/fish-audio-s2-fine-grained-ai-voice-control-at-the-word-level/
- https://fish.audio/blog/fish-audio-s2-fine-grained-ai-voice-control-at-the-word-level/
