# GPT-SoVITS + Lue 使用指南

GPT-SoVITS 是一个声音克隆 TTS，可以用极少量参考音频复现特定人的声音。
集成到 lue 后，读书时会用你指定的声音朗读，音色非常自然。

**注意**：GPT-SoVITS 推理较慢（每句 5-30 秒），适合追求音色质量、对实时性要求不高的场景。
如果只需流畅听书，推荐使用默认的 Edge TTS。

---

## 架构说明

```
Windows（宿主）                          WSL2（lue 运行环境）
┌─────────────────────────┐             ┌─────────────────────────┐
│  GPT-SoVITS 服务器       │  HTTP:9880  │  lue + gptsovits 后端   │
│  runtime\python          │◄───────────►│  gptsovits_tts.py       │
│  api_v2.py               │             │  urllib → asyncio.thread │
│  GPU 推理                │             └─────────────────────────┘
└─────────────────────────┘
```

lue 在 WSL 中运行，通过 HTTP 请求 Windows 上的 GPT-SoVITS API 服务器合成音频。

---

## 第一步：安装 GPT-SoVITS（Windows）

1. 从 [GPT-SoVITS Release 页面](https://github.com/RVC-Boss/GPT-SoVITS/releases) 下载预打包版（带 runtime 的 zip）
2. 解压到任意目录，例如 `E:\GPT-SoVITS\`
3. 下载预训练模型放到对应目录（按 README 指引）

**推荐使用 v3 版本**，模型文件：
- `GPT_SoVITS/pretrained_models/s1v3.ckpt`（AR 模型）
- `GPT_SoVITS/pretrained_models/s2Gv3.pth`（声码器）

---

## 第二步：配置 `tts_infer.yaml`

位于 `GPT_SoVITS/configs/tts_infer.yaml`，修改 `custom` 段：

```yaml
custom:
  bert_base_path: GPT_SoVITS/pretrained_models/chinese-roberta-wwm-ext-large
  cnhuhbert_base_path: GPT_SoVITS/pretrained_models/chinese-hubert-base
  device: cuda        # ← 必须是 cuda，不能是 cpu
  is_half: false      # ← 必须是 false，v3 模型 true 会静默回退到 CPU
  t2s_weights_path: GPT_SoVITS/pretrained_models/s1v3.ckpt
  version: v3
  vits_weights_path: GPT_SoVITS/pretrained_models/s2Gv3.pth
```

**关键注意事项**：
- `is_half: true` + v3 模型会导致 GPU 占用为 0%，实际在 CPU 上跑，极慢
- `version` 字段 GPT-SoVITS 每次启动会自动重写，实际版本由模型文件决定，不用在意

---

## 第三步：准备参考音频

参考音频决定了朗读时的音色，要求：

| 项目 | 要求 |
|------|------|
| 格式 | WAV（推荐）或 MP3 |
| 时长 | 3-10 秒，不宜过长或过短 |
| 内容 | 清晰、无背景噪音 |
| 语言 | 与目标朗读语言一致（中文书用中文参考音频）|

准备好音频后记录：
1. **音频文件的 Windows 完整路径**，例如 `E:\my_voice.wav`
2. **音频中说的话的文字**，例如 `"今天天气真不错，出去走走吧。"`

---

## 第四步：启动 API 服务器

在 PowerShell 或 CMD（Windows，不是 WSL）中执行：

```powershell
cd E:\GPT-SoVITS
runtime\python api_v2.py -a 0.0.0.0 -p 9880
```

服务器启动成功后会显示类似：
```
INFO:     Uvicorn running on http://0.0.0.0:9880
```

**保持此窗口开着**，不要关闭。

---

## 第五步：配置 lue 连接 GPT-SoVITS

通过环境变量告诉 lue 服务器地址和参考音频信息。

在 WSL 终端执行（每次启动 lue 前，或加到 `~/.bashrc`）：

```bash
export GPTSOVITS_URL="http://172.x.x.x:9880"       # Windows 宿主机 IP（见下方说明）
export GPTSOVITS_REF_AUDIO="E:\\my_voice.wav"       # 参考音频 Windows 路径
export GPTSOVITS_PROMPT_TEXT="今天天气真不错，出去走走吧。"  # 参考音频的文字内容
export GPTSOVITS_PROMPT_LANG="zh"                   # zh / en / ja
```

**如何获取 Windows 宿主机 IP**（在 WSL 中执行）：
```bash
ip route show default | awk '{print $3}'
```

输出的 IP 就是 Windows 宿主机地址，通常是 `172.x.x.x` 格式。

**永久保存到 `~/.bashrc`**（推荐）：
```bash
cat >> ~/.bashrc << 'EOF'

# GPT-SoVITS 配置
export GPTSOVITS_URL="http://172.x.x.x:9880"
export GPTSOVITS_REF_AUDIO="E:\\my_voice.wav"
export GPTSOVITS_PROMPT_TEXT="今天天气真不错，出去走走吧。"
export GPTSOVITS_PROMPT_LANG="zh"
EOF
source ~/.bashrc
```

---

## 第六步：启动 lue

```bash
lue --tts gptsovits /mnt/e/ebook/你的书.epub
```

启动后 lue 会先检测 API 是否可达，然后开始推理。

---

## 环境变量参考

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `GPTSOVITS_URL` | 自动检测宿主 IP:9880 | API 服务器地址 |
| `GPTSOVITS_REF_AUDIO` | 空（必须设置）| 参考音频的 Windows 完整路径 |
| `GPTSOVITS_PROMPT_TEXT` | 空（必须设置）| 参考音频中说的话 |
| `GPTSOVITS_PROMPT_LANG` | `zh` | 参考音频语言：`zh` / `en` / `ja` |

---

## 常见问题

### GPU 占用为 0%，推理极慢

`tts_infer.yaml` 中 `is_half: true` 与 v3 模型不兼容，导致静默回退 CPU。
**修复**：将 `is_half` 改为 `false`，重启服务器。

### lue 提示 `GPT-SoVITS API not reachable`

1. 确认服务器在 Windows 上已启动（看 PowerShell 窗口）
2. 确认 `api_v2.py` 绑定的是 `0.0.0.0`（不是 `127.0.0.1`），否则 WSL 无法访问
3. 检查 Windows 防火墙是否放行了 9880 端口
4. 在 WSL 中测试连通性：`curl http://172.x.x.x:9880/`

### 暂停键反应慢

这是已知问题。GPT-SoVITS 每句推理需要数秒，暂停命令会在当前句完成后生效。
lue 已通过 `asyncio.to_thread` 优化，不会完全卡死，但仍有延迟。

### 每次重启服务器 `version` 字段变回 v2

GPT-SoVITS 在启动时会自动重写 `tts_infer.yaml` 的 `version` 字段，这是正常行为。
实际使用的版本由 `t2s_weights_path` 和 `vits_weights_path` 指向的模型文件决定，
只要模型文件路径正确（s1v3.ckpt / s2Gv3.pth），就是 v3 推理。

---

## 与 Edge TTS 的对比

| | GPT-SoVITS | Edge TTS（默认）|
|-|-----------|-----------------|
| 速度 | 5-30 秒/句 | <1 秒/句 |
| 音色 | 可克隆任意声音 | 微软预设语音 |
| 网络 | 不需要（本地推理）| 需要 |
| GPU | 需要 CUDA | 不需要 |
| 适合场景 | 追求特定音色 | 日常流畅听书 |
