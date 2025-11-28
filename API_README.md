# ThinkSound API 使用文档

纯后端 FastAPI 服务，支持视频生成音频和文本生成音频。

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install fastapi uvicorn python-multipart requests
```

### 2. 启动服务

```bash
# Linux/macOS
./start_api.sh


# 或直接运行
python api_server.py
```

服务启动后访问: http://localhost:8000/docs

### 3. 快速测试

```bash
# 测试文本生成音频
python test_api.py text

# 测试视频生成音频
python test_api.py video your_video.mp4
```

---

## 📚 核心功能

### 1️⃣ 文本生成音频 (推荐)

**接口**: `POST /api/generate-text`

**参数**:
- `description` (必填): 音频描述
- `title` (可选): 标题
- `duration` (可选): 时长（秒），默认10秒，范围0-60
- `use_half` (可选): 半精度模式，默认false

**示例**:

```bash
# cURL
curl -X POST "http://localhost:8000/api/generate-text" \
  -F "description=海浪拍打岸边，海鸥鸣叫" \
  -F "duration=10.0"
```

```python
# Python
import requests
import time

# 提交任务
response = requests.post(
    "http://localhost:8000/api/generate-text",
    data={
        "description": "大雨倾盆，雨滴打在窗户上",
        "duration": 10.0
    }
)
task_id = response.json()["task_id"]

# 等待完成
while True:
    status = requests.get(f"http://localhost:8000/api/status/{task_id}").json()
    if status["status"] == "completed":
        break
    time.sleep(2)

# 下载音频
audio = requests.get(f"http://localhost:8000/api/audio/{task_id}")
with open("rain.wav", "wb") as f:
    f.write(audio.content)
```

### 2️⃣ 视频生成音频

**接口**: `POST /api/generate`

**参数**:
- `video` (可选): 视频文件
- `title` (可选): 标题
- `description` (可选): 描述
- `use_half` (可选): 半精度模式

**示例**:

```bash
# cURL
curl -X POST "http://localhost:8000/api/generate" \
  -F "video=@video.mp4" \
  -F "description=街道场景，汽车驶过"
```

```python
# Python
with open("video.mp4", "rb") as f:
    response = requests.post(
        "http://localhost:8000/api/generate",
        files={"video": f},
        data={"description": "街道场景"}
    )
```

### 3️⃣ 查询任务状态

**接口**: `GET /api/status/{task_id}`

```python
status = requests.get(f"http://localhost:8000/api/status/{task_id}").json()
# 状态: pending, processing, completed, failed
```

### 4️⃣ 下载结果

```python
# 下载音频
audio = requests.get(f"http://localhost:8000/api/audio/{task_id}")
with open("audio.wav", "wb") as f:
    f.write(audio.content)

# 下载视频（带音频）
video = requests.get(f"http://localhost:8000/api/download/{task_id}")
with open("video.mp4", "wb") as f:
    f.write(video.content)
```

### 5️⃣ 其他接口

```python
# 列出所有任务
tasks = requests.get("http://localhost:8000/api/tasks").json()

# 删除任务
requests.delete(f"http://localhost:8000/api/tasks/{task_id}")
```

---

## 💡 提示词示例

### 自然环境

```python
"海浪拍打岸边的声音，伴随着海鸥的叫声和微风吹过"
"鸟鸣声此起彼伏，树叶沙沙作响，远处传来溪流的声音"
"大雨倾盆，雨滴密集地打在窗户上，偶尔传来雷声"
"山谷中回荡着风声，远处传来瀑布的轰鸣声"
```

### 城市场景

```python
"繁忙的城市街道，汽车喇叭声、引擎声和人群的喧哗声交织"
"咖啡馆内的环境音，咖啡机的蒸汽声、杯盘碰撞声和轻柔的背景音乐"
"地铁进站的声音，刹车声、车门开关声和广播提示音"
"建筑工地的嘈杂声，电钻声、锤击声和工人的呼喊声"
```

### 室内场景

```python
"厨房里的烹饪声，炒菜的滋滋声、切菜声和水龙头的流水声"
"安静的图书馆，偶尔传来翻书声、轻微的脚步声和键盘敲击声"
"健身房的环境音，器械碰撞声、跑步机的运转声和音乐声"
```

### 交通工具

```python
"汽车在高速公路上行驶，引擎的轰鸣声和风声"
"火车在铁轨上行驶，车轮与铁轨摩擦的咔嗒声和车厢的晃动声"
"飞机起飞时的引擎轰鸣声，逐渐增强的推力声"
```

---

## 🎯 使用场景

### 场景1: 批量生成音效库

```python
import requests
import time

