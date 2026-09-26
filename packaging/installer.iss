; Inno Setup script for the Windows installer — built by packaging/build-windows.ps1.
;   iscc /DAppVersion=1.1.0 packaging\installer.iss
; Input:  dist\ReadingPacer\  (PyInstaller one-folder build)
; Output: dist\ReadingPacer-Setup-<version>.exe
;
; Installs per-user (no admin prompt) to %LOCALAPPDATA%\Programs\ReadingPacer,
; adds Start Menu (and optional desktop) shortcuts, and registers an
; uninstaller in Settings > Apps. Running a newer installer over an existing
; install upgrades it in place — that is how the in-app updater works.

#ifndef AppVersion
  #error Pass the version: iscc /DAppVersion=x.y.z installer.iss
#endif

#define AppName "Reading Pacer"
#define AppExe "ReadingPacer.exe"
#define AppUrl "https://github.com/aaronorelup/reading-pacer"

[Setup]
; Never change AppId — it is how upgrades and the uninstaller find this app.
AppId={{E960C5A7-87AF-41E9-8DD1-E86E8DF6B9A0}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=Bloodtailor
AppPublisherURL={#AppUrl}
AppSupportURL={#AppUrl}/issues
AppUpdatesURL={#AppUrl}/releases
VersionInfoVersion={#AppVersion}
DefaultDirName={localappdata}\Programs\ReadingPacer
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
DisableDirPage=auto
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=ReadingPacer-Setup-{#AppVersion}
SetupIconFile=..\reading_pacer\assets\icon.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
LicenseFile=..\LICENSE
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
; Close a running copy before replacing files (used by the in-app updater).
CloseApplications=force
RestartApplications=no

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: unchecked

[InstallDelete]
; Versions before 1.1 were a single-file exe; clear old program files on upgrade.
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "..\dist\ReadingPacer\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
; Interactive installs: a "Launch Reading Pacer" checkbox on the last page.
Filename: "{app}\{#AppExe}"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent
; The in-app updater installs silently with /RELAUNCH=1 so the app reopens afterwards.
Filename: "{app}\{#AppExe}"; Flags: nowait; Check: ShouldRelaunch

[Code]
function ShouldRelaunch(): Boolean;
begin
  Result := WizardSilent() and (ExpandConstant('{param:RELAUNCH|0}') = '1');
end;

// On uninstall, ask whether to also remove settings, API key and reading history.
// Default is to keep them, so reinstalling later picks up where you left off.
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  DataDir: String;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    DataDir := ExpandConstant('{userappdata}\ReadingPacer');
    if DirExists(DataDir) and not UninstallSilent() then
      if MsgBox('Also delete your Reading Pacer settings, API key, saved progress and reading stats?' + #13#10#13#10 +
                'Choose No to keep them for a future reinstall.',
                mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
        DelTree(DataDir, True, True, True);
  end;
end;
