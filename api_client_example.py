"""
ThinkSound API 客户端使用示例
"""
import requests
import time
from pathlib import Path
from typing import Optional

API_BASE_URL = "http://localhost:8000"

def generate_audio_from_video(video_path: str, title: str = "", description: str = "", use_half: bool = False):
    """从视频生成音频"""
    url = f"{API_BASE_URL}/api/generate"
    
    with open(video_path, "rb") as f:
        files = {"video": (Path(video_path).name, f, "video/mp4")}
        data = {
            "title": title,
            "description": description,
            "use_half": use_half
        }
        
        response = requests.post(url, files=files, data=data)
        response.raise_for_status()
        return response.json()

def generate_audio_from_text(description: str, title: str = "", duration: float = 10.0, use_half: bool = False):
    """从文本生成音频"""
    url = f"{API_BASE_URL}/api/generate-text"
    
    data = {
        "title": title,
        "description": description,
        "duration": duration,
        "use_half": use_half
    }
    
    response = requests.post(url, data=data)
    response.raise_for_status()
    return response.json()

def check_status(task_id: str):
    """查询任务状态"""
    url = f"{API_BASE_URL}/api/status/{task_id}"
    response = requests.get(url)
    response.raise_for_status()
    return response.json()

def download_video(task_id: str, save_path: str):
    """下载生成的视频"""
    url = f"{API_BASE_URL}/api/download/{task_id}"
    response = requests.get(url)
    response.raise_for_status()
    
    with open(save_path, "wb") as f:
        f.write(response.content)
    print(f"视频已保存到: {save_path}")

def download_audio(task_id: str, save_path: str):
    """下载生成的音频"""
    url = f"{API_BASE_URL}/api/audio/{task_id}"
    response = requests.get(url)
    response.raise_for_status()
    
    with open(save_path, "wb") as f:
        f.write(response.content)
    print(f"音频已保存到: {save_path}")

def list_tasks():
    """列出所有任务"""
    url = f"{API_BASE_URL}/api/tasks"
    response = requests.get(url)
    response.raise_for_status()
    return response.json()

def delete_task(task_id: str):
    """删除任务"""
    url = f"{API_BASE_URL}/api/tasks/{task_id}"
    response = requests.delete(url)
    response.raise_for_status()
    return response.json()

def wait_for_completion(task_id: str, timeout: int = 300):
    """等待任务完成"""
    start_time = time.time()
    while time.time() - start_time < timeout:
        status = check_status(task_id)
        print(f"状态: {status['status']} - {status['message']}")
        
        if status["status"] == "completed":
            return True
        elif status["status"] == "failed":
            print(f"任务失败: {status.get('error')}")
            return False
        
        time.sleep(2)
    
    print("任务超时")
    return False

def example_video_to_audio():
    """示例1: 视频生成音频"""
    print("=" * 60)
    print("示例1: 视频生成音频")
    print("=" * 60)
    
    result = generate_audio_from_video(
        video_path="path/to/your/video.mp4",
        title="街道场景",
        description="一辆汽车驶过，伴随着引擎声和轮胎摩擦声",
        use_half=False
    )
    
    task_id = result["task_id"]
    print(f"任务ID: {task_id}")
    
    if wait_for_completion(task_id):
        download_video(task_id, f"result_{task_id}.mp4")
        download_audio(task_id, f"audio_{task_id}.wav")
        print("✓ 完成")

def example_text_to_audio():
    """示例2: 纯文本生成音频"""
    print("\n" + "=" * 60)
    print("示例2: 纯文本生成音频")
    print("=" * 60)
    
    result = generate_audio_from_text(
        description="海浪拍打岸边的声音，伴随着海鸥的叫声",
        title="海滩场景",
        duration=10.0,
        use_half=False
    )
    
    task_id = result["task_id"]
    print(f"任务ID: {task_id}")
    
    if wait_for_completion(task_id):
        download_audio(task_id, f"text_audio_{task_id}.wav")
        print("✓ 完成")

def example_multiple_text_audio():
    """示例3: 批量文本生成音频"""
    print("\n" + "=" * 60)
    print("示例3: 批量文本生成音频")
    print("=" * 60)
    
    prompts = [
        ("雨声", "大雨倾盆，雨滴打在窗户上的声音", 8.0),
        ("森林", "鸟鸣声和树叶沙沙作响", 10.0),
        ("城市", "繁忙的街道，汽车喇叭声和人群喧哗", 12.0),
    ]
    
    task_ids = []
    for title, desc, duration in prompts:
        result = generate_audio_from_text(desc, title, duration)
        task_ids.append((result["task_id"], title))
        print(f"提交任务: {title} - {result['task_id']}")
    
    # 等待所有任务完成
    for task_id, title in task_ids:
        print(f"\n等待任务: {title}")
        if wait_for_completion(task_id):
            download_audio(task_id, f"{title}_{task_id}.wav")

def main():
    # 选择运行哪个示例
    import sys
    
    if len(sys.argv) > 1:
        mode = sys.argv[1]
        if mode == "video":
            example_video_to_audio()
        elif mode == "text":
            example_text_to_audio()
        elif mode == "batch":
            example_multiple_text_audio()
        else:
            print("用法: python api_client_example.py [video|text|batch]")
    else:
        # 默认运行文本生成示例
        example_text_to_audio()
        
        # 列出所有任务
        print("\n" + "=" * 60)
        print("所有任务")
        print("=" * 60)
        tasks = list_tasks()
        print(f"总任务数: {tasks['total']}")
        for task in tasks["tasks"][:5]:
            print(f"  - {task['task_id']}: {task['status']}")

if __name__ == "__main__":
    main()
