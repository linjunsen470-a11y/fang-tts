# 视频压缩与 Fish Audio 整段配音

**压缩视频 → 上传 ChatGPT Project 写稿并审核 → 保存台词 TXT 和配置 YAML → 本地生成配音。**

## 快速使用

1. 将视频放进 `input/`，双击 **compress.bat**；或把任意视频文件夹拖到这个 BAT 上。
2. 从该文件夹的 `ai_upload/` 上传 MP4 到 ChatGPT 当次对话。原视频不改动。
3. 按下面说明配置 Project，让 ChatGPT 输出纯台词、带标签的台词和 TTS YAML。审核后，将带标签的台词保存为 UTF-8 的 `tts.txt`，YAML 保存为同目录的 `tts.yaml`。以后只改台词时，只需编辑 `tts.txt`，无需调整 YAML 缩进。
4. 把 YAML 拖到 **synthesize.bat** 上生成音频；双击则读取仓库 `tts.yaml`。主动运行即确认台词，无额外审批开关。

相对 `text_file` 和 `output` 路径以 **YAML 所在文件夹**为基准。已有音频默认不覆盖，控制台会显示实际时长。压缩和 `--check` 不联网；合成只请求 Fish Audio。

## 首次准备

需要 Python 3.10+ 和含 libx264 的 FFmpeg/ffprobe。将 FFmpeg 加入 PATH；也支持本机 `D:\ffmpeg\bin`。HDR 转 SDR 另需 FFmpeg 包含 zscale、tonemap 滤镜。

只压缩视频无需安装 Python 第三方包。使用 TTS 时，在仓库打开 PowerShell：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

已有 `.venv` 时直接安装依赖即可。BAT 优先使用仓库 `.venv`，不存在时使用 PATH 中的 `python`。
将 `.env.example` 复制为 `.env`，填入 API Key；已有 `.env` 不要覆盖。模型固定为 `s2.1-pro-free`；音色在 YAML 的 `reference_id` 中指定，不需要额外环境变量。

`.env`、虚拟环境、`input/`、`output/`、`ai_upload/` 以及音视频不会进入 Git。密钥只留在本机。

## ChatGPT Project 怎么放文档

四份文档都在 [chatgpt_project](chatgpt_project/)：

- [01 角色与任务规则](chatgpt_project/01_project_instructions.md)
- [02 语气与标签](chatgpt_project/02_fish_tags.md)
- [03 配音输出规范](chatgpt_project/03_fish_api_and_yaml.md)
- [04 任务理解与写作示例](chatgpt_project/04_task_template.md)

四份均直接面向 ChatGPT，可一起作为 Project 知识文件使用，无需从文档中再摘取或改写指令。安装和操作说明集中在本 README。

每套房源另开对话，只附该房源的压缩视频与事实。不要把密钥、整个代码仓库、旧房源任务或音频缓存上传为知识文件。
视频是否能直接解析取决于实际使用的云端入口；压缩不改变平台支持情况。若 ChatGPT 无法读取，请让它明确说明，不能让它猜画面。

## 压缩设置和命令

默认：H.264 MP4，横屏最高 1280×720 / 竖屏最高 720×1280，保持比例、不放大小视频，最高 12 fps，CRF 26，fast，yuv420p，faststart。仅保留画面，移除音频、字幕、章节和源文件元数据；HDR 自动转 SDR（所需能力缺失时失败）。

```powershell
python compress_videos.py "D:\我的视频"
python compress_videos.py "D:\我的视频" --recursive
python compress_videos.py "D:\我的视频" --overwrite
```

默认仅处理该目录；`--recursive` 包括子目录并保留相对目录结构，自动排除 `ai_upload`。支持 `.mp4 .mov .m4v .mkv .webm .avi`，不区分大小写。
例如 `看房.mov` 输出为 `ai_upload/看房.mov.ai.mp4`。每个原片对应一个完整文件，不设硬性体积上限、不分段。

单个失败会继续处理其他视频，最终返回失败状态。只有通过尺寸/轨道/时长（误差≤0.15秒）和全片解码检查的文件才会发布。已存在的输出默认直接跳过；源片变更后请显式重压。
`ai_upload/compression-report.csv` 保存本次成功、跳过、失败和大小/时长明细；跳过的文件不重复探测，时长列为空。汇总文件每次更新。MB 按 1,000,000 字节计算，remaining_percent 是压缩后占原文件的百分比。

这是用于快速看画面的有损压缩，不能保证 AI“无损理解”；12 fps 可能遗漏极短闪过的画面，小字和精细材质可能变模糊。必要时补充原始清晰截图或提高质量后另行上传。低码率原片可能压缩后反而更大，汇总会如实显示。

## 台词与配置分开编辑

