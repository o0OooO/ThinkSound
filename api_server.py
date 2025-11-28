from fastapi import FastAPI, File, UploadFile, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import os
import subprocess
import shutil
import uuid
import cv2
import tempfile
from datetime import datetime
from pathlib import Path
import asyncio
from enum import Enum
import numpy as np
import torch

app = FastAPI(title="ThinkSound API", version="1.0.0")

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 任务状态枚举
class TaskStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

# 任务存储
tasks_db = {}

class TaskResponse(BaseModel):
    task_id: str
    status: TaskStatus
    message: str
    result_path: Optional[str] = None
    error: Optional[str] = None

class GenerateRequest(BaseModel):
    title: Optional[str] = ""
    description: Optional[str] = ""
    use_half: bool = False

PROJECT_ROOT = Path(__file__).parent.resolve()
TEMP_DIR = Path(tempfile.gettempdir()) / "thinksound_api"
TEMP_DIR.mkdir(exist_ok=True)

def run_infer(stage: int, duration_sec: float, videos_dir: str, csv_path: str, 
              results_dir: str, use_half: bool = False):
    """运行推理命令"""
    cmd = (
        ["python", "extract_latents.py", "--duration_sec", str(duration_sec),
         "--root", videos_dir, "--tsv_path", csv_path, "--save-dir", results_dir]
        if stage == 1 else
        ["python", "predict.py", "--duration-sec", str(duration_sec),
         "--results-dir", results_dir]
    )
    
    if stage == 1 and use_half:
        cmd.append("--use_half")
    
    process = subprocess.Popen(
        cmd,
        cwd=PROJECT_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    
    output_lines = []
    while True:
        line = process.stdout.readline()
        if not line and process.poll() is not None:
            break
        if line:
            output_lines.append(line)
    
    return_code = process.wait()
    return return_code, "".join(output_lines)

def convert_to_mp4(original_path: str, converted_path: str):
    """转换视频为MP4格式"""
    result = subprocess.run(
        ["ffmpeg", "-y", "-i", original_path, "-c:v", "libx264", 
         "-preset", "fast", "-c:a", "aac", "-strict", "experimental", converted_path],
        capture_output=True,
        text=True
    )
    return result.returncode == 0, result.stderr

def combine_audio_video(video_path: str, audio_path: str, output_path: str):
    """合并音频和视频"""
    result = subprocess.run(
        ["ffmpeg", "-y", "-i", video_path, "-i", audio_path,
         "-c:v", "copy", "-c:a", "aac", "-strict", "experimental",
         "-map", "0:v:0", "-map", "1:a:0", "-shortest", output_path],
        capture_output=True,
        text=True
    )
    return result.returncode == 0, result.stderr

def create_text_inference_script(session_dir: Path, duration: float, results_dir: Path):
    """创建纯文本推理脚本"""
    script_path = session_dir / "predict_text.py"
    
    script_content = f'''
import sys
import os
sys.path.insert(0, "{PROJECT_ROOT}")

import torch
import torchaudio
import numpy as np
from datetime import datetime
from pathlib import Path
import json
from ThinkSound.models import create_model_from_config
from ThinkSound.models.utils import load_ckpt_state_dict
from ThinkSound.inference.sampling import sample_discrete_euler

# 加载模型配置
model_config_path = "{PROJECT_ROOT}/ThinkSound/configs/model_configs/thinksound.json"
with open(model_config_path) as f:
    model_config = json.load(f)

duration = {duration}
model_config["sample_size"] = duration * model_config["sample_rate"]
model_config["model"]["diffusion"]["config"]["sync_seq_len"] = 24*int(duration)
model_config["model"]["diffusion"]["config"]["clip_seq_len"] = 8*int(duration)
model_config["model"]["diffusion"]["config"]["latent_seq_len"] = round(44100/64/32*duration)

# 创建模型
model = create_model_from_config(model_config)
model.load_state_dict(torch.load("{PROJECT_ROOT}/ckpts/pytorch_model_main.bin"))

# 加载 VAE
load_vae_state = load_ckpt_state_dict("{PROJECT_ROOT}/ckpts/vae.safetensors", prefix='autoencoder.')
model.pretransform.load_state_dict(load_vae_state)

model = model.to('cuda:0')

# 加载特征（纯文本模式）
npz_path = "{results_dir}/demo.npz"
npz_data = np.load(npz_path, allow_pickle=True)
metaclip_features = torch.from_numpy(npz_data['metaclip_features']).to('cuda:0')
sync_features = torch.from_numpy(npz_data['sync_features']).to('cuda:0')

# 读取文本描述
csv_path = "{session_dir}/cot.csv"
with open(csv_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()
    caption, caption_cot = lines[1].strip().split(',', 2)[1:]
    caption_cot = caption_cot.strip('"')

# 准备元数据
metadata = [{{
    'id': 'demo',
    'caption': caption,
    'caption_cot': caption_cot,
    'metaclip_features': metaclip_features,
    'sync_features': sync_features,
    'video_exist': torch.tensor(False)  # 纯文本模式
}}]

# 生成音频
with torch.amp.autocast('cuda'):
    conditioning = model.conditioner(metadata, 'cuda:0')

# 对于纯文本模式，使用空的视频特征
video_exist = torch.stack([item['video_exist'] for item in metadata], dim=0)
conditioning['metaclip_features'][~video_exist] = model.model.model.empty_clip_feat
conditioning['sync_features'][~video_exist] = model.model.model.empty_sync_feat

cond_inputs = model.get_conditioning_inputs(conditioning)

batch_size = 1
length = round(44100/64/32*duration)
noise = torch.randn([batch_size, model.io_channels, length]).to('cuda:0')

with torch.amp.autocast('cuda'):
    fakes = sample_discrete_euler(model.model, noise, 24, **cond_inputs, cfg_scale=5, batch_cfg=True)

if model.pretransform is not None:
    fakes = model.pretransform.decode(fakes)

audios = fakes.to(torch.float32).div(torch.max(torch.abs(fakes))).clamp(-1, 1).mul(32767).to(torch.int16).cpu()

# 保存音频
today = datetime.now().strftime('%m%d')
audio_dir = Path("{results_dir}") / f"{{today}}_batch_size1"
audio_dir.mkdir(parents=True, exist_ok=True)
torchaudio.save(str(audio_dir / "demo.wav"), audios[0], 44100)

print("音频生成完成!")
'''
    
    with open(script_path, 'w', encoding='utf-8') as f:
        f.write(script_content)
    
    return script_path

async def process_text_task(task_id: str, title: str, description: str, 
                           duration: float, use_half: bool):
    """异步处理纯文本任务"""
    try:
        tasks_db[task_id]["status"] = TaskStatus.PROCESSING
        tasks_db[task_id]["message"] = "开始处理文本"
        
        # 创建会话目录
        session_dir = TEMP_DIR / task_id
        results_dir = session_dir / "results" / "audios"
        results_dir.mkdir(parents=True, exist_ok=True)
        
        # 创建空的视频特征
        fake_clip_features = torch.zeros(8*int(duration), 1024)
        fake_sync_features = torch.zeros(24*int(duration), 768)
        
        npz_path = results_dir / "demo.npz"
        np.savez(
            str(npz_path),
            metaclip_features=fake_clip_features.numpy(),
            sync_features=fake_sync_features.numpy()
        )
        
        # 创建CSV文件
        csv_path = session_dir / "cot.csv"
        caption_cot = description.replace('"', "'")
        with open(csv_path, "w", encoding="utf-8") as f:
            f.write("id,caption,caption_cot\n")
            f.write(f"demo,{title},\"{caption_cot}\"\n")
        
        # 创建并运行纯文本推理脚本
        tasks_db[task_id]["message"] = "生成音频中"
        script_path = create_text_inference_script(session_dir, duration, results_dir)
        
        process = subprocess.Popen(
            ["python", str(script_path)],
            cwd=PROJECT_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        
        output_lines = []
        while True:
            line = process.stdout.readline()
            if not line and process.poll() is not None:
                break
            if line:
                output_lines.append(line)
        
        return_code = process.wait()
        
        if return_code != 0:
            raise Exception(f"推理失败: {''.join(output_lines)}")
        
        # 查找生成的音频
        today = datetime.now().strftime("%m%d")
        audio_file = results_dir / f"{today}_batch_size1" / "demo.wav"
        
        if not audio_file.exists():
            raise Exception("生成的音频文件未找到")
        
        # 更新任务状态
        tasks_db[task_id]["status"] = TaskStatus.COMPLETED
        tasks_db[task_id]["message"] = "处理完成"
        tasks_db[task_id]["audio_path"] = str(audio_file)
        tasks_db[task_id]["result_path"] = str(audio_file)
        
    except Exception as e:
        tasks_db[task_id]["status"] = TaskStatus.FAILED
        tasks_db[task_id]["message"] = "处理失败"
        tasks_db[task_id]["error"] = str(e)

async def process_video_task(task_id: str, video_path: str, title: str, 
                             description: str, use_half: bool):
    """异步处理视频任务"""
    try:
        tasks_db[task_id]["status"] = TaskStatus.PROCESSING
        tasks_db[task_id]["message"] = "开始处理视频"
        
        # 创建会话目录
        session_dir = TEMP_DIR / task_id
        videos_dir = session_dir / "videos"
        cot_dir = session_dir / "cot_coarse"
        results_dir = session_dir / "results" / "audios"
        
        videos_dir.mkdir(parents=True, exist_ok=True)
        cot_dir.mkdir(parents=True, exist_ok=True)
        results_dir.mkdir(parents=True, exist_ok=True)
        
        # 转换视频格式
        ext = os.path.splitext(video_path)[1].lower()
        temp_mp4 = str(videos_dir / "demo.mp4")
        
        if ext != ".mp4":
            tasks_db[task_id]["message"] = "转换视频格式"
            ok, err = convert_to_mp4(video_path, temp_mp4)
            if not ok:
                raise Exception(f"视频转码失败: {err}")
        else:
            shutil.copy(video_path, temp_mp4)
        
        # 计算视频时长
        cap = cv2.VideoCapture(temp_mp4)
        fps = cap.get(cv2.CAP_PROP_FPS) or 1
        frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        cap.release()
        duration_sec = frames / fps
        
        # 创建CSV文件
        csv_path = str(cot_dir / "cot.csv")
        caption_cot = description.replace('"', "'")
        with open(csv_path, "w", encoding="utf-8") as f:
            f.write("id,caption,caption_cot\n")
            f.write(f"demo,{title},\"{caption_cot}\"\n")
        
        # 特征提取
        tasks_db[task_id]["message"] = "提取特征中"
        code, out = run_infer(1, duration_sec, str(videos_dir), csv_path, 
                             str(results_dir), use_half)
        if code != 0:
            raise Exception(f"特征提取失败: {out}")
        
        # 推理生成
        tasks_db[task_id]["message"] = "生成音频中"
        code, out = run_infer(2, duration_sec, str(videos_dir), csv_path, 
                             str(results_dir))
        if code != 0:
            raise Exception(f"推理失败: {out}")
        
        # 查找生成的音频
        today = datetime.now().strftime("%m%d")
        audio_file = results_dir / f"{today}_batch_size1" / "demo.wav"
        
        if not audio_file.exists():
            raise Exception("生成的音频文件未找到")
        
        # 合并音视频
        vid = os.path.splitext(os.path.basename(video_path))[0]
        combined_video = results_dir / f"{vid}_with_audio.mp4"
        ok, err = combine_audio_video(temp_mp4, str(audio_file), str(combined_video))
        
        if not ok:
            raise Exception(f"合并音视频失败: {err}")
        
        # 更新任务状态
        tasks_db[task_id]["status"] = TaskStatus.COMPLETED
        tasks_db[task_id]["message"] = "处理完成"
        tasks_db[task_id]["result_path"] = str(combined_video)
        tasks_db[task_id]["audio_path"] = str(audio_file)
        
    except Exception as e:
        tasks_db[task_id]["status"] = TaskStatus.FAILED
        tasks_db[task_id]["message"] = "处理失败"
        tasks_db[task_id]["error"] = str(e)

@app.get("/")
async def root():
    """API根路径"""
    return {
        "name": "ThinkSound API",
        "version": "1.0.0",
        "description": "支持视频生成音频和纯文本生成音频",
        "endpoints": {
            "generate": "/api/generate (支持视频或纯文本)",
            "generate_text": "/api/generate-text (纯文本专用)",
            "status": "/api/status/{task_id}",
            "download": "/api/download/{task_id}",
            "audio": "/api/audio/{task_id}",
            "tasks": "/api/tasks"
        }
    }

@app.post("/api/generate", response_model=TaskResponse)
async def generate_audio(
    background_tasks: BackgroundTasks,
    video: UploadFile = File(None),
    title: str = Form(""),
    description: str = Form(""),
    use_half: bool = Form(False)
):
    """
    生成音频接口（支持视频或纯文本）
    - video: 视频文件（可选，如果不提供则为纯文本模式）
    - title: 标题（可选）
    - description: CoT描述（可选）
    - use_half: 是否使用半精度（可选）
    """
    # 验证输入
    if title.isdigit() or description.isdigit():
        raise HTTPException(status_code=400, detail="标题和描述不能完全由数字构成")
    
    if not video and not description:
        raise HTTPException(status_code=400, detail="必须提供视频或描述")
    
    # 生成任务ID
    task_id = uuid.uuid4().hex
    
    # 初始化任务
    tasks_db[task_id] = {
        "task_id": task_id,
        "status": TaskStatus.PENDING,
        "message": "任务已创建",
        "result_path": None,
        "audio_path": None,
        "error": None,
        "created_at": datetime.now().isoformat(),
        "mode": "text" if not video else "video"
    }
    
    if video:
        # 视频模式
        session_dir = TEMP_DIR / task_id
        session_dir.mkdir(parents=True, exist_ok=True)
        video_path = session_dir / f"upload_{video.filename}"
        
        with open(video_path, "wb") as f:
            content = await video.read()
            f.write(content)
        
        # 添加后台任务
        background_tasks.add_task(
            process_video_task, task_id, str(video_path), title, description, use_half
        )
    else:
        # 纯文本模式（默认10秒）
        duration = 10.0
        background_tasks.add_task(
            process_text_task, task_id, title, description, duration, use_half
        )
    
    return TaskResponse(
        task_id=task_id,
        status=TaskStatus.PENDING,
        message="任务已提交，正在处理中"
    )

@app.post("/api/generate-text", response_model=TaskResponse)
async def generate_audio_from_text(
    background_tasks: BackgroundTasks,
    title: str = Form(""),
    description: str = Form(...),
    duration: float = Form(10.0),
    use_half: bool = Form(False)
):
    """
    纯文本生成音频接口
    - title: 标题（可选）
    - description: CoT描述（必填）
    - duration: 音频时长（秒），默认10秒
    - use_half: 是否使用半精度（可选）
    """
    # 验证输入
    if not description or description.isdigit():
        raise HTTPException(status_code=400, detail="描述不能为空或纯数字")
    
    if duration <= 0 or duration > 60:
        raise HTTPException(status_code=400, detail="时长必须在0-60秒之间")
    
    # 生成任务ID
    task_id = uuid.uuid4().hex
    
    # 初始化任务
    tasks_db[task_id] = {
        "task_id": task_id,
        "status": TaskStatus.PENDING,
        "message": "任务已创建",
        "result_path": None,
        "audio_path": None,
        "error": None,
        "created_at": datetime.now().isoformat(),
        "mode": "text"
    }
    
    # 添加后台任务
    background_tasks.add_task(
        process_text_task, task_id, title, description, duration, use_half
    )
    
    return TaskResponse(
        task_id=task_id,
        status=TaskStatus.PENDING,
        message="任务已提交，正在处理中"
    )

@app.get("/api/status/{task_id}", response_model=TaskResponse)
async def get_task_status(task_id: str):
    """查询任务状态"""
    if task_id not in tasks_db:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    task = tasks_db[task_id]
    return TaskResponse(
        task_id=task_id,
        status=task["status"],
        message=task["message"],
        result_path=task.get("result_path"),
        error=task.get("error")
    )

@app.get("/api/download/{task_id}")
async def download_result(task_id: str):
    """下载生成的视频（带音频）"""
    if task_id not in tasks_db:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    task = tasks_db[task_id]
    
    if task["status"] != TaskStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="任务尚未完成")
    
    result_path = task.get("result_path")
    if not result_path or not os.path.exists(result_path):
        raise HTTPException(status_code=404, detail="结果文件不存在")
    
    return FileResponse(
        result_path,
        media_type="video/mp4",
        filename=f"result_{task_id}.mp4"
    )

@app.get("/api/audio/{task_id}")
async def download_audio(task_id: str):
    """下载生成的音频文件"""
    if task_id not in tasks_db:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    task = tasks_db[task_id]
    
    if task["status"] != TaskStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="任务尚未完成")
    
    audio_path = task.get("audio_path")
    if not audio_path or not os.path.exists(audio_path):
        raise HTTPException(status_code=404, detail="音频文件不存在")
    
    return FileResponse(
        audio_path,
        media_type="audio/wav",
        filename=f"audio_{task_id}.wav"
    )

@app.get("/api/tasks")
async def list_tasks():
    """列出所有任务"""
    return {
        "total": len(tasks_db),
        "tasks": [
            {
                "task_id": task_id,
                "status": task["status"],
                "message": task["message"],
                "created_at": task.get("created_at")
            }
            for task_id, task in tasks_db.items()
        ]
    }

@app.delete("/api/tasks/{task_id}")
async def delete_task(task_id: str):
    """删除任务及其文件"""
    if task_id not in tasks_db:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    # 删除任务文件
    session_dir = TEMP_DIR / task_id
    if session_dir.exists():
        shutil.rmtree(session_dir, ignore_errors=True)
    
    # 删除任务记录
    del tasks_db[task_id]
    
    return {"message": "任务已删除", "task_id": task_id}

@app.on_event("startup")
async def startup_event():
    """启动时清理临时目录"""
    print(f"ThinkSound API 启动")
    print(f"临时目录: {TEMP_DIR}")
    print(f"项目根目录: {PROJECT_ROOT}")

@app.on_event("shutdown")
async def shutdown_event():
    """关闭时清理资源"""
    print("ThinkSound API 关闭")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
