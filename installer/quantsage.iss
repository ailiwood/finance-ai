; QuantSage Windows Installer — Inno Setup Script
; ================================================
; Flow: Welcome → Features → Agreement (forced checkboxes) → Purchase → Config → Install
; Language: Simplified Chinese

#define AppName "QuantSage"
#define AppVersion "1.0.0"
#define AppPublisher "ailiwood"
#define AppURL ""
#define LicensePrice "19.90 RMB"

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
DisableProgramGroupPage=yes
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
Source: "assets\pay_qr.bmp"; DestDir: "{tmp}"; Flags: ignoreversion dontcopy nocompression

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "快捷方式:"; Flags: checkedonce
Name: "startmenu"; Description: "添加到开始菜单"; GroupDescription: "快捷方式:"; Flags: checkedonce

[Types]
Name: "minimal"; Description: "标准安装"
Name: "custom"; Description: "自定义安装"; Flags: iscustom

[Components]
Name: "core"; Description: "QuantSage 核心程序"; Types: minimal custom; Flags: fixed

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\QuantSage_v{#AppVersion}.exe"; WorkingDir: "{app}"; Flags: useapppaths; Tasks: startmenu
Name: "{commondesktop}\{#AppName}"; Filename: "{app}\QuantSage_v{#AppVersion}.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\QuantSage_v{#AppVersion}.exe"; Description: "启动 {#AppName}"; Flags: nowait postinstall skipifsilent shellexec; Components: core

[UninstallDelete]
Type: filesandordirs; Name: "{app}"

[Code]

var
  FeaturePage: TWizardPage;
  AgreementPage: TWizardPage;
  AgreeCheck, RiskCheck: TCheckBox;
  PurchasePage: TInputQueryWizardPage;
  QrImage: TBitmapImage;
  SerialValid: Boolean;

// ── License key validation ──
function ValidateLicenseKey(Key: String): Boolean;
var
  CleanKey: String;
  P1Val, P2Val, CSVal, InvVal: Integer;
  ExpectedCS, ExpectedInv: Integer;
  I: Integer;
begin
  CleanKey := Uppercase(Key);
  StringChangeEx(CleanKey, ' ', '', True);
  StringChangeEx(CleanKey, '-', '', True);
  if Length(CleanKey) <> 18 then begin Result := False; Exit; end;
  if Copy(CleanKey, 1, 2) <> 'QS' then begin Result := False; Exit; end;
  for I := 3 to 18 do
    if not (((CleanKey[I] >= '0') and (CleanKey[I] <= '9')) or
            ((CleanKey[I] >= 'A') and (CleanKey[I] <= 'F'))) then
    begin Result := False; Exit; end;
  P1Val := StrToInt('$' + Copy(CleanKey, 3, 4));
  P2Val := StrToInt('$' + Copy(CleanKey, 7, 4));
  CSVal := StrToInt('$' + Copy(CleanKey, 11, 4));
  InvVal := StrToInt('$' + Copy(CleanKey, 15, 4));
  ExpectedCS := (P1Val + P2Val + 24221) mod 65536;
  ExpectedInv := 65535 - ExpectedCS;
  Result := (CSVal = ExpectedCS) and (InvVal = ExpectedInv);
end;

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

// ── Purchase page: validate license key ──
function OnPurchaseNext(Sender: TWizardPage): Boolean;
var
  InputKey: String;
begin
  InputKey := PurchasePage.Values[0];
  if InputKey = '' then
  begin
    MsgBox('请输入许可证密钥。', mbError, MB_OK);
    Result := False;
    Exit;
  end;
  SerialValid := ValidateLicenseKey(InputKey);
  if not SerialValid then
  begin
    MsgBox('许可证密钥无效，请检查后重试。' + #13#13 +
           '如尚未购买，请联系开发者（抖音：23230218947）。', mbError, MB_OK);
    Result := False;
  end
  else
    Result := True;
end;

function OnPurchaseSkip(Sender: TWizardPage): Boolean;
begin
  Result := SerialValid;
end;

// ── Build all custom pages ──
procedure InitializeWizard;
var
  FeaturesText, AgreementText: String;
begin
  WizardForm.Caption := 'QuantSage v{#AppVersion} 安装向导';

  ExtractTemporaryFile('pay_qr.bmp');

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
    '  - GPU 可选：无显卡也能用，有 NVIDIA 显卡可升级加速';

  FeaturePage := CreateCustomPage(wpWelcome,
    '欢迎使用 QuantSage',
    FeaturesText);

  // ═══ Page 2: Agreement (MANDATORY checkboxes) ═══
  AgreementText :=
    '========================================================' + #13#10 +
    '  软件许可协议与风险告知（请完整阅读）' + #13#10 +
    '========================================================' + #13#10 + #13#10 +
    '一、软件用途' + #13#10 +
    'QuantSage 是股票研究辅助工具，产出分析报告供用户参考。' + #13#10 +
    '本软件不集成任何实盘下单功能，不连接任何券商或交易所。' + #13#10 + #13#10 +
    '二、风险警告（重要！请仔细阅读）' + #13#10 +
    '1. 本软件仅供参考研究，不构成任何投资建议。' + #13#10 +
    '2. 所有投资决策请自行判断，盈亏自负。' + #13#10 +
    '3. 股市有风险，投资需谨慎。过往表现不代表未来收益。' + #13#10 +
    '4. 软件提供的数据来自免费公开源（BaoStock、AKShare），' + #13#10 +
    '   开发者不保证数据的准确性、完整性和时效性。' + #13#10 +
    '5. AI 模型（Kronos）的预测为概率性结果，非确定性结论。' + #13#10 +
    '6. 开发者不对因使用本软件而产生的任何损失承担责任。' + #13#10 + #13#10 +
    '三、知识产权' + #13#10 +
    '本软件受著作权法保护。禁止逆向工程、破解、未经授权的分发。' + #13#10 + #13#10 +
    '四、许可证' + #13#10 +
    '购买许可证（{#LicensePrice}一次性买断）后获得单机使用权。';

  AgreementPage := CreateCustomPage(FeaturePage.ID,
    '许可协议与风险告知',
    AgreementText);

  // Mandatory checkboxes
  AgreeCheck := TCheckBox.Create(WizardForm);
  AgreeCheck.Parent := AgreementPage.Surface;
  AgreeCheck.Caption := '我已完整阅读并同意上述软件许可协议';
  AgreeCheck.Left := ScaleX(0);
  AgreeCheck.Top := ScaleY(0);
  AgreeCheck.Width := ScaleX(400);

  RiskCheck := TCheckBox.Create(WizardForm);
  RiskCheck.Parent := AgreementPage.Surface;
  RiskCheck.Caption := '我已知晓并接受全部投资风险，承诺盈亏自负';
  RiskCheck.Left := ScaleX(0);
  RiskCheck.Top := ScaleY(30);
  RiskCheck.Width := ScaleX(400);

  AgreementPage.OnNextButtonClick := @OnAgreementNext;

  // ═══ Page 3: Purchase ═══
  PurchasePage := CreateInputQueryPage(AgreementPage.ID,
    '购买许可证 — {#LicensePrice}',
    '请用支付宝扫描下方二维码支付 {#LicensePrice}，' +
    '然后联系开发者（抖音：23230218947）获取许可证密钥。' + #13#10 +
    '输入正确的密钥后即可解锁安装。',
    '');

  // QR code — half size, centered below
  QrImage := TBitmapImage.Create(WizardForm);
  QrImage.Parent := PurchasePage.Surface;
  QrImage.Width := ScaleX(140);
  QrImage.Height := ScaleY(140);
  QrImage.Left := (PurchasePage.SurfaceWidth - QrImage.Width) div 2;
  QrImage.Top := ScaleY(0);
  QrImage.Stretch := True;
  QrImage.Bitmap.LoadFromFile(ExpandConstant('{tmp}\pay_qr.bmp'));

  PurchasePage.Add('许可证密钥 (格式: QS-XXXX-XXXX-XXXX-XXXX):', False);
  PurchasePage.Values[0] := '';
  PurchasePage.OnNextButtonClick := @OnPurchaseNext;
  PurchasePage.OnShouldSkipPage := @OnPurchaseSkip;
end;

procedure CurPageChanged(CurPageID: Integer);
begin
  if CurPageID = AgreementPage.ID then
    WizardForm.NextButton.Caption := '同意并继续(&A)';

  if CurPageID = PurchasePage.ID then
    WizardForm.NextButton.Caption := '验证并继续(&V)';

  if CurPageID = wpFinished then
  begin
    WizardForm.FinishedHeadingLabel.Caption := '安装完成！';
    WizardForm.FinishedLabel.Caption :=
      'QuantSage 已成功安装并激活。' + #13#13 +
      '重要提示：本软件仅供参考研究，不构成任何投资建议，盈亏自负。';
  end;
end;
