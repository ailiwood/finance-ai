; QuantSage Windows Installer — Inno Setup Script
; ================================================
; Flow: Welcome → Features → Agreement → Install
; License activation happens inside the app, NOT in the installer.
; Language: Simplified Chinese

#define AppName "QuantSage"
#define AppVersion "1.0.0"
#define AppPublisher "ailiwood"
#define AppURL ""

[Setup]
AppId={{B8F4A3E2-7D1C-4A9B-8E2F-6C5D4A3B2C1F}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
AppUpdatesURL={#AppURL}
DefaultDirName={localappdata}\Programs\{#AppName}
DefaultGroupName={#AppName}
PrivilegesRequired=lowest
OutputDir=..\dist\installer
OutputBaseFilename=QuantSage_Setup_v{#AppVersion}
SetupIconFile=..\src\ui\assets\logo.ico
WizardImageFile=assets\wizard.bmp
WizardSmallImageFile=assets\wizard_small.bmp
Compression=lzma2/ultra64
SolidCompression=yes
LZMAUseSeparateProcess=yes
WizardStyle=modern
SetupLogging=yes

[Languages]
Name: "chinese"; MessagesFile: "assets\ChineseSimplified.isl"

[Files]
Source: "assets\licenses\LICENSE.txt"; DestDir: "{app}\licenses"; Flags: ignoreversion
Source: "assets\licenses\THIRD_PARTY_LICENSES.txt"; DestDir: "{app}\licenses"; Flags: ignoreversion
Source: "..\dist\QuantSage_v{#AppVersion}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Types]
Name: "minimal"; Description: "标准安装"
Name: "custom"; Description: "自定义安装"; Flags: iscustom

[Components]
Name: "core"; Description: "QuantSage 核心程序（必需）"; Types: minimal custom; Flags: fixed
Name: "desktop_shortcut"; Description: "创建桌面快捷方式"; Types: minimal custom
Name: "startmenu_shortcut"; Description: "添加到开始菜单"; Types: minimal custom
Name: "autostart"; Description: "安装完成后启动 QuantSage"; Types: custom

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\QuantSage_v{#AppVersion}.exe"; WorkingDir: "{app}"; Components: startmenu_shortcut
Name: "{userdesktop}\{#AppName}"; Filename: "{app}\QuantSage_v{#AppVersion}.exe"; WorkingDir: "{app}"; Components: desktop_shortcut

[Run]
Filename: "{app}\QuantSage_v{#AppVersion}.exe"; Description: "启动 {#AppName}"; Flags: nowait postinstall skipifsilent shellexec; Components: autostart

[UninstallDelete]
Type: filesandordirs; Name: "{app}"

[Code]

var
  FeaturePage: TWizardPage;
  AgreementPage: TWizardPage;
  AgreementMemo: TRichEditViewer;
  AgreeCheck, RiskCheck: TCheckBox;

// ── Agreement page: force both checkboxes ──
function OnAgreementNext(Sender: TWizardPage): Boolean;
begin
  if not AgreeCheck.Checked then
  begin
    MsgBox('请先阅读并勾选"我已阅读并同意软件许可协议"。', mbError, MB_OK);
    Result := False;
    Exit;
  end;
  if not RiskCheck.Checked then
  begin
    MsgBox('请先阅读并勾选"我已知晓并接受全部投资风险"。', mbError, MB_OK);
    Result := False;
    Exit;
  end;
  Result := True;
end;

// ── Build all custom pages ──
procedure InitializeWizard;
var
  FeaturesText, AgreementText: String;
begin
  WizardForm.Caption := 'QuantSage v{#AppVersion} 安装向导';

  // ═══ Page 1: Features ═══
  FeaturesText :=
    '========================================================' + #13#10 +
    '  QuantSage — 智能股票研究助手' + #13#10 +
    '========================================================' + #13#10 + #13#10 +
    '核心功能：' + #13#10 +
    '  1. 多智能体 AI 分析 — 8 个专业 Agent 协作，自动生成研究报告' + #13#10 +
    '  2. 技术面分析 — 真实 K 线数据，MA/MACD/RSI/KDJ/BOLL 多周期指标' + #13#10 +
    '  3. 基本面分析 — 公司基本信息、行业分类、估值框架' + #13#10 +
    '  4. 情绪面分析 — 基于真实新闻的情绪判断' + #13#10 +
    '  5. K 线预测 — Kronos-base 深度学习模型，概率性价格预测' + #13#10 +
    '  6. 数据体检 — 与同花顺/东方财富一致的 OHLCV 数据对账' + #13#10 + #13#10 +
    '技术亮点：' + #13#10 +
    '  - 数据源：BaoStock 免费前复权 + AKShare 多源降级' + #13#10 +
    '  - AI 引擎：DeepSeek V4 大模型（需自备 API Key）' + #13#10 +
    '  - 本地运行：所有数据在本地处理，不上传、不回传' + #13#10 +
    '  - GPU 可选：无显卡也能用，有 NVIDIA 显卡可升级加速' + #13#10 + #13#10 +
    '激活说明：' + #13#10 +
    '  安装完成后打开软件，在激活页面查看设备码，' + #13#10 +
    '  使用支付宝扫码付款（备注设备码），在激活网页提交订单并获取激活码即可激活。' + #13#10 +
	    '  激活网页：https://quantsage-activation.lk166564317.workers.dev/';

  FeaturePage := CreateCustomPage(wpWelcome,
    '欢迎使用 QuantSage',
    FeaturesText);

  // ═══ Page 2: Agreement (scrollable + MANDATORY checkboxes) ═══
  AgreementText :=
    '========================================================' + #13#10 +
    '  软件许可协议与风险告知（请完整阅读）' + #13#10 +
    '========================================================' + #13#10 + #13#10 +
    '一、软件用途与功能说明' + #13#10 +
    'QuantSage 是一款本地运行的股票研究辅助软件。' + #13#10 +
    '它基于多智能体 AI 架构，自动采集公开市场数据，' + #13#10 +
    '生成技术面、基本面、情绪面的综合分析报告。' + #13#10 +
    '本软件不集成任何实盘下单功能，不连接任何券商或交易所。' + #13#10 +
    '它产出研究报告，不产出交易指令。' + #13#10 + #13#10 +
    '二、风险警告（重要！请仔细逐条阅读）' + #13#10 +
    '1. 本软件仅供参考研究，不构成任何投资建议。' + #13#10 +
    '   任何依据本软件报告做出的投资决策，均由用户自行承担后果。' + #13#10 +
    '2. 股市有风险，投资需谨慎。过往表现不代表未来收益。' + #13#10 +
    '   软件生成的任何分析观点、价格预测、趋势判断，' + #13#10 +
    '   均为基于历史数据的统计或推理结果，不保证准确性。' + #13#10 +
    '3. 本软件使用的市场数据来自免费公开数据源' + #13#10 +
    '   （BaoStock、AKShare、东方财富等）。' + #13#10 +
    '   开发者不对数据的准确性、完整性、时效性做任何保证。' + #13#10 +
    '   数据可能存在延迟、遗漏或错误。' + #13#10 +
    '4. AI 模型（DeepSeek、Kronos 等）的输出为概率性结果，' + #13#10 +
    '   非确定性结论。模型可能产生"幻觉"或错误推理。' + #13#10 +
    '   用户应独立验证关键信息，不应盲目依赖 AI 输出。' + #13#10 +
    '5. 开发者（ailiwood）不对因使用或无法使用本软件' + #13#10 +
    '   而产生的任何直接或间接损失承担责任，' + #13#10 +
    '   包括但不限于投资亏损、数据丢失、业务中断。' + #13#10 +
    '6. 用户应自行评估自身的风险承受能力，' + #13#10 +
    '   在完全理解相关风险后谨慎做出投资决策。' + #13#10 + #13#10 +
    '三、知识产权与使用限制' + #13#10 +
    '1. 本软件及其相关文档的著作权归开发者所有。' + #13#10 +
    '2. 禁止对软件进行逆向工程、反编译、破解或篡改。' + #13#10 +
    '3. 禁止未经开发者书面授权的复制、分发、出租或转售。' + #13#10 +
    '4. 每个许可证密钥仅授权在一台计算机上使用。' + #13#10 + #13#10 +
    '四、隐私与数据' + #13#10 +
    '1. 本软件在用户本地计算机运行，不会自动上传或回传任何数据。' + #13#10 +
    '2. API Key 等敏感信息仅存储在用户本地配置文件中。' + #13#10 +
    '3. 分析过程中产生的临时数据仅存在于本地内存和缓存中。' + #13#10 + #13#10 +
    '五、免责声明的完整性' + #13#10 +
    '本协议中的免责条款在适用法律允许的最大范围内生效。' + #13#10 +
    '如任何条款被认定为无效，其余条款仍具有完全效力。' + #13#10 + #13#10 +
    '========================================================' + #13#10 +
    '请在下方勾选两个选项以确认您已阅读并同意上述全部内容。';

  AgreementPage := CreateCustomPage(FeaturePage.ID,
    '许可协议与风险告知 — 请下滑完整阅读',
    '');

  // Scrollable agreement text
  AgreementMemo := TRichEditViewer.Create(WizardForm);
  AgreementMemo.Parent := AgreementPage.Surface;
  AgreementMemo.Left := ScaleX(0);
  AgreementMemo.Top := ScaleY(0);
  AgreementMemo.Width := AgreementPage.SurfaceWidth;
  AgreementMemo.Height := ScaleY(230);
  AgreementMemo.ScrollBars := ssVertical;
  AgreementMemo.ReadOnly := True;
  AgreementMemo.UseRichEdit := True;
  AgreementMemo.RTFText := AgreementText;

  // Mandatory checkboxes
  AgreeCheck := TCheckBox.Create(WizardForm);
  AgreeCheck.Parent := AgreementPage.Surface;
  AgreeCheck.Caption := '我已完整阅读并同意上述软件许可协议';
  AgreeCheck.Left := ScaleX(0);
  AgreeCheck.Top := ScaleY(240);
  AgreeCheck.Width := ScaleX(400);

  RiskCheck := TCheckBox.Create(WizardForm);
  RiskCheck.Parent := AgreementPage.Surface;
  RiskCheck.Caption := '我已知晓并接受全部投资风险，承诺盈亏自负';
  RiskCheck.Left := ScaleX(0);
  RiskCheck.Top := ScaleY(265);
  RiskCheck.Width := ScaleX(400);

  AgreementPage.OnNextButtonClick := @OnAgreementNext;
end;

procedure CurPageChanged(CurPageID: Integer);
begin
  if CurPageID = AgreementPage.ID then
    WizardForm.NextButton.Caption := '同意并继续(&A)';

  if CurPageID = wpFinished then
  begin
    WizardForm.FinishedHeadingLabel.Caption := '安装完成！';
    WizardForm.FinishedLabel.Caption :=
      'QuantSage 已成功安装。' + #13#13 +
      '首次启动时会引导您完成激活。' + #13#10 +
      '激活需提供设备码（软件内显示），支付宝扫码付款后通过激活网页获取许可证密钥。' + #13#13 +
      '重要提示：本软件仅供参考研究，不构成任何投资建议，盈亏自负。';
  end;
end;
