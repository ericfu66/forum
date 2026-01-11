#!/bin/bash

echo "========================================"
echo "安全功能依赖安装脚本"
echo "========================================"
echo ""

echo "正在安装 bleach..."
pip install bleach==6.1.0
if [ $? -ne 0 ]; then
    echo "错误: bleach 安装失败"
    exit 1
fi

echo ""
echo "正在安装 Pillow..."
pip install Pillow==10.1.0
if [ $? -ne 0 ]; then
    echo "错误: Pillow 安装失败"
    exit 1
fi

echo ""
echo "========================================"
echo "安装完成！"
echo "========================================"
echo ""
echo "已安装的包:"
pip show bleach
echo ""
pip show Pillow
echo ""
echo "下一步: 运行 python run.py 启动应用"
echo ""
