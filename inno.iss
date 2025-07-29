#define GetVersion(FileName) \
  Local[0] = FileOpen(FileName), \
  Local[1] = FileRead(Local[0]), \
  FileClose(Local[0]), \
  Local[2] = Trim(Copy(Local[1], Pos(": ", Local[1]) + 2, 100)), \
  Local[2]

#define MyAppName "Hydroscope"
#define MyAppPublisher "NIWA"
#define MyAppURL "https://earthsciences.co.nz"
#define MyAppExeName "hydroscope.exe"
#define MyAppVersion GetVersion("bin\version.txt")




[Setup]
AppId={{710723FD-D7D5-444C-885C-8C442239DD97}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputBaseFilename=hydroscopesetup-{#MyAppVersion}
SetupIconFile=dist\hydroscope\_internal\hydroscope.ico
Compression=lzma
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "dist\hydroscope\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

