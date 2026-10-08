# Fish Audio 语气与标签

为旁白添加表达标签时，遵循以下规则。标签只出现在配音台词文件（由 YAML 的 `text_file` 指定）或旧格式的内嵌 `text` 中，纯台词不含标签。固定模型为 `s2.1-pro-free`，使用 S2 方括号语法。

## 模型能力与项目清单

官方说明 `s2.1-pro-free` 与 `s2.1-pro` 使用同一模型；S2/S2.1 支持自然语言方括号提示，并不只有固定的 71 个标签。官方 S2 中文指南明确列出 `[pitch up]`、`[pitch down]`，英文指南也以 `[pitch up]` 展示自然语言控制。结合 S2.1 的语法说明，这些提示适用于本项目固定模型。依据见文末官方来源。

本项目继续采用已核实清单：原有 71 个标签加上本次收录的 27 个，共 **98 个**。这是本地校验范围，不是模型能力上限；清单外标签仍在联网前报错。官方中英文指南的示例表不同，本清单收录两者明确列出的补充标签。文档核实不等于已对当前音色做过实际合成试听。

## 选择与放置

- 先写好自然的台词，再按表达需要选择标签。没有明确作用时不添加，不把标签数量当作表现力。
- 情绪通常放在句首，每句最多一个主要情绪。房产讲解优先少量使用 `[calm]`、`[confident]` 或 `[relaxed]`。
- 需要温和表达时可使用 `[soft tone]`；强调放在要强调的词句之前，例如“这里是[emphasis]窗边的位置。”。只有正文确有强调重点时才使用。
- 口播成片不要使用 `[pause]`、`[long pause]`、`[break]`、`[long-break]`、`[slight pause]`、`[short pause]`。当前音色几乎不执行这些标签；若按标签拆开重合成，每句都会重新起音。同一口气里的分句用逗号连着写。一个卖点说完再用句号、问号或叹号。`tts.breaths: true` 时，本地在整段一次合成之后，把句号、问号、叹号处的气口收到约 0.50 秒：原来更长的空白会剪短，不够的才用本条音频的底噪补上。对齐位置仍在出字就跳过。0.3 秒以下听起来像没有换气。
- 用户要求音调升高或降低时，可在相应词句前使用 `[pitch up]` 或 `[pitch down]`。不要把音高与音量、语速或更换音色混为一谈。
- 不堆叠相互冲突的情绪。默认不添加笑声、哭声、呻吟、喘息、鼾声、歌唱、人群或环境效果；只有用户明确要求且语境合适时才考虑。
- 只使用下表的 98 个标签，严格保留英文拼写、大小写和空格。不要自行翻译、缩写或添加自由描述标签。
- 不使用旧版 S1 的 `(happy)` 等圆括号标签，也不把“停两秒”“轻声说”等舞台说明写入正文。

## 基础情绪（24）

| 标签 | 中文含义 |
| --- | --- |
| `[happy]` | 开心 |
| `[sad]` | 悲伤 |
| `[angry]` | 生气 |
| `[excited]` | 兴奋 |
| `[calm]` | 平静 |
| `[nervous]` | 紧张 |
| `[confident]` | 自信 |
| `[surprised]` | 惊讶 |
| `[satisfied]` | 满意 |
| `[delighted]` | 欣喜 |
| `[scared]` | 害怕 |
| `[worried]` | 担心 |
| `[upset]` | 难过 |
| `[frustrated]` | 受挫 |
| `[depressed]` | 低落 |
| `[empathetic]` | 共情 |
| `[embarrassed]` | 尴尬 |
| `[disgusted]` | 厌恶 |
| `[moved]` | 感动 |
| `[proud]` | 自豪 |
| `[relaxed]` | 放松 |
| `[grateful]` | 感激 |
| `[curious]` | 好奇 |
| `[sarcastic]` | 讽刺 |

## 进阶情绪（25）

| 标签 | 中文含义 |
| --- | --- |
| `[disdainful]` | 轻蔑 |
| `[unhappy]` | 不快 |
| `[anxious]` | 焦虑 |
| `[hysterical]` | 歇斯底里 |
| `[indifferent]` | 冷淡 |
| `[uncertain]` | 不确定 |
| `[doubtful]` | 怀疑 |
| `[confused]` | 困惑 |
| `[disappointed]` | 失望 |
| `[regretful]` | 遗憾 |
| `[guilty]` | 内疚 |
| `[ashamed]` | 羞愧 |
| `[jealous]` | 嫉妒 |
| `[envious]` | 羡慕 |
| `[hopeful]` | 怀有希望 |
| `[optimistic]` | 乐观 |
| `[pessimistic]` | 悲观 |
| `[nostalgic]` | 怀旧 |
| `[lonely]` | 孤独 |
| `[bored]` | 无聊 |
| `[contemptuous]` | 鄙视 |
| `[sympathetic]` | 同情 |
| `[compassionate]` | 关怀 |
| `[determined]` | 坚定 |
| `[resigned]` | 无奈接受 |

## 语气与表达控制（6）

| 标签 | 中文含义 |
| --- | --- |
| `[in a hurry tone]` | 急促 |
| `[shouting]` | 喊叫 |
| `[screaming]` | 尖叫 |
| `[whispering]` | 耳语 |
| `[soft tone]` | 轻柔 |
| `[emphasis]` | 强调后面的词句 |

## 音频效果（11）

| 标签 | 中文含义 |
| --- | --- |
| `[laughing]` | 笑声 |
| `[chuckling]` | 轻笑 |
| `[sobbing]` | 抽泣 |
| `[crying loudly]` | 大哭 |
| `[sighing]` | 叹气 |
| `[groaning]` | 呻吟或不满声 |
| `[panting]` | 喘息 |
| `[gasping]` | 倒吸气 |
| `[yawning]` | 打哈欠 |
| `[snoring]` | 鼾声 |
| `[clear throat]` | 清嗓 |

