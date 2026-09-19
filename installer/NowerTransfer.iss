; Built by scripts/make_installer.py, which passes:
;   /DAppVersion=1.0.0        what the app calls itself
;   /DNumericVersion=1.0.0.0  file metadata, four numbers
;   /DSourceExe=...           the built NowerTransfer.exe
;   /DOutputDir=...           where the setup goes

#define AppName "NowerTransfer"
#define Publisher "Nowenr"
#define HomePage "https://github.com/Nowenr/NowerTransfer"

[Setup]
; Never change: an upgrade replaces the previous install by matching it.
AppId={{D67C5ECC-97A8-467C-98A5-ED21D35BB391}
AppName={#AppName}
AppVersion={#AppVersion}
VersionInfoVersion={#NumericVersion}
AppPublisher={#Publisher}
AppPublisherURL={#HomePage}
AppSupportURL={#HomePage}/issues
AppUpdatesURL={#HomePage}/releases

; Current user only, so no admin prompt. The app writes nothing outside
; the user's profile, so nothing here needs elevation.
PrivilegesRequired=lowest
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
DisableDirPage=auto

ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

OutputDir={#OutputDir}
OutputBaseFilename=NowerTransfer-{#AppVersion}-setup
SetupIconFile={#SourcePath}\..\assets\icon.ico
UninstallDisplayIcon={app}\NowerTransfer.exe
UninstallDisplayName={#AppName} {#AppVersion}

WizardStyle=modern
Compression=lzma2/max
SolidCompression=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "german"; MessagesFile: "compiler:Languages\German.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; \
    GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#SourceExe}"; DestDir: "{app}"; DestName: "NowerTransfer.exe"; \
    Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\NowerTransfer.exe"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\NowerTransfer.exe"; \
    Tasks: desktopicon

[Run]
Filename: "{app}\NowerTransfer.exe"; \
    Description: "{cm:LaunchProgram,{#AppName}}"; \
    Flags: nowait postinstall skipifsilent

; %APPDATA%\NowerTransfer is left behind on uninstall on purpose:
; reinstalling should not mean typing the relay in again.
