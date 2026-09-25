# Fish Audio TTS

使用 `tts.yaml` 配置文本和合成参数，在终端运行 Fish Audio Python SDK，并把生成的音频保存到本地。项目默认使用免费测试模型 `s2.1-pro-free`。

当前音色固定为 Fish Audio API Playground 示例中的 reference ID：`5c353fdb312f4888836a9a5680099ef0`。需要更换时直接编辑 YAML 中的 `reference_id`。

## 安装

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

在 `.env` 中配置 API key：

```dotenv
FISH_AUDIO_API_KEY=sk-fish-...
```

也兼容官方环境变量名 `FISH_API_KEY`。

## 合成

```powershell
python cli.py
```

默认读取项目根目录的 `tts.yaml`。也可以指定另一份 YAML：

```powershell
python cli.py .\examples\chapter.yaml
```

程序会在 terminal 打印模型、固定音色、文本、请求状态和输出音频大小；API key 不会写入日志。`output` 中的相对路径以 YAML 文件所在目录为基准。

## 配置

`tts.yaml` 提供官方 TTS 配置字段，包括格式和采样率、MP3/Opus 码率、文本规范化、分块和延迟、语速音量、top-p、temperature、重复惩罚、token 上限以及 chunk 条件控制。详细字段和取值见 [Fish Audio TTS 文档](https://docs.fish.audio/features/text-to-speech) 与 [TTSConfig 字段参考](https://docs.fish.audio/api-reference/sdk/python/types)。`references` 是即时语音克隆使用的参考音频列表；本项目使用固定的 `reference_id`，因此不传该字段。
