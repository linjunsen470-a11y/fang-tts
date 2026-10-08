# Fish Audio 配音输出规范

生成配音配置时遵循以下格式。默认交付纯台词、独立的配音台词和完整 YAML；纯台词供人阅读，`tts.txt` 中的配音台词是实际需要朗读的文字及表达标签，YAML 通过 `text_file` 指向该文件。

## 模型与默认音色

| 项目 | 约定 |
| --- | --- |
| 模型 | `s2.1-pro-free` |
| 默认音色 ID | `5c353fdb312f4888836a9a5680099ef0`；可替换为用户指定的其他音色 ID |
| 说话人 | 单说话人 |
| 默认语言与风格 | 中文，克制、温和、清晰、可信 |

模型保持 `s2.1-pro-free`。音色由 `reference_id` 指定，可以更换；仅采用用户明确提供的 ID，不根据风格描述猜测 ID，不切换为参考音频克隆。

每份 YAML 都显式写出 `model` 和 `reference_id`，让当前声音选择一目了然。未指定音色时使用默认值；同一任务的后续修改沿用已经选定的音色。

## YAML 内容

根节点使用 `model`、`reference_id`、`text_file`、`output`、`tts`。兼容旧的内嵌 `text`，但 `text` 和 `text_file` 必须且只能出现一个。不要自行添加其他根字段。

- `text_file`：默认 `tts.txt`，用户指定其他名称时沿用。它是本地工具的文件路径字段，不是 Fish API 参数；相对路径以 YAML 所在文件夹为基准。对应文件使用 UTF-8（允许 BOM），正文与纯台词一致，只额外插入合法的英文方括号标签，无需 YAML 缩进。标题、解释、镜头时间、舞台说明、估算时长均不得混入其中。
- `text`：仅在用户要求内嵌格式时使用 `|-` 多行文本，并省略 `text_file`；正文与标签要求相同。不要把文件路径写进 `text`，否则它会被当成台词朗读。
- `output`：使用 `output/房源代号.mp3` 形式的相对路径。优先使用用户给出的代号；没有代号时可依据文件名命名，无法确定时使用 `narration`。代号只用于标识，不可据此推断房源事实。修改版本可加 `-v2` 等后缀。
- `tts`：配音参数。`prosody` 必须是其中的嵌套对象。数字写成数值，布尔写成 `true` / `false`，不要写成带引号的字符串。
- `tts.breaths`：仅本地使用。口播成片写 `true`。整段一次合成之后，把句号、问号、叹号处的气口收到约 0.50 秒。该字段在请求前删除，不会发给 Fish API。省略时不调整气口。

默认采用下面的参数组合；用户未要求调整时保持一致。例句仅用于展示格式，不属于当前任务。

**配音台词（`tts.txt`）**

```text
[calm] 我们先从这里开始，慢慢看看眼前的空间。
```

**配音 YAML**

```yaml
model: s2.1-pro-free
reference_id: "5c353fdb312f4888836a9a5680099ef0"
text_file: tts.txt
output: output/example.mp3
tts:
  breaths: true
  format: mp3
  mp3_bitrate: 128
  normalize: true
  chunk_length: 200
  latency: balanced
  prosody:
    speed: 1.0
    volume: 0.0
    normalize_loudness: true
  temperature: 0.7
  top_p: 0.7
```

YAML 代码块外分别给出纯台词和完整配音台词，不把纯台词另存为 YAML 字段。不写审批状态、分镜任务、字幕时间轴或多余注释；不要使用省略号代替应输出的内容。回复中无需解释字段和生成流程，除非用户明确询问。

## 参数调整规则

- `reference_id` 选择声音身份；语速、音量和情绪标签调整表达方式。它们不是同一个控制项。
- 默认值用于没有额外要求的任务；用户给出合法数值时按其指定值输出。
- 用户以自然语言要求“稍慢一点”“音量高一点”“更平静”时，将需求落实到相应的语速、音量或标签，并用一句话说明改动。不要求用户必须给出数字。
- `temperature` 和 `top_p` 控制采样变化，不是音高、年龄或性别开关；没有对应需求时保留当前值。不要虚构 `pitch`、`gender`、`age` 等参数。
- 用户要求提高或降低音调时，在配音文本中使用 `[pitch up]` 或 `[pitch down]`，不添加 `tts.pitch` / `tts.prosody.pitch`。它们只引导音高变化，不代表固定半音数；只调音高时保持其余参数不变。局部快慢可用 `[speaking fast]` / `[speaking slowly]`，整段语速使用 `prosody.speed`。完整标签见《Fish Audio 语气与标签》。
- 修改配置后输出完整 YAML；未涉及的参数沿用当前版本。参数超出下表范围时说明范围，不静默改成另一个值。

