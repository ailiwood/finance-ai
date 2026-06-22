; QuantSage Windows Installer — Inno Setup Script
; ================================================
; Flow: Welcome -> Disclaimer -> Purchase License -> Serial -> Install
; License validation: offline 16-bit checksum (no server needed)
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
; Alipay QR code — displayed on license purchase page
Source: "assets\pay_qr.bmp"; DestDir: "{tmp}"; Flags: ignoreversion dontcopy nocompression

[Tasks]
Name: "desktopicon"; Description: "Create &desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: checkedonce
Name: "startmenu"; Description: "Add to &Start Menu"; GroupDescription: "Additional shortcuts:"; Flags: checkedonce

[Types]
Name: "minimal"; Description: "Minimal (core app only)"
Name: "custom"; Description: "Custom installation"; Flags: iscustom

[Components]
Name: "core"; Description: "QuantSage Core Application"; Types: minimal custom; Flags: fixed

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\QuantSage_v{#AppVersion}.exe"; WorkingDir: "{app}"; Flags: useapppaths; Tasks: startmenu
Name: "{commondesktop}\{#AppName}"; Filename: "{app}\QuantSage_v{#AppVersion}.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\QuantSage_v{#AppVersion}.exe"; Description: "启动 {#AppName}"; Flags: nowait postinstall skipifsilent shellexec; Components: core

[UninstallDelete]
Type: filesandordirs; Name: "{app}"

; ═══════════════════════════════════════════════════════════════
; License Validation Code
; ═══════════════════════════════════════════════════════════════
[Code]

var
  LicensePage: TInputQueryWizardPage;
  QrImage: TBitmapImage;
  SerialValid: Boolean;

// ── Offline license key validation (16-bit math, safe for Pascal) ──
// Key format: QS-XXXX-YYYY-ZZZZ-WWWW
// Checksum (16-bit): ZZZZ = (XXXX_val + YYYY_val + 0x5E9D) mod 65536
// Inverse:         WWWW = 0xFFFF - ZZZZ
// All operations stay within 32-bit integers — safe for Pascal Int64.
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

  // Validate all hex chars
  for I := 3 to 18 do
  begin
    if not (((CleanKey[I] >= '0') and (CleanKey[I] <= '9')) or
            ((CleanKey[I] >= 'A') and (CleanKey[I] <= 'F'))) then
    begin Result := False; Exit; end;
  end;

  // Parse — use StrToInt (32-bit), all values are 0-65535
  P1Val := StrToInt('$' + Copy(CleanKey, 3, 4));     // XXXX
  P2Val := StrToInt('$' + Copy(CleanKey, 7, 4));     // YYYY
  CSVal := StrToInt('$' + Copy(CleanKey, 11, 4));    // ZZZZ
  InvVal := StrToInt('$' + Copy(CleanKey, 15, 4));   // WWWW

  // Core check: ZZZZ = (P1 + P2 + 0x5E9D) mod 65536
  ExpectedCS := (P1Val + P2Val + 24221) mod 65536;   // 0x5E9D = 24221
  ExpectedInv := (65535 - ExpectedCS);                 // 0xFFFF - CS

  // Exact match required — no tolerance needed with pure 16-bit math
  Result := (CSVal = ExpectedCS) and (InvVal = ExpectedInv);
end;

// ── Serial page: on next, validate key ──
function OnLicensePageNext(Sender: TWizardPage): Boolean;
var
  InputKey: String;
begin
  InputKey := LicensePage.Values[0];
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
           '如尚未购买，请联系开发者获取：' + #13 +
           '抖音号：23230218947',
           mbError, MB_OK);
    Result := False;
  end
  else
    Result := True;
end;

function OnSerialPageShouldSkip(Sender: TWizardPage): Boolean;
begin
  // Skip serial page once validated
  Result := SerialValid;
end;

// ── Initialize ──
procedure InitializeWizard;
var
  DisclaimerText: String;
begin
  WizardForm.Caption := 'QuantSage v{#AppVersion} — 购买许可证';

  // Extract Alipay QR code to temp folder for display
  ExtractTemporaryFile('pay_qr.bmp');

  // ── Custom Page: License Purchase ──
  DisclaimerText :=
    '========================================================' + #13#10 +
    '  QuantSage — 软件许可协议与风险告知' + #13#10 +
    '========================================================' + #13#10 + #13#10 +
    '1. 软件用途：QuantSage 是股票研究辅助工具，产出研究报告，' + #13#10 +
    '   不集成任何实盘下单功能，不连接任何券商。' + #13#10 + #13#10 +
    '2. 风险警告：本软件仅供参考研究，不构成任何投资建议。' + #13#10 +
    '   所有投资决策请自行判断，盈亏自负。' + #13#10 + #13#10 +
    '3. 许可证：{#LicensePrice} 一次性买断，终身使用。' + #13#10 +
    '   禁止未经授权的分发或破解。' + #13#10 + #13#10 +
    '继续安装即表示您接受以上全部条款。';

  LicensePage := CreateInputQueryPage(wpWelcome,
    '购买许可证 — {#LicensePrice}',
    DisclaimerText,
    '激活步骤：1. 用手机扫描下方支付宝收款码 → 2. 支付 {#LicensePrice} → ' +
    '3. 联系开发者获取 License Key（抖音：23230218947）→ ' +
    '4. 在下方输入 Key 解锁安装');

  // Display Alipay QR code image on the page
  QrImage := TBitmapImage.Create(WizardForm);
  QrImage.Parent := LicensePage.Surface;
  QrImage.Left := ScaleX(40);
  QrImage.Top := ScaleY(0);
  QrImage.Width := ScaleX(280);
  QrImage.Height := ScaleY(280);
  QrImage.Stretch := True;
  QrImage.Bitmap.LoadFromFile(ExpandConstant('{tmp}\pay_qr.bmp'));

  // Push the input field down below the QR image
  LicensePage.Add('许可证密钥 (格式: QS-XXXX-XXXX-XXXX-XXXX):', False);
  LicensePage.Values[0] := '';
  LicensePage.OnNextButtonClick := @OnLicensePageNext;
  LicensePage.OnShouldSkipPage := @OnSerialPageShouldSkip;
end;

procedure CurPageChanged(CurPageID: Integer);
begin
  if CurPageID = LicensePage.ID then
  begin
    WizardForm.NextButton.Caption := '验证并继续(&V)';
  end;

  if CurPageID = wpFinished then
  begin
    WizardForm.FinishedHeadingLabel.Caption := '安装完成！';
    WizardForm.FinishedLabel.Caption :=
      'QuantSage 已成功安装并激活。' + #13#13 +
      '重要提示：本软件仅供参考研究，不构成任何投资建议，盈亏自负。';
  end;
end;
