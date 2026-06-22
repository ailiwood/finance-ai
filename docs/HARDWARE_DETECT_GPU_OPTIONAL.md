# HARDWARE_DETECT_GPU_OPTIONAL.md — 硬件检测 + GPU 可选升级方案

> 放到项目 `docs/`。目标:CPU 版开箱即用 + 自动检测显卡 + 引导式 GPU 升级(非强制全自动)。

---

## 一、设计原则:CPU 默认 + 检测引导 + 用户主动升级

不要做"安装时全自动装 CUDA"——CUDA 版 torch 体积大(2-3GB)、强依赖用户驱动版本,全自动安装失败率高、不可控,会产生大量"装了跑不了"的问题。

采用三层方案(稳健):

| 层级 | 做法 | 风险 |
|------|------|------|
| 基础(默认) | 安装包内置 **CPU 版 torch**,人人能跑,开箱即用 | 低 |
| 检测(自动) | 应用启动时检测 N 卡,**显示**"可升级GPU加速",只提示不强装 | 低 |
| 升级(半自动) | 用户点"升级GPU版" → 程序执行 GPU torch 安装 + 驱动检测,失败回退CPU | 中(有回退兜底) |

核心:**检测是自动零风险的;真正装 GPU 版是用户主动选择且可失败回退。**

---

## 二、为什么放在"应用启动后"而非"安装程序里"
- 安装程序(Inno Setup)里跑 GPU 检测 + pip 安装别扭,失败用户更懵。
- 应用内检测可直观显示("当前CPU模式 / 检测到RTX5070Ti,可升级"),升级有进度和报错。
- CPU 版先跑起来,用户立刻可用;升级是渐进、不阻塞的。

---

## 三、实现

### 1. 硬件检测(启动时,自动,零风险)
```python
def detect_hardware():
    info = {"has_nvidia": False, "gpu_name": None, "torch_build": None, "device": "cpu"}
    # 检测 NVIDIA 显卡(即使没装CUDA版torch也能查)
    try:
        import subprocess
        r = subprocess.run(["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
                           capture_output=True, text=True, timeout=5)
        if r.returncode == 0 and r.stdout.strip():
            info["has_nvidia"] = True
            info["gpu_name"] = r.stdout.strip().splitlines()[0]
    except Exception:
        pass
    # 检测当前 torch 是否能用 cuda
    try:
        import torch
        info["torch_build"] = "cuda" if torch.version.cuda else "cpu"
        if torch.cuda.is_available():
            info["device"] = "cuda"
    except Exception:
        pass
    return info
```

### 2. UI 显示与引导
- 侧边栏/设置页显示:
  - 无N卡:`💻 当前:CPU 模式(适用于所有电脑)`
  - 有N卡但装的是CPU版torch:`🎮 检测到显卡 {gpu_name},当前CPU模式。可升级GPU版获得更快的K线预测速度 [升级GPU版]`
  - 有N卡且已是GPU版:`⚡ GPU 加速已启用({gpu_name})`

### 3. GPU 升级(半自动,用户点击触发)
```python
def upgrade_to_gpu():
    """用户主动点击。执行 GPU 版 torch 安装。失败回退,不破坏现有CPU环境。"""
    # 1) 再次确认有 N 卡
    # 2) 提示用户:将下载约2-3GB,需要较新的NVIDIA驱动,过程几分钟
    # 3) 执行(示例,CUDA 版本号按主流驱动选,如 cu121/cu124):
    #    pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124
    # 4) 安装后用 torch.cuda.is_available() 验证;成功提示重启应用,失败回退说明
    ...
```
要点:
- 升级前明确告知:体积、耗时、需要较新驱动。
- 升级失败(驱动太旧/CUDA不匹配)→ 给清晰中文提示,**保持CPU版可用**,不让用户卡死。
- 不强制:用户不升级,CPU 版照常全功能可用(只是 Kronos 慢些)。

### 4. 设备选择仍用 pick_device()
无论 CPU/GPU 版,推理时都用 pick_device() 自动选,严禁硬编码 cuda。

---

## 四、打包
- 安装包内置 **CPU 版 torch**(默认,人人可跑,体积小)。
- 不在安装包里塞 CUDA 版(太大且多数用户用不上)。
- GPU 升级走应用内按需安装(联网下载)。

---

## 五、验证
1. 无N卡机器(或 CUDA_VISIBLE_DEVICES=-1 模拟):显示CPU模式,两插件能跑。
2. 有N卡机器(你的5070Ti):检测到显卡并显示可升级;升级后 torch.cuda.is_available()=True,Kronos走GPU更快。
3. 升级失败场景:给清晰提示且CPU版仍可用。
