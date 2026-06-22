; Inno Setup — Simplified Chinese language messages
; Minimal set covering all pages shown in the installer.

[LangOptions]
LanguageName=Simplified Chinese
LanguageID=$0804
LanguageCodePage=936
DialogFontName=Microsoft YaHei
DialogFontSize=9
TitleFontName=Microsoft YaHei
TitleFontSize=12

[Messages]

; ── Setup Wizard ──
SetupWindowTitle=QuantSage 安装向导
SelectDirLabel3=安装程序将把 [name] 安装到以下文件夹。
DiskSpaceMBLabel=至少需要 [mb] MB 的可用磁盘空间。
CannotCreateDir=安装程序无法创建文件夹 "%1"

; ── Buttons ──
ButtonNext=下一步(&N) >
ButtonBack=< 上一步(&B)
ButtonInstall=安装(&I)
ButtonCancel=取消
ButtonFinish=完成(&F)
ButtonYes=是(&Y)
ButtonNo=否(&N)

; ── Welcome Page ──
WelcomeLabel1=欢迎使用 [name] 安装向导
WelcomeLabel2=本程序将在您的计算机上安装 [name/ver]。%n%n建议在继续安装前关闭所有其他应用程序。

; ── Component Selection ──
SelectComponentsLabel2=选择要安装的组件。取消勾选您不需要的组件。完成后点击"下一步"。
ComponentsDiskSpaceMBLabel=当前所选组件至少需要 [mb] MB 磁盘空间。

; ── Installation Progress ──
InstallingLabel=请稍候，正在安装 [name]...
FinishedHeadingLabel=[name] 安装完成
FinishedLabelNoIcons=安装程序已在您的计算机上成功安装 [name]。
ClickFinish=点击"完成"退出安装程序。

; ── Misc ──
StatusExtractFiles=正在解压文件...
StatusCreateDirs=正在创建目录...
StatusCreateIcons=正在创建快捷方式...
ExitSetupTitle=退出安装程序
ExitSetupMessage=安装尚未完成。如果现在退出，程序将不会被安装。%n%n您可以稍后再次运行本安装程序以完成安装。%n%n确定要退出吗？
AboutSetupMenuItem=关于安装程序(&A)...
AboutSetupTitle=关于安装程序
AboutSetupMessage=%1 版本 %2%n%n基于 Inno Setup
HelpTextNote=本安装程序由 Inno Setup 提供支持。要了解如何使用 Inno Setup 制作自己的安装程序，请访问 Inno Setup 官网。

; ── Error messages ──
MissingParams=缺少参数。%n%n用法: %1 /?
InvalidParameter=无效参数: %1
SetupAppRunningError=安装程序检测到 [name] 正在运行。%n%n请关闭所有 [name] 实例，然后点击"确定"继续，或点击"取消"退出。
UninstallAppRunningError=卸载程序检测到 [name] 正在运行。%n%n请关闭所有 [name] 实例，然后点击"确定"继续，或点击"取消"退出。