## 特殊效果与停顿（5）

| 标签 | 中文含义 |
| --- | --- |
| `[audience laughing]` | 观众笑声 |
| `[background laughter]` | 背景笑声 |
| `[crowd laughing]` | 人群笑声 |
| `[break]` | 短暂停顿 |
| `[long-break]` | 较长停顿 |

## S2 行内控制补充（27）

以下标签来自官方 S2 指南的中英文示例表。“中文”和“英文”指文末对应版本；含义为简要说明，所有标签都是表达提示，效果随声音和上下文变化。

| 标签 | 中文含义 | 来源 |
| --- | --- | --- |
| `[pitch up]` | 音调升高 | 中文；英文亦有示例 |
| `[pitch down]` | 音调降低 | 中文 |
| `[speaking fast]` | 局部加快语速 | 中文 |
| `[speaking slowly]` | 局部放慢语速 | 中文 |
| `[slight pause]` | 短暂停顿 | 中文 |
| `[long pause]` | 较长停顿 | 中文、英文 |
| `[pause]` | 停顿 | 英文 |
| `[short pause]` | 短暂停顿 | 英文 |
| `[soft voice]` | 轻柔说话 | 英文 |
| `[loud voice]` | 提高说话音量 | 英文 |
| `[low voice]` | 低沉声线 | 英文 |
| `[mumbling]` | 含糊说话 | 中文 |
| `[monotone]` | 减少语调起伏 | 中文 |
| `[singing]` | 尝试带旋律地演唱 | 中文 |
| `[breathing]` | 呼吸声 | 中文 |
| `[inhale]` | 吸气声 | 英文 |
| `[exhale]` | 呼气声 | 英文 |
| `[sigh]` | 叹气声 | 中文、英文 |
| `[sniffing]` | 吸鼻声 | 中文 |
| `[clears throat]` | 清嗓声 | 中文、英文 |
| `[laughter]` | 笑声 | 中文 |
| `[giggle]` | 轻快的笑声 | 英文 |
| `[cough]` | 咳嗽声 | 中文 |
| `[crying]` | 哭泣 | 中文、英文 |
| `[gasp]` | 突然吸气 | 英文 |
| `[groan]` | 低声呻吟或抱怨声 | 英文 |
| `[rustling sound]` | 窸窣声 | 英文 |

`[pause]`、`[long pause]` 已有官方文字依据，不再列为仅在 Playground 出现的标签。`[sigh]` / `[sighing]`、`[clears throat]` / `[clear throat]` 等写法分别保留；程序原样发送，不自动互换。

## 音高和语速怎么用

音高提示放在要改变表达的词句之前。例如下面仅用于演示格式的内嵌 YAML：

```yaml
model: s2.1-pro-free
reference_id: "5c353fdb312f4888836a9a5680099ef0"
text: |-
  [pitch up] 欢迎参观。
  [pitch down] 我们接着往下看。
output: output/example-pitch.mp3
```

- `[pitch up]`、`[pitch down]` 是定性的表达指令。官方没有给出固定的半音数或 Hz 幅度，不能保证精确升降调，也不能保证每种音色表现相同。
- 想让局部词句快慢变化，可用 `[speaking fast]`、`[speaking slowly]`；整段语速继续使用 `tts.prosody.speed`，整段音量使用 `tts.prosody.volume`。
- 不添加 `pitch` 或 `prosody.pitch` 参数，也不把音高要求转换成 `temperature`、`top_p` 的变化。只调音高时，正文、音色和未涉及的参数保持不变。
- 停顿标签不保证精确秒数。即使指南给出近似时长，也不能据此对齐视频或承诺音频时长。

## 保持正文一致

纯台词：“先看窗边，再转向旁边的房间。”

对应的带标签台词：“[calm] 先看窗边，再转向旁边的房间。”

该例仅说明标签位置。正式写作中的窗户、房间及镜头顺序必须来自当前素材。不要因添加标签而偷偷替换正文、补充事实或改变句意。

## 清单外标签

`[breathy]`、`[moaning]`、`[soft]` 未收录于本次核对的参考表，不在项目清单中，不生成。这不表示 S2 一定无法理解这些自然语言描述。表达轻柔时可使用 `[soft tone]` 或 `[soft voice]`。

模型支持自由描述提示，但本项目只放行上表清单。表达不够自然时，先调整句式、标点和标签密度，不凭空增加标签。用户反馈语气太强时，减少情绪强度和强调；涉及整段快慢或音量的要求，同时调整对应配音参数。只有用户提供新的音色 ID 时才更换音色。

知识依据核对日期：2026-09-27。

- [模型选择](https://docs.fish.audio/developer-guide/models-pricing/choosing-a-model)：免费版与 S2.1-Pro 使用同一模型。
- [Fish Emotion Control](https://docs.fish.audio/developer-guide/core-features/emotions)：S2/S2.1 方括号自然语言提示及原有标签。
- [S2 词级语音控制指南（中文）](https://fish.audio/zh-CN/blog/fish-audio-s2-fine-grained-ai-voice-control-at-the-word-level/)：音高、局部语速等补充标签。
- [S2 词级语音控制指南（英文）](https://fish.audio/blog/fish-audio-s2-fine-grained-ai-voice-control-at-the-word-level/)：停顿、声线、发声等补充示例；示例表与中文版不同。
- [TTS API](https://docs.fish.audio/api-reference/endpoint/openapi-v1/text-to-speech)：通过 `model` 请求头选择 `s2.1-pro-free`，当前 `prosody` 不包含 `pitch`。
