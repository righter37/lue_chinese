# Lue TTS 技术架构文档

## 一、为什么 GPT-SoVITS 表现不好

### 1.1 模型本身的定位问题

GPT-SoVITS 是一个**声音克隆**模型，设计目标是用极少量参考音频复现特定人的声音。它的推理分两个阶段：

```
文本 → [AR 自回归模型 (GPT)] → 语义 token
                                       ↓
参考音频 →  [Flow-matching 声码器 (SoVITS)] → 波形
```

每句话都要完整走这两步，GPU 计算量大。对于"不在乎音色"的场景，声音克隆能力完全是多余的开销。

### 1.2 配置导致 GPU 未被使用

`tts_infer.yaml` 中 `is_half: true`（半精度）与 v3 版 AR 模型存在兼容性问题，导致模型**静默回退到 CPU** 运行，GPU 占用接近 0%。修复方式是将 `is_half` 改为 `false`。

### 1.3 asyncio 事件循环被阻塞

`generate_audio` 函数声明为 `async`，但内部直接调用的是**同步阻塞** I/O：

```python
# 问题代码：同步调用卡住整个事件循环
with urllib.request.urlopen(url, timeout=120) as resp:
    audio_data = resp.read()
```

asyncio 是**单线程**协作式调度。一个协程调用同步阻塞 I/O 时，整个事件循环都会被挂起，期间所有其他协程（包括暂停键的响应）都无法运行。这就是为什么暂停键"不灵"——它必须等当前句子推理完成才能被处理。

### 1.4 综合延迟

- 每句话推理：5–30 秒（取决于句子长度和 GPU 状态）
- 预生成队列填满后：播放速度跟不上阅读速度，持续卡顿

---

## 二、Edge TTS 方案

### 2.1 原理

Edge TTS 调用的是**微软 Edge 浏览器**内置的在线 TTS 服务（WebSocket 协议）。这个服务：

- 免费，无需注册或 API Key
- 延迟极低（每句话 < 1 秒）
- 中文质量高（`zh-CN-XiaoxiaoNeural` 等神经网络语音）
- 原生支持 `async/await`，不会阻塞事件循环

Python 库 `edge-tts` 封装了这个 WebSocket 接口，内部基于 `aiohttp` 实现异步 HTTP/WS 通信。

### 2.2 WordBoundary：精确时间戳

Edge TTS 服务会随音频流同时推送**单词边界事件**（WordBoundary），包含每个词的开始和结束时间（100 纳秒精度）。lue 利用这些数据实现阅读时**逐词高亮**：

```python
async for chunk in communicate.stream():
    if chunk['type'] == 'WordBoundary':
        start = chunk['offset'] / 10_000_000  # 转换为秒
        end   = (chunk['offset'] + chunk['duration']) / 10_000_000
        word_timings.append((chunk['text'], start, end))
    elif chunk['type'] == 'audio':
        audio_chunks.append(chunk['data'])
```

---

## 三、并发架构：Producer-Consumer 模式

lue 的音频系统采用经典的**生产者-消费者**架构，两个独立协程通过队列通信：

```
[Producer 协程]                        [Player 协程]
    │                                       │
    ├─ 取下一句文本                         ├─ 从队列取音频文件
    ├─ 调用 Edge TTS 生成 WAV/MP3          ├─ 启动 ffplay 播放
    ├─ 放入 asyncio.Queue                  ├─ sleep(duration - overlap)
    └─ 循环（最多预生成 MAX_QUEUE_SIZE 句）  └─ 循环
                    ↕
            asyncio.Queue（容量 8）
```

### 关键参数

| 参数 | 值 | 作用 |
|------|-----|------|
| `MAX_QUEUE_SIZE` | 8 | 最多预生成 8 句，避免内存堆积 |
| `AUDIO_BUFFERS` | 10 个槽位 | 循环复用的临时音频文件 |
| `overlap_seconds` | 0.15s (Edge) | 下一句提前开始播放，掩盖切换间隙 |

### Buffer 文件循环复用

为避免频繁创建/删除文件，音频缓冲区使用固定文件名循环覆写：

```
buffer_0.mp3 → buffer_1.mp3 → ... → buffer_9.mp3 → buffer_0.mp3 → ...
```

`MAX_QUEUE_SIZE`（8）必须小于 `AUDIO_BUFFERS`（10），否则生产者会覆写播放器正在读取的文件。

---

## 四、asyncio 并发模型详解

lue 全程使用 Python 的 `asyncio`（单线程事件循环），**不使用多线程**。并发靠**协作式调度**：协程在 `await` 处主动让出控制权。

```
事件循环（单线程）
├─ Producer 协程：await edge_tts → 让出 → 其他协程运行
├─ Player 协程：await asyncio.sleep → 让出 → 其他协程运行
├─ Input 协程：await 按键事件 → 让出 → 其他协程运行
└─ ffplay 进程：asyncio.create_subprocess_exec（非阻塞子进程）
```

### 关键 asyncio API

| API | 用途 |
|-----|------|
| `asyncio.Queue` | Producer/Player 之间传递音频文件路径和时间信息 |
| `asyncio.create_task` | 启动 Producer 和 Player 协程 |
| `asyncio.create_subprocess_exec` | 非阻塞启动 ffplay 播放进程 |
| `asyncio.sleep` | 等待音频播放完毕（释放事件循环） |
| `asyncio.to_thread` | 将同步阻塞调用（如 urllib）移入线程池，避免卡死事件循环 |
| `task.cancel()` | 暂停/停止时取消 Producer 和 Player |

### 为什么不用多线程？

- asyncio 更适合 I/O 密集型任务（网络请求、文件读写、子进程）
- 避免线程安全问题（GIL、锁、竞态条件）
- Edge TTS 本身是 async API，天然适配

---

## 五、整体数据流

```
epub 文件
    │
    ▼
[content_parser]
    ├─ 按段落拆分
    └─ 按句子拆分（中文：。！？  英文：.!?）
                    │
                    ▼
            [Producer 协程]
                    │
                    ├─ sanitize_text（清理特殊字符）
                    ├─ Edge TTS WebSocket 请求（async）
                    ├─ 写入 buffer_N.mp3
                    └─ 放入 Queue（含时间戳信息）
                                    │
                                    ▼
                            [Player 协程]
                                    │
                                    ├─ ffplay buffer_N.mp3（子进程）
                                    ├─ 更新 UI 高亮（逐词）
                                    └─ sleep(duration - 0.15s)
                                            │
                                            ▼
                                    [下一句开始播放]
```

---

## 六、环境说明

| 组件 | 位置 | 说明 |
|------|------|------|
| lue 源码 | `E:\lue-main\lue-main\` | 通过 editable install 直接使用 |
| WSL Python 环境 | `~/lue-wslenv/` | Ubuntu-22.04，Python 3.10 |
| 运行命令 | `~/lue-wslenv/bin/python3 -m lue <epub>` | 必须在 WSL 终端运行（依赖 termios 等 Linux 模块） |
| 音频播放 | `ffplay`（ffmpeg 套件）| 在 WSL 内播放，音频输出到 Windows 音频设备 |
| TTS 服务 | 微软云端（edge-tts） | 需要网络连接 |
