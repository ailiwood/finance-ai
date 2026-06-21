; QuantSage Windows Installer — Inno Setup Script
; ================================================
; Build: iscc installer/quantsage.iss
; Requires: Inno Setup 6.3+ (https://jrsoftware.org/isinfo.php)
;
; Produces a single .exe installer with:
;   - Minimal install: core app only (~300MB)
;   - Full install: core + GPU plugins (~8GB)
;   - Custom install: user selects components

#define AppName "QuantSage"
#define AppVersion "1.0.0"
#define AppPublisher "QuantSage"
#define AppURL "https://github.com/ailiwood/finance-ai"
#define AppSupportURL "https://github.com/ailiwood/finance-ai/issues"
#define AppUpdatesURL "https://github.com/ailiwood/finance-ai/releases"

[Setup]
; Basic info
AppId={{B8F4A3E2-7D1C-4A9B-8E2F-6C5D4A3B2C1F}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppSupportURL}
AppUpdatesURL={#AppUpdatesURL}

; Install paths
DefaultDirName={localappdata}\Programs\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest

; Output
OutputDir=..\dist\installer
OutputBaseFilename=QuantSage_Setup_v{#AppVersion}
SetupIconFile=assets\quantsage.ico
WizardImageFile=assets\wizard.bmp
WizardSmallImageFile=assets\wizard_small.bmp

; Compression
Compression=lzma2/ultra64
SolidCompression=yes
LZMAUseSeparateProcess=yes

; Appearance
WizardStyle=modern
SetupLogging=yes

; Languages
[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

; License
[Files]
Source: "assets\licenses\LICENSE.txt"; DestDir: "{app}\licenses"; Flags: ignoreversion
Source: "assets\licenses\THIRD_PARTY_LICENSES.txt"; DestDir: "{app}\licenses"; Flags: ignoreversion

; Main application (built by PyInstaller — single-file exe)
Source: "..\dist\QuantSage_v{#AppVersion}.exe"; DestDir: "{app}"; Flags: ignoreversion

; ─── Component Selection ───
[Types]
Name: "minimal"; Description: "Minimal (core app only, ~300MB)"
Name: "full"; Description: "Full (core + GPU plugins, ~8GB)"
Name: "custom"; Description: "Custom installation"; Flags: iscustom

[Components]
Name: "core"; Description: "QuantSage Core Application"; Types: minimal full custom; Flags: fixed
Name: "kronos"; Description: "Kronos GPU Prediction Engine (~5.3GB)"; Types: full; ExtraDiskSpaceRequired: 5566275584
Name: "finbert"; Description: "FinBERT Sentiment Engine (~3.3GB)"; Types: full; ExtraDiskSpaceRequired: 3460300800

; ─── Shortcuts ───
[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\QuantSage_v{#AppVersion}.exe"; WorkingDir: "{app}"
Name: "{group}\访问官网"; Filename: "{#AppURL}"
Name: "{group}\卸载 {#AppName}"; Filename: "{uninstallexe}"
Name: "{commondesktop}\{#AppName}"; Filename: "{app}\QuantSage_v{#AppVersion}.exe"; WorkingDir: "{app}"

; ─── Post-install Actions ───
[Run]
; Install TradingAgents-CN from GitHub
Filename: "{cmd}"; Parameters: "/C ""pip install git+https://github.com/hsliuping/TradingAgents-CN.git@v1.0.1"""; \
    Flags: runhidden waituntilterminated; \
    StatusMsg: "Installing TradingAgents-CN analysis engine..."; \
    Components: core

; Launch QuantSage after install
Filename: "{app}\QuantSage_v{#AppVersion}.exe"; \
    Description: "启动 {#AppName}"; \
    Flags: nowait postinstall skipifsilent shellexec; \
    Components: core

; ─── Uninstall ───
[UninstallRun]
Filename: "{app}\QuantSage_v{#AppVersion}.exe"; Parameters: "--reset-config"; \
    Flags: runhidden; \
    RunOnceId: "ClearConfig"

[UninstallDelete]
Type: filesandordirs; Name: "{app}"

; ─── Pre-install Checks ───
[Code]
function InitializeSetup: Boolean;
begin
  // Disk space check: deferred to post-MVP
  // GetSpaceOnDisk API changed in Inno Setup 6.7.x and needs investigation.
  Result := True;
end;

// Custom page: welcome message
procedure InitializeWizard;
begin
  WizardForm.Caption := 'QuantSage Setup Wizard';
end;

// Disclaimer on finish page
procedure CurPageChanged(CurPageID: Integer);
begin
  if CurPageID = wpFinished then
  begin
    WizardForm.FinishedHeadingLabel.Caption := 'Installation Complete!';
    WizardForm.FinishedLabel.Caption :=
      'QuantSage has been successfully installed.' + #13#13 +
      'IMPORTANT DISCLAIMER: This software is for research reference only, ' +
      'does not constitute any investment advice. Use at your own risk. ' +
      'By using this software you accept this disclaimer.';
  end;
end;
