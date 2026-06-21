# PACKAGING_FIXES.md — 打包与安装器修复指导

> 放到项目 `docs/` 下。CC 实施任务 1、任务 2 时严格参照本文件。

---

## 一、修复 `No module named 'unittest'`(及同类标准库被排除)

### 根因
fpdf 的导入链 `fpdf → output.py → sign.py` 在模块顶层 `import unittest`。PyInstaller 的默认行为会把 `unittest`、`test`、`lib2to3`、`pydoc` 等"测试/开发"模块当作不需要的东西排除,导致打包后运行时找不到。onedir 不会自动修复这个——它只是把"打进去的东西"以文件夹形式存放,没打进去的照样缺。

### 修复(改 pyinstaller_quantsage.spec)
```python
from PyInstaller.utils.hooks import collect_all, copy_metadata

datas, binaries, hiddenimports = [], [], []

# 1) 把被默认排除的标准库测试模块显式加回
hiddenimports += [
    "unittest",
    "unittest.mock",
]

# 2) 收全 fpdf(注意发行名可能是 fpdf 或 fpdf2)
for pkg in ["fpdf", "fpdf2", "reportlab", "PIL", "Pillow", "svglib", "defusedxml", "fontTools"]:
    try:
        d, b, h = collect_all(pkg)
        datas += d; binaries += b; hiddenimports += h
    except Exception:
        pass

# 3) 关键:检查 Analysis(...) 的 excludes 参数,
#    确保里面没有 'unittest'。若有,删除它。
# excludes=[...]  ← 不要排除 unittest / unittest.mock
```

### 额外:让 PDF 导出"惰性 + 降级"(改 home.py)
不要在 home.py 顶层 import 导出模块。改成:
```python
# 在"导出PDF"按钮的回调里:
def on_export_pdf(report):
    try:
        from src.report.pdf_exporter import export_report_pdf
        path = export_report_pdf(report)
        st.success(f"已导出: {path}")
    except Exception as e:
        st.error("PDF 导出组件当前不可用,请改用 Markdown 导出。")
        # 记录到日志,但不要让它影响主分析流程
        logger.warning(f"PDF export unavailable: {e}")
```
Markdown 导出同理(它依赖少,通常更稳,可作为默认推荐)。

### 自检
- 在开发机 `python -c "import unittest, fpdf"` 不报错。
- 打包后由开发者(我)验证点导出不再崩。

---

## 二、Inno Setup 安装器:增加用户可选项

### 目标
安装时除了选路径,还能勾选:桌面快捷方式、开始菜单、开机自启(默认关)、快速启动(可选)。

### .iss 脚本片段(installer/ 下)
```pascal
[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "快捷方式:"; Flags: checkedonce
Name: "startmenuicon"; Description: "添加到开始菜单"; GroupDescription: "快捷方式:"; Flags: checkedonce
Name: "quicklaunchicon"; Description: "创建快速启动栏图标"; GroupDescription: "快捷方式:"; Flags: unchecked
Name: "autostart"; Description: "开机时自动启动 QuantSage"; GroupDescription: "启动选项:"; Flags: unchecked

[Icons]
; 开始菜单(随 startmenuicon)
Name: "{group}\QuantSage"; Filename: "{app}\QuantSage.exe"; Tasks: startmenuicon
Name: "{group}\卸载 QuantSage"; Filename: "{uninstallexe}"
; 桌面(随 desktopicon)
Name: "{autodesktop}\QuantSage"; Filename: "{app}\QuantSage.exe"; Tasks: desktopicon
; 快速启动(随 quicklaunchicon)
Name: "{userappdata}\Microsoft\Internet Explorer\Quick Launch\QuantSage"; Filename: "{app}\QuantSage.exe"; Tasks: quicklaunchicon

[Registry]
; 开机自启(随 autostart 勾选才写注册表;卸载时自动清除)
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "QuantSage"; ValueData: """{app}\QuantSage.exe"""; Flags: uninsdeletevalue; Tasks: autostart

[Setup]
; onedir 模式:打包整个 dist\QuantSage 目录
; 确认 Source 指向 onedir 输出目录而非单个 exe
; 保持卸载进度提示,改善"卸载慢无进度"的观感
```

### 注意
- 当前是 onedir,`[Files]` 的 Source 要用 `dist\QuantSage\*` 递归 (`Flags: recursesubdirs`),Filename 快捷方式指向 `{app}\QuantSage.exe`。
- `checkedonce` 让默认勾选但用户可取消。

---

## 三、卸载慢的观感改善
Inno Setup 默认有卸载进度条。若之前被关闭,确认 `[Setup]` 未设 `Uninstallable=no` 之类;可在卸载开始加一句提示:
```pascal
[Messages]
ConfirmUninstall=确定要卸载 QuantSage 吗?组件较多,卸载可能需要 1-2 分钟,请耐心等待。
```

---

## 四、本轮不强求、但建议记录的事项
- 若点"分析"后仍偶发缺其它动态依赖(langchain/tiktoken/akshare 等),按本文件第一节同样方式 collect_all + hiddenimports 补齐,逐个收敛。
- onedir 模式下,资源路径用 `sys._MEIPASS`(onedir 时指向 `_internal` 目录)解析,确认 app.py / pages / DISCLAIMER.md 等能定位到。
