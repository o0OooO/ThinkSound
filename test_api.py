"""
API 测试脚本
"""
import requests
import time
import sys

API_URL = "http://localhost:8000"

def test_health():
    """测试服务是否正常"""
    print("测试服务健康状态...")
    try:
        response = requests.get(API_URL)
        print(f"✓ 服务正常运行")
        print(f"  响应: {response.json()}")
        return True
    except Exception as e:
        print(f"✗ 服务连接失败: {e}")
        return False

def test_generate_video(video_path):
    """测试视频生成接口"""
    print(f"\n测试视频生成接口...")
    print(f"视频路径: {video_path}")
    
    try:
        with open(video_path, "rb") as f:
            response = requests.post(
                f"{API_URL}/api/generate",
                files={"video": f},
                data={
                    "title": "测试视频",
                    "description": "这是一个测试描述",
                    "use_half": False
                }
            )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✓ 任务创建成功")
            print(f"  任务ID: {result['task_id']}")
            print(f"  状态: {result['status']}")
            return result['task_id']
        else:
            print(f"✗ 任务创建失败: {response.text}")
            return None
    except Exception as e:
        print(f"✗ 请求失败: {e}")
        return None

def test_generate_text():
    """测试文本生成接口"""
    print(f"\n测试文本生成接口...")
    
    try:
        response = requests.post(
            f"{API_URL}/api/generate-text",
            data={
                "title": "测试音频",
                "description": "海浪拍打岸边的声音，伴随着海鸥的叫声",
                "duration": 8.0,
                "use_half": False
            }
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✓ 任务创建成功")
            print(f"  任务ID: {result['task_id']}")
            print(f"  状态: {result['status']}")
            return result['task_id']
        else:
            print(f"✗ 任务创建失败: {response.text}")
            return None
    except Exception as e:
        print(f"✗ 请求失败: {e}")
        return None

def test_status(task_id):
    """测试状态查询"""
    print(f"\n测试状态查询...")
    
    max_attempts = 60
    attempt = 0
    
    while attempt < max_attempts:
        try:
            response = requests.get(f"{API_URL}/api/status/{task_id}")
            
            if response.status_code == 200:
                status = response.json()
                print(f"  [{attempt+1}/{max_attempts}] 状态: {status['status']} - {status['message']}")
                
                if status['status'] == 'completed':
                    print(f"✓ 任务完成")
                    return True
                elif status['status'] == 'failed':
                    print(f"✗ 任务失败: {status.get('error')}")
                    return False
            else:
                print(f"✗ 查询失败: {response.text}")
                return False
                
        except Exception as e:
            print(f"✗ 请求失败: {e}")
            return False
        
        attempt += 1
        time.sleep(5)
    
    print(f"✗ 超时: 任务未在预期时间内完成")
    return False

def test_download(task_id):
    """测试下载接口"""
    print(f"\n测试下载接口...")
    
    # 下载视频
    try:
        response = requests.get(f"{API_URL}/api/download/{task_id}")
        if response.status_code == 200:
            output_video = f"test_result_{task_id}.mp4"
            with open(output_video, "wb") as f:
                f.write(response.content)
            print(f"✓ 视频下载成功: {output_video}")
        else:
            print(f"✗ 视频下载失败: {response.text}")
            return False
    except Exception as e:
        print(f"✗ 视频下载失败: {e}")
        return False
    
    # 下载音频
    try:
        response = requests.get(f"{API_URL}/api/audio/{task_id}")
        if response.status_code == 200:
            output_audio = f"test_audio_{task_id}.wav"
            with open(output_audio, "wb") as f:
                f.write(response.content)
            print(f"✓ 音频下载成功: {output_audio}")
        else:
            print(f"✗ 音频下载失败: {response.text}")
            return False
    except Exception as e:
        print(f"✗ 音频下载失败: {e}")
        return False
    
    return True

def test_list_tasks():
    """测试任务列表"""
    print(f"\n测试任务列表...")
    
    try:
        response = requests.get(f"{API_URL}/api/tasks")
        if response.status_code == 200:
            result = response.json()
            print(f"✓ 获取任务列表成功")
            print(f"  总任务数: {result['total']}")
            for task in result['tasks'][:5]:  # 只显示前5个
                print(f"    - {task['task_id']}: {task['status']}")
            return True
        else:
            print(f"✗ 获取失败: {response.text}")
            return False
    except Exception as e:
        print(f"✗ 请求失败: {e}")
        return False

def test_delete(task_id):
    """测试删除接口"""
    print(f"\n测试删除接口...")
    
    try:
        response = requests.delete(f"{API_URL}/api/tasks/{task_id}")
        if response.status_code == 200:
            result = response.json()
            print(f"✓ 任务删除成功: {result['message']}")
            return True
        else:
            print(f"✗ 删除失败: {response.text}")
            return False
    except Exception as e:
        print(f"✗ 请求失败: {e}")
        return False

def main():
    print("=" * 60)
    print("ThinkSound API 测试")
    print("=" * 60)
    
    # 检查参数
    mode = "text"  # 默认测试文本模式
    video_path = None
    
    if len(sys.argv) >= 2:
        if sys.argv[1] in ["text", "video"]:
            mode = sys.argv[1]
            if mode == "video" and len(sys.argv) < 3:
                print("\n用法: python test_api.py video <video_path>")
                print("示例: python test_api.py video demo.mp4")
                sys.exit(1)
            elif mode == "video":
                video_path = sys.argv[2]
        else:
            # 兼容旧版本，直接提供视频路径
            mode = "video"
            video_path = sys.argv[1]
    
    print(f"测试模式: {mode}")
    
    # 1. 测试服务健康
    if not test_health():
        print("\n请先启动 API 服务: python api_server.py")
        sys.exit(1)
    
    # 2. 测试生成
    if mode == "video":
        task_id = test_generate_video(video_path)
    else:
        task_id = test_generate_text()
    
    if not task_id:
        sys.exit(1)
    
    # 3. 测试状态查询
    if not test_status(task_id):
        sys.exit(1)
    
    # 4. 测试下载
    if not test_download(task_id):
        sys.exit(1)
    
    # 5. 测试任务列表
    test_list_tasks()
    
    # 6. 测试删除（可选）
    # test_delete(task_id)
    
    print("\n" + "=" * 60)
    print("所有测试完成!")
    print("=" * 60)
    print("\n提示:")
    print("  - 测试文本模式: python test_api.py text")
    print("  - 测试视频模式: python test_api.py video <video_path>")

if __name__ == "__main__":
    main()
