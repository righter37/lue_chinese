# Lue 中文听书 — 完整部署指南

本项目基于 [lue](https://github.com/superstarryeyes/lue)，针对中文电子书做了定制，
默认使用 **Edge TTS**（微软云端，毫秒级响应，无需 GPU）。

---

## 目录

- [系统要求](#系统要求)
- [第一步：WSL2 环境准备](#第一步wsl2-环境准备)
- [第二步：安装系统依赖](#第二步安装系统依赖)
- [第三步：获取源码](#第三步获取源码)
- [第四步：创建 Python 虚拟环境并安装](#第四步创建-python-虚拟环境并安装)
- [第五步：配置别名](#第五步配置别名)
- [第六步：运行验证](#第六步运行验证)
- [常用命令参考](#常用命令参考)
- [GPT-SoVITS 声音克隆（可选）](#gptsovits-声音克隆可选)
- [常见问题](#常见问题)

---

## 系统要求

| 项目 | 要求 |
|------|------|
| 操作系统 | Windows 10/11（64位）|
| WSL2 | Ubuntu 22.04 LTS |
| Python | 3.10（Ubuntu 22.04 内置）|
| 网络 | 需要（Edge TTS 是云端服务）|
| GPU | 不需要（Edge TTS 模式）|

---

## 第一步：WSL2 环境准备

如果已有 Ubuntu 22.04 的 WSL2 可跳过此步。

**以管理员身份**打开 PowerShell，执行：

```powershell
wsl --install -d Ubuntu-22.04
```

安装完成后重启电脑，重启后 Ubuntu 会弹出窗口让你设置用户名和密码。

验证安装成功：
```powershell
wsl --list --verbose
# 应看到 Ubuntu-22.04  Running  2
```

---

## 第二步：安装系统依赖

打开 **WSL 终端**（Ubuntu），执行：

```bash
sudo apt update
sudo apt install -y ffmpeg python3.10-venv
```

验证：
```bash
ffplay -version   # 应输出 ffplay 版本信息，有则成功
python3 --version # 应输出 Python 3.10.x
```

> **为什么需要 ffmpeg？**
> lue 用 `ffplay` 播放音频，用 `ffprobe` 获取音频时长，两者都在 ffmpeg 包里。

---

## 第三步：获取源码

**方式一：Git 克隆（推荐）**

```bash
git clone https://github.com/YOUR_USERNAME/lue-zh.git /home/你的用户名/lue
```

**方式二：下载 ZIP**

在 Windows 浏览器下载 ZIP 解压，假设解压到 `E:\lue-main\lue-main\`，
在 WSL 中对应路径为 `/mnt/e/lue-main/lue-main/`。

以下步骤以 `/mnt/e/lue-main/lue-main/` 为例，根据实际路径替换。

---

## 第四步：创建 Python 虚拟环境并安装

```bash
# 在用户 home 下创建虚拟环境
python3 -m venv ~/lue-wslenv

# 安装 lue 及所有依赖（含 edge-tts）
~/lue-wslenv/bin/python3 -m pip install -e /mnt/e/lue-main/lue-main
```

安装过程会自动安装：
`edge-tts`, `rich`, `PyMuPDF`, `python-docx`, `aiohttp` 等全部依赖。

安装完成后验证：
```bash
~/lue-wslenv/bin/python3 -c "import lue, edge_tts; print('OK')"
# 输出 OK 则成功
```

---

## 第五步：配置别名

```bash
echo "alias lue='~/lue-wslenv/bin/python3 -m lue'" >> ~/.bashrc
source ~/.bashrc
```

---

## 第六步：运行验证

```bash
lue /mnt/e/ebook/置身事内.epub
```

首次运行会有短暂的 Edge TTS 预热（~1秒），之后开始朗读。

**常用启动参数：**

```bash
lue 书.epub                      # 默认 Edge TTS 中文
lue 书.epub -s 1.3               # 1.3 倍速
lue 书.epub -v zh-CN-YunxiNeural # 换男声
lue 书.epub -t none              # 关闭 TTS，纯阅读模式
lue                              # 打开上次读到的书
```

---

## 常用命令参考

### 启动参数

| 参数 | 说明 | 示例 |
|------|------|------|
| `-t`, `--tts` | 选择 TTS 引擎 | `-t edge` / `-t gptsovits` / `-t none` |
| `-v`, `--voice` | 指定语音 | `-v zh-CN-YunxiNeural` |
| `-s`, `--speed` | 播放速度（1.0-3.0）| `-s 1.5` |
| `-l`, `--lang` | 语言代码 | `-l zh` |
| `-g`, `--guide` | 打开按键指南 | `lue -g` |

### 可用中文 Edge TTS 语音

```bash
# 列出所有中文语音
~/lue-wslenv/bin/python3 -c "
import asyncio, edge_tts
async def main():
    voices = await edge_tts.list_voices()
    for v in voices:
        if v['Locale'].startswith('zh'):
            print(v['ShortName'], '|', v['Gender'])
asyncio.run(main())
"
```

常用语音：
- `zh-CN-XiaoxiaoNeural` — 女声，温和自然（**默认**）
- `zh-CN-YunxiNeural` — 男声，清晰
- `zh-TW-HsiaoChenNeural` — 台湾腔女声

修改默认语音：编辑 `lue/config.py` 第 11 行的 `TTS_VOICES`。

### 阅读界面快捷键

| 按键 | 功能 |
|------|------|
| `空格` | 暂停 / 继续 |
| `←` / `→` | 上一章 / 下一章 |
| `↑` / `↓` | 滚动 |
| `[` / `]` | 减速 / 加速 |
| `q` | 退出（自动保存进度）|
| `?` | 显示按键帮助 |

---

## GPT-SoVITS 声音克隆（可选）

如果想用自己的声音朗读，参考 [docs/gptsovits/GPTSOVITS_SETUP.md](docs/gptsovits/GPTSOVITS_SETUP.md)。

**快速说明**：
1. 在 Windows 上安装并启动 GPT-SoVITS API 服务（CUDA GPU 必须）
2. 准备参考音频（3-10 秒的清晰录音）
3. 设置环境变量：

```bash
export GPTSOVITS_URL="http://$(ip route show default | awk '{print $3}'):9880"
export GPTSOVITS_REF_AUDIO="E:\\my_voice.wav"   # Windows 路径
export GPTSOVITS_PROMPT_TEXT="参考音频中说的话"
export GPTSOVITS_PROMPT_LANG="zh"
```

4. 启动 lue：
```bash
lue -t gptsovits 书.epub
```

---

## 常见问题

### `termios` 模块找不到 / 无法在 Windows 直接运行

lue 依赖 Linux 专属模块，**必须在 WSL 终端中运行**，不能在 Windows CMD/PowerShell 直接执行。

### `ffplay: command not found`

```bash
sudo apt install ffmpeg
```

### `python3 -m venv` 失败，提示安装 python3.10-venv

```bash
sudo apt install python3.10-venv
# 然后重新执行 python3 -m venv ~/lue-wslenv
```

### Edge TTS 没有声音但没有报错

WSL 音频默认通过 PulseAudio 输出到 Windows。检查：
```bash
# 测试 WSL 是否能播放音频
ffplay -nodisp -autoexit /mnt/e/任意音频.mp3
```
如果听不到声音，检查 Windows 音频设备设置或更新 WSL。

### 运行后界面显示乱码

终端需要支持 UTF-8 和 256 色，推荐使用 **Windows Terminal**（微软商店免费下载）。

### 修改代码后生效问题

本项目使用 editable install（`pip install -e`），修改 `lue/` 目录下的 Python 文件后直接生效，无需重新安装。

### 切换书籍时提示找不到上次进度

进度文件保存在 `~/.local/share/lue/`，跨设备复现时不会自动迁移，重新从头读即可。