## 常用参数

| 参数 | 本项目采用值 | 可用范围与作用 |
| --- | --- | --- |
| `breaths` | `true` | 仅本地；`true` / `false`。口播收到约 0.50 秒句末气口，不发给接口 |
| `format` | `mp3` | `mp3`、`wav`、`pcm`、`opus`；输出路径扩展名须匹配 |
| `mp3_bitrate` | `128` | `64`、`128`、`192`，单位 kbps，仅 MP3 |
| `normalize` | `true` | 文本规范化，不是音量标准化 |
| `chunk_length` | `200` | 整数 100–300；控制语音服务处理的文本块长度 |
| `latency` | `balanced` | `low`、`balanced`、`normal` |
| `prosody.speed` | `1.0` | 0.5–2.0，语速倍率 |
| `prosody.volume` | `0.0` | −20–20 dB，音量调整 |
| `prosody.normalize_loudness` | `true` | 音量标准化 |
| `temperature` | `0.7` | 0–1，表达变化度 |
| `top_p` | `0.7` | 0–1，采样参数 |

这些是本项目的写稿配音约定。官方 `chunk_length` 默认值为 300，`latency` 默认值为 normal；本项目分别使用 200 和 balanced。`normalize_loudness: true` 来自官方请求示例，不将其表述为已确认的接口默认值。

调整语速会改变声音表现和时长，但不能保证精确匹配视频。用户给出实际音频时长后，可以据此调整文案；不要把尚未生成的音频时长当成测量结果。

## 可选参数

仅在当前需求确实涉及这些控制时使用；普通成稿不必添加。

| 参数 | 可用值 / 官方默认 | 使用含义 |
| --- | --- | --- |
| `sample_rate` | 整数或 `null`；null 使用格式默认 | 采样率，Hz，须匹配下面的格式表 |
| `opus_bitrate` | −1000、24000、32000、48000、64000 | 仅 Opus，单位 bps；−1000 为自动，常用 32000 |
| `max_new_tokens` | 正整数；默认 1024 | 每文本块生成 token 上限 |
| `repetition_penalty` | 正数；默认 1.2 | 大于 1 可抑制重复 |
| `min_chunk_length` | 整数 0–100；默认 50 | 开始新块前的最小字符数 |
| `condition_on_previous_chunks` | 布尔；默认 true | 使用前文音频保持声音连贯 |
| `early_stop_threshold` | 0–1；默认 1 | 提前结束阈值 |
| `features` | 可选字符串数组；已列出 `quality-guard` | 具体可用性由语音服务决定，不主动添加 |
| `pronunciation_dictionary` | 可选对象 | 用于专名读音；仅在用户提供已确认的官方词典对象时原样采用，不臆造内部字段 |

| 格式 | 可用采样率（Hz） | 默认采样率 |
| --- | --- | --- |
| MP3 | 32000、44100 | 44100 |
| WAV / PCM | 8000、16000、24000、32000、44100 | 44100 |
| Opus | 48000 | 48000 |

WAV / PCM 为单声道、16-bit；PCM 是裸音频数据，日常交付优先 MP3。只写当前格式需要的码率字段。

## 输出边界

- 不生成 `references`、多说话人配置或自定义自由标签。
- 不生成 `tag_compatible_mode`；当前已核实字段不包含这一项。
- 不加入密钥、认证信息、网络请求代码、命令行或文件操作说明。
- 参数名称、取值和单位以本规范为准。规范之外的参数有明确需求时再核实，不为每次写稿重复联网。

知识依据核对日期：2026-09-27。[Fish TTS 参数](https://docs.fish.audio/api-reference/endpoint/openapi-v1/text-to-speech)、[语音生成说明](https://docs.fish.audio/features/text-to-speech)、[S2 行内控制](https://fish.audio/zh-CN/blog/fish-audio-s2-fine-grained-ai-voice-control-at-the-word-level/)。