sound_effects = [
    ("雨声", "大雨倾盆，雨滴打在窗户上", 8),
    ("森林", "鸟鸣声和树叶沙沙作响", 10),
    ("城市", "繁忙的街道，汽车喇叭声", 12),
]

# 批量提交
task_ids = []
for title, desc, duration in sound_effects:
    response = requests.post(
        "http://localhost:8000/api/generate-text",
        data={"title": title, "description": desc, "duration": duration}
    )
    task_ids.append((response.json()["task_id"], title))

# 等待并下载
for task_id, title in task_ids:
    while True:
        status = requests.get(f"http://localhost:8000/api/status/{task_id}").json()
        if status["status"] == "completed":
            break
        time.sleep(2)
    
    audio = requests.get(f"http://localhost:8000/api/audio/{task_id}")
    with open(f"{title}.wav", "wb") as f:
        f.write(audio.content)
    print(f"✓ {title}.wav")
```

### 场景2: 视频配音

```python
with open("silent_video.mp4", "rb") as f:
    response = requests.post(
        "http://localhost:8000/api/generate",
        files={"video": f},
        data={"description": "街道场景，汽车驶过"}
    )

task_id = response.json()["task_id"]

# 等待完成
while True:
    status = requests.get(f"http://localhost:8000/api/status/{task_id}").json()
    if status["status"] == "completed":
        break
    time.sleep(2)

# 下载带音频的视频
video = requests.get(f"http://localhost:8000/api/download/{task_id}")
with open("video_with_audio.mp4", "wb") as f:
    f.write(video.content)
```

---

## ⚙️ 配置与优化

### 修改端口

编辑 `api_server.py` 最后一行：

```python
uvicorn.run(app, host="0.0.0.0", port=8080)  # 改为 8080
```

### 启用半精度（节省显存）

```python
data = {
    "description": "...",
    "use_half": True  # 减少显存占用
}
```

### 性能建议

| 场景 | 建议时长 | 建议配置 |
|------|---------|---------|
| 短音效 | 3-5秒 | 默认 |
| 环境音 | 10-20秒 | 默认 |
| 长场景 | 30-60秒 | use_half=true |
| 显存不足 | 任意 | use_half=true |

### 生产环境部署

```bash
# 使用 gunicorn
pip install gunicorn
gunicorn api_server:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000
```

---

## 🔧 故障排除

### 问题1: 服务无法启动

**检查**:
- ✅ 是否激活了 thinksound 环境
- ✅ 是否安装了依赖: `pip install fastapi uvicorn python-multipart`
- ✅ 是否下载了模型到 `ckpts/` 目录

### 问题2: 任务失败

**解决**:
- 查看任务状态的 error 字段
- 确认描述不为空且不是纯数字
- 确认时长在 0-60 秒范围内
- 查看服务器日志

### 问题3: 显存不足

**解决**:
- 设置 `use_half=true`
- 减少音频时长
- 减少并发任务数

### 问题4: 生成质量不佳

**改进**:
- 增加描述的细节
- 描述声音的特征（音量、节奏、层次）
- 使用视频+文本组合模式
- 适当增加音频时长

---

## 📝 API 接口总览

| 接口 | 方法 | 说明 |
|------|------|------|
| `/` | GET | API 信息 |
| `/api/generate-text` | POST | 文本生成音频 |
| `/api/generate` | POST | 视频生成音频（支持纯文本） |
| `/api/status/{task_id}` | GET | 查询任务状态 |
| `/api/audio/{task_id}` | GET | 下载音频文件 |
| `/api/download/{task_id}` | GET | 下载视频（带音频） |
| `/api/tasks` | GET | 列出所有任务 |
| `/api/tasks/{task_id}` | DELETE | 删除任务 |

---

## 📦 文件说明

- `api_server.py` - FastAPI 服务器主程序
- `api_client_example.py` - Python 客户端示例
- `test_api.py` - API 测试脚本
- `start_api.sh` - Linux/macOS 启动脚本
- `start_api.bat` - Windows 启动脚本
- `requirements_api.txt` - API 依赖包

---

## 🎓 完整示例

查看 `api_client_example.py` 获取完整的客户端示例代码：

```bash
# 运行文本生成示例
python api_client_example.py text

# 运行视频生成示例
python api_client_example.py video

# 运行批量生成示例
python api_client_example.py batch
```

---

## 💬 获取帮助

- 📖 查看 API 文档: http://localhost:8000/docs
- 🧪 运行测试: `python test_api.py`
- 💡 查看示例: `api_client_example.py`

---

**开始使用**: `python api_server.py` 🚀
