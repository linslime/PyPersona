import torch
print(torch.__version__)

import torch
print(torch.cuda.is_available())  # 检查是否有可用的 CUDA 设备
print(torch.cuda.current_device())  # 查看当前使用的设备编号（如果有）
print(torch.cuda.get_device_name(0))  # 获取 GPU 的名称（如果有）

import torch
x = torch.rand(5, 3)
print(x)

# 简单运算
y = torch.rand(5, 3)
z = x + y
print(z)

import torch
if torch.cuda.is_available():
    device = torch.device("cuda")
    x = torch.rand(5, 3).to(device)  # 将张量移到 GPU 上
    print(x)
else:
    print("CUDA is not available.")
