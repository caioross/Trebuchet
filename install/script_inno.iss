; Script para Instalador Completo (Incluindo Modelos)
; Localização: /install/setup.iss

#define MyAppName "Trebuchet AI"
#define MyAppVersion "4.0"
#define MyAppPublisher "Caio Ross"
#define MyAppExeName "main.py"

[Setup]
AppId={{TREBUCHET-V4-AUTO-INSTALL}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=admin
OutputDir=.
OutputBaseFilename=Instalador_Trebuchet_Full
Compression=lzma2/ultra64
SolidCompression=yes
DiskSpanning=yes

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "install,venv,.git,.gitignore,.vscode,__pycache__,*.spec,build,dist,*.iss"
Source: "setup_installer.py"; DestDir: "{app}\install"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\venv\Scripts\python.exe"; Parameters: """{app}\main.py"""; WorkingDir: "{app}"; IconFilename: "{app}\public\logo_trebuchet.ico"
Name: "{commondesktop}\{#MyAppName}"; Filename: "{app}\venv\Scripts\python.exe"; Parameters: """{app}\main.py"""; WorkingDir: "{app}"; IconFilename: "{app}\public\logo_trebuchet.ico"; Tasks: desktopicon

[Run]

Filename: "cmd.exe"; Parameters: "/c python --version"; StatusMsg: "Verificando Python..."; Flags: runhidden; Check: PythonNotInstalled

Filename: "cmd.exe"; Parameters: "/k python install/setup_installer.py"; WorkingDir: "{app}"; StatusMsg: "Configurando ambiente e hardware..."; Flags: runascurrentuser waituntilterminated

Filename: "{app}\venv\Scripts\python.exe"; Parameters: "main.py"; WorkingDir: "{app}"; Description: "Iniciar Trebuchet agora"; Flags: nowait postinstall skipifsilent

[Code]
function PythonInstalled: Boolean;
var
  ResultCode: Integer;
begin
  Result := Exec('cmd.exe', '/c python --version', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Result := (ResultCode = 0);
end;

function PythonNotInstalled: Boolean;
begin
  Result := not PythonInstalled;
end;

procedure InitializeWizard;
begin
  if PythonNotInstalled then
  begin
    MsgBox('Erro Crítico: Python 3.10+ não detectado.' + #13#10 +
           'Por favor, instale o Python e adicione ao PATH antes de instalar o Trebuchet.', mbCriticalError, MB_OK);
  end;
end;