仓库的 `tts.yaml` 已使用 `text_file: tts.txt`；现有台词保存在同目录的 `tts.txt`。用记事本或其他文本编辑器修改 TXT，保存为 **UTF-8**（允许 BOM）即可。台词文件只放正文和合法标签，不需要 YAML 缩进，也不要放 Markdown 代码围栏、标题或说明。

下面是可独立使用的最小示例。`tts.txt` 内容：

```text
[calm] 欢迎参观。
我们接着往下看。
```

同目录的 `tts.yaml`：

```yaml
text_file: tts.txt
output: output/example.mp3
```

其他音色和配音参数仍在 YAML 中配置。也可以指定子目录，例如 `text_file: "台词/房源 A.txt"`，或使用绝对路径；Windows 绝对路径建议使用正斜杠或 YAML 单引号，如 `text_file: 'D:\台词\房源 A.txt'`。从其他目录运行、双击或拖放 YAML 时，均按该 YAML 所在目录解析相对路径。

每次运行都会重新读取台词文件；除移除 UTF-8 BOM 外，保留正文、标签、空白和换行，不改稿、不拆分。文件不存在、不可读、不是 UTF-8、内容为空或标签不合法时，会在读取密钥和联网之前报错。`text_file` 仅是本地配置字段，不会作为参数发送给 Fish API。

仍兼容原来的内嵌写法：

```yaml
text: |-
  [calm] 欢迎参观。
output: output/example.mp3
```

`text` 与 `text_file` **必须且只能填写一个**；切换为文件方式时删除整个 `text` 字段，不能留空。音频输出不能指向 YAML 或台词源文件，即使使用 `--overwrite` 也会拒绝。

## 音高与扩展标签

已核对 Fish 官方资料（2026-09-27）：`s2.1-pro-free` 与 S2.1-Pro 使用同一模型，支持 S2 方括号表达提示。项目清单已从 71 个扩展到 **98 个**，包括 `[pitch up]`、`[pitch down]`、`[speaking fast]`、`[speaking slowly]`、`[pause]`、`[long pause]` 等。完整清单与来源见 [02 语气与标签](chatgpt_project/02_fish_tags.md)。

将标签写在 `tts.txt`（或内嵌 `text`）中需要改变表达的词句前。音高标签是定性提示，没有固定半音幅度；不用新增 YAML 参数，`pitch` / `prosody.pitch` 仍会报错。局部快慢使用标签，整段快慢使用 `tts.prosody.speed`。

模型本身支持自然语言提示；本项目按规则仅放行已核实清单，未知标签继续在联网前报错，整段文本一次原样发送。口播成片不要靠停顿标签制造句间空白。需要句末换气时在 YAML 里设置 `tts.breaths: true`：合成仍是一次请求，之后把句号、问号、叹号处的气口收到约 0.50 秒。这个字段只在本地使用，请求前会删掉。规则见 [02 语气与标签](chatgpt_project/02_fish_tags.md)。ChatGPT Project 请整组使用四份知识文件。

## 整段配音命令

```powershell
python cli.py --check
python cli.py "D:\台词\房源A.yaml" --check
python cli.py "D:\台词\房源A.yaml"
python cli.py "D:\台词\房源A.yaml" --overwrite
```

`--check` 会读取 YAML 及其指定的台词文件，检查配置、标签和参数，不读取密钥、不创建音频、不访问网络，也不要求 FFmpeg。
音色 `reference_id` 可替换为你选择的 Fish Audio 音色 ID，省略时沿用默认音色。`tts.prosody` 控制语速、音量和音量标准化；`temperature`、`top_p` 可调整表达采样，情绪和停顿标签写在 `tts.txt`（或内嵌 `text`）中。离线校验不验证音色是否存在或账户是否有使用权限。
YAML 中的 `tts` 可以省略，或只覆盖部分默认值。完整字段规范见 [03 参数与输出规范](chatgpt_project/03_fish_api_and_yaml.md)。输出扩展名必须匹配格式。普通格式用 ffprobe 检查返回文件和时长；PCM 按官方单声道 16-bit 数据长度计算。

合成前检查已有输出；API 或音频验证失败时不会替换旧音频。不自动重试请求、不改写台词、不加速音频；超时后先核实账户记录，再决定是否手动重试。

如需从命令行运行 BAT 而不暂停，可先设置 `$env:FISH_TTS_NO_PAUSE='1'`。正常双击会保留窗口，方便查看结果。

## 清理说明与测试

旧的 `prepare` / `synthesize jobs.yaml` 命令、联系表、分镜审批、分段拼接和 SRT 输出已移除。旧 `jobs.yaml` 已删除，历史 `work/` 完整归档到 `output/_legacy/work/`；新程序不读取该归档。原片和历史配音保留。

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

测试使用模拟 API，不会付费生成配音或上传用户视频。文档示例在临时目录校验，不读取用户当前的 `tts.yaml` / `tts.txt`。FFmpeg 集成测试使用临时合成的视频素材。
