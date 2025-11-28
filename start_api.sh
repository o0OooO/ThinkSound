#!/bin/bash

echo "=================================="
echo "ThinkSound API 启动脚本"
echo "=================================="

# 检查 conda 环境
if ! conda info --envs | grep -q "thinksound"; then
    echo "❌ 未找到 thinksound 环境"
    echo "请先运行: conda create -n thinksound python=3.10"
    exit 1
fi

# 激活环境
echo "✓ 激活 thinksound 环境"
source $(conda info --base)/etc/profile.d/conda.sh
conda activate thinksound

# 检查依赖
echo "✓ 检查依赖..."
if ! python -c "import fastapi" 2>/dev/null; then
    echo "安装 API 依赖..."
    pip install -r requirements_api.txt
fi

# 检查模型文件
if [ ! -d "ckpts" ]; then
    echo "❌ 未找到模型文件"
    echo "请先下载模型: git clone https://huggingface.co/liuhuadai/ThinkSound ckpts"
    exit 1
fi

echo "✓ 模型文件已就绪"

# 启动服务
echo ""
echo "=================================="
echo "启动 API 服务..."
echo "=================================="
echo ""
echo "访问地址:"
echo "  - API 文档: http://localhost:8000/docs"
echo "  - ReDoc: http://localhost:8000/redoc"
echo ""
echo "按 Ctrl+C 停止服务"
echo ""

python api_server.py
