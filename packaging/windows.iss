#define AppVersion GetEnv('CANTIERELINK_VERSION')
[Setup]
AppId={{17BBFD7E-3599-485D-AB3B-631888E0E516}
AppName=CantiereLink
AppVersion={#AppVersion}
AppPublisher=Nicola Silvestre
AppSupportURL=mailto:ni.silvestre91@gmail.com
DefaultDirName={localappdata}\Programs\CantiereLink
DefaultGroupName=CantiereLink
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=CantiereLink-Setup-{#AppVersion}
SetupIconFile=icon.ico
UninstallDisplayIcon={app}\CantiereLink.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes
RestartApplications=no
LicenseFile=..\LICENSE
DisableProgramGroupPage=yes
[Languages]
Name: "italian"; MessagesFile: "compiler:Languages\Italian.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"
[Tasks]
Name: "desktopicon"; Description: "Crea un collegamento sul desktop"; Flags: unchecked
[Files]
Source: "..\dist\native\CantiereLink\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
[Icons]
Name: "{group}\CantiereLink"; Filename: "{app}\CantiereLink.exe"
Name: "{autodesktop}\CantiereLink"; Filename: "{app}\CantiereLink.exe"; Tasks: desktopicon
[Run]
Filename: "{app}\CantiereLink.exe"; Description: "Apri CantiereLink"; Flags: nowait postinstall skipifsilent
