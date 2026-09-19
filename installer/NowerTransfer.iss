; Inno Setup script for the NowerTransfer installer.
;
; Not built by hand - scripts/make_installer.py passes the values below
; and runs ISCC. See `poe installer --help`.
;
; Required on the command line:
;   /DAppVersion=1.0.0        what the app calls itself
;   /DNumericVersion=1.0.0.0  file-metadata version, four numbers
;   /DSourceExe=...           the built NowerTransfer.exe
;   /DOutputDir=...           where the setup should end up

#define AppName "NowerTransfer"
#define Publisher "Nowenr"
#define HomePage "https://github.com/Nowenr/NowerTransfer"

[Setup]
; Fixed, so an upgrade replaces the previous install instead of adding
; a second entry to the installed-programs list. Never change it.
AppId={{D67C5ECC-97A8-467C-98A5-ED21D35BB391}
AppName={#AppName}
AppVersion={#AppVersion}
VersionInfoVersion={#NumericVersion}
AppPublisher={#Publisher}
AppPublisherURL={#HomePage}
AppSupportURL={#HomePage}/issues
AppUpdatesURL={#HomePage}/releases

; Installs for the current user only, which means no admin prompt. The
; app writes nothing outside the user's own profile, so nothing here
; needs elevation - and one fewer scary dialog matters for something
; handed to people who just want to receive a file.
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
; The app itself is bilingual; the installer should not be less.
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

; Settings and the resume file live in %APPDATA%\NowerTransfer and are
; deliberately left behind on uninstall: reinstalling should not mean
; typing the relay in again. They are a few hundred bytes.
