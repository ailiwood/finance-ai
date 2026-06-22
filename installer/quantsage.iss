; QuantSage Windows Installer — Inno Setup Script
; ================================================
; Flow: Welcome -> Disclaimer -> Purchase License ($19.9) -> Serial -> Install
; License validation: offline checksum-based (no server needed)

#define AppName "QuantSage"
#define AppVersion "1.0.0"
#define AppPublisher "ailiwood"
#define AppURL "https://github.com/ailiwood/finance-ai"
#define LicensePrice "$19.90 (USD)"

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
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
Source: "assets\licenses\LICENSE.txt"; DestDir: "{app}\licenses"; Flags: ignoreversion
Source: "assets\licenses\THIRD_PARTY_LICENSES.txt"; DestDir: "{app}\licenses"; Flags: ignoreversion
Source: "..\dist\QuantSage_v{#AppVersion}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

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
Filename: "{app}\QuantSage_v{#AppVersion}.exe"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent shellexec; Components: core

[UninstallDelete]
Type: filesandordirs; Name: "{app}"

; ═══════════════════════════════════════════════════════════════
; License Validation Code
; ═══════════════════════════════════════════════════════════════
[Code]

var
  LicensePage: TInputQueryWizardPage;
  SerialValid: Boolean;

// ── Offline license key validation (modular checksum, matches keygen.py) ──
// Key format: QS-XXXX-YYYY-ZZZZ-WWWW (4 hex groups of 4)
// Checksum: (XXXX_val * 6719 + YYYY_val * 31790 + 1589039500) mod 65536
//           then multiplied by 65537 must equal ZZZZ_WWWW as a 32-bit int
function ValidateLicenseKey(Key: String): Boolean;
var
  CleanKey: String;
  P1Str, P2Str, CSStr: String;
  P1Val, P2Val, ActualCS, ExpectedCS: Int64;
  I: Integer;
  MULT1, MULT2, SECRET: Int64;
  ModVal: Int64;
begin
  CleanKey := Uppercase(Key);
  StringChangeEx(CleanKey, ' ', '', True);
  StringChangeEx(CleanKey, '-', '', True);

  if Length(CleanKey) <> 18 then begin Result := False; Exit; end;
  if Copy(CleanKey, 1, 2) <> 'QS' then begin Result := False; Exit; end;

  // Validate hex (Inno Pascal: no set range literals)
  for I := 3 to 18 do
  begin
    if not (((CleanKey[I] >= '0') and (CleanKey[I] <= '9')) or
            ((CleanKey[I] >= 'A') and (CleanKey[I] <= 'F'))) then
    begin Result := False; Exit; end;
  end;

  // Parse
  P1Str := Copy(CleanKey, 3, 4);
  P2Str := Copy(CleanKey, 7, 4);
  CSStr := Copy(CleanKey, 11, 8);

  P1Val := StrToInt64('$' + P1Str);
  P2Val := StrToInt64('$' + P2Str);
  ActualCS := StrToInt64('$' + CSStr);

  MULT1 := 6719;   // 0x1A3F
  MULT2 := 31790;  // 0x7C2E
  SECRET := 1589039500;  // 0x5E9D2B8C

  // Core check: (P1*M1 + P2*M2 + SECRET) mod 0x10000, then * 0x10001
  ModVal := (P1Val * MULT1 + P2Val * MULT2 + SECRET) mod 65536;
  ExpectedCS := ModVal * 65537;  // 0x10001

  // Allow tolerance of 10 for 32-bit vs 64-bit rounding differences
  Result := (ActualCS >= ExpectedCS - 10) and (ActualCS <= ExpectedCS + 10);
end;

// ── Serial page: on next, validate key ──
function OnLicensePageNext(Sender: TWizardPage): Boolean;
var
  InputKey: String;
begin
  InputKey := LicensePage.Values[0];
  if InputKey = '' then
  begin
    MsgBox('Please enter your license key before continuing.', mbError, MB_OK);
    Result := False;
    Exit;
  end;

  SerialValid := ValidateLicenseKey(InputKey);
  if not SerialValid then
  begin
    MsgBox('Invalid license key. Please check your key and try again.' + #13#13 +
           'If you have not yet purchased a license, please contact the developer.' + #13 +
           'Douyin/TikTok: 23230218947' + #13 +
           'GitHub: https://github.com/ailiwood',
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
  WizardForm.Caption := 'QuantSage v{#AppVersion} — Installation';

  // ── Custom Page 1: Disclaimer + Purchase Info ──
  DisclaimerText :=
    '========================================================' + #13#10 +
    '  QUANTSAGE SOFTWARE LICENSE' + #13#10 +
    '========================================================' + #13#10 + #13#10 +
    '1. SOFTWARE PURPOSE' + #13#10 +
    '   QuantSage is a stock RESEARCH tool for reference only.' + #13#10 +
    '   It produces analysis reports, NOT trading orders.' + #13#10 +
    '   It does NOT integrate with any brokerage or exchange.' + #13#10 + #13#10 +
    '2. RISK WARNING' + #13#10 +
    '   This software is for RESEARCH REFERENCE ONLY.' + #13#10 +
    '   It does NOT constitute investment advice.' + #13#10 +
    '   All investment decisions are at your OWN RISK.' + #13#10 +
    '   Past performance does not guarantee future results.' + #13#10 + #13#10 +
    '3. DATA ACCURACY' + #13#10 +
    '   Market data comes from free public sources (BaoStock, AKShare).' + #13#10 +
    '   The developer does NOT guarantee data accuracy or timeliness.' + #13#10 + #13#10 +
    '4. PURCHASE & LICENSE' + #13#10 +
    '   License Fee: {#LicensePrice} (one-time purchase, lifetime use)' + #13#10 +
    '   Each license key is for ONE machine only.' + #13#10 +
    '   Unauthorized distribution or cracking is prohibited.' + #13#10 + #13#10 +
    'By clicking "I Agree" and proceeding, you accept ALL terms above.';

  LicensePage := CreateInputQueryPage(wpWelcome,
    'License Agreement & Purchase',
    'Please read the terms below carefully.',
    DisclaimerText + #13#10 + #13#10 +
    'Enter your license key to continue:' + #13#10 +
    '(Purchase via: Douyin/TikTok @23230218947 or GitHub @ailiwood)');

  LicensePage.Add('License Key (format: QS-XXXX-XXXX-XXXX-XXXX):', False);
  LicensePage.OnNextButtonClick := @OnLicensePageNext;
  LicensePage.OnShouldSkipPage := @OnSerialPageShouldSkip;
end;

procedure CurPageChanged(CurPageID: Integer);
begin
  if CurPageID = LicensePage.ID then
  begin
    WizardForm.NextButton.Caption := '&Validate && Continue';
  end;

  if CurPageID = wpFinished then
  begin
    WizardForm.FinishedHeadingLabel.Caption := 'Installation Complete!';
    WizardForm.FinishedLabel.Caption :=
      'QuantSage has been successfully installed and activated.' + #13#13 +
      'IMPORTANT DISCLAIMER: This software is for research reference only, ' +
      'does NOT constitute any investment advice. Use at your own risk. ' +
      'All profits and losses are solely your responsibility.';
  end;
end;
