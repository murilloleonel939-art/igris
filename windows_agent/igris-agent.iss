; Inno Setup: instala IgrisAgent.exe y crea desinstalador.
#define MyAppName "IGRIS Windows Agent"
#define MyAppVersion "11.0.0"
#define MyAppPublisher "IGRIS"
#define MyAppExeName "IgrisAgent.exe"

[Setup]
AppId={{8B9C2F1D-1B1D-4B4A-9B22-7A6E4C9D1F07}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\IGRIS\agent
DisableProgramGroupPage=yes
DefaultGroupName={#MyAppName}
OutputBaseFilename=IgrisAgentSetup-v11
Compression=lzma
SolidCompression=yes
OutputDir=output
PrivilegesRequired=lowest
UninstallDisplayName=IGRIS Windows Agent
UninstallDisplayIcon={app}\IgrisAgent.exe
CreateUninstallRegKey=yes

[Files]
Source: "dist\IgrisAgent.exe"; DestDir: "{app}"; Flags: ignoreversion

[Tasks]
Name: "desktopicon"; Description: "Crear acceso directo de configuración en el escritorio"; GroupDescription: "Accesos directos:"

[Icons]
Name: "{userstartup}\IGRIS Windows Agent"; Filename: "{app}\IgrisAgent.exe"; WorkingDir: "{app}"
Name: "{group}\IGRIS Windows Agent"; Filename: "{app}\IgrisAgent.exe"; WorkingDir: "{app}"
Name: "{group}\Configurar IGRIS"; Filename: "{app}\IgrisAgent.exe"; Parameters: "--configure"; WorkingDir: "{app}"
Name: "{group}\Desinstalar IGRIS Windows Agent"; Filename: "{uninstallexe}"
Name: "{userdesktop}\Configurar IGRIS"; Filename: "{app}\IgrisAgent.exe"; Parameters: "--configure"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\IgrisAgent.exe"; Description: "Iniciar IGRIS Windows Agent"; Flags: nowait postinstall skipifsilent

[Code]
var
  TokenPage: TInputQueryWizardPage;
  TokenFile: String;

procedure InitializeWizard;
begin
  TokenPage := CreateInputQueryPage(wpSelectDir, 'Conexión de IGRIS', 'Token del agente', 'Pega el NODE_TOKEN generado en el panel de administración.');
  TokenPage.Add('NODE_TOKEN:', True);
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  TokenValue: String;
begin
  Result := '';
  TokenValue := Trim(TokenPage.Values[0]);
  if TokenValue = '' then
    Result := 'El token del agente es obligatorio. Introduce el NODE_TOKEN del panel.';
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  TokenValue: String;
  ResultCode: Integer;
begin
  if CurStep = ssInstall then
  begin
    { El agente arranca con Windows y no tiene consola: al reinstalar puede
      seguir vivo y ocupar el único puesto de conexión del servidor. Se cierra
      antes de copiar los archivos nuevos. }
    Exec(ExpandConstant('{sys}\taskkill.exe'), '/F /IM IgrisAgent.exe',
      '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  end;
  if CurStep = ssPostInstall then
  begin
    TokenValue := Trim(TokenPage.Values[0]);
    TokenFile := ExpandConstant('{localappdata}\IGRIS\node_token.txt');
    ForceDirectories(ExtractFileDir(TokenFile));
    if not SaveStringToFile(TokenFile, TokenValue, False) then
      RaiseException('No se pudo guardar la configuración del agente en el perfil de Windows.');
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  ResultCode: Integer;
begin
  if CurUninstallStep = usUninstall then
  begin
    Exec(ExpandConstant('{sys}\taskkill.exe'), '/F /IM IgrisAgent.exe',
      '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
    TokenFile := ExpandConstant('{localappdata}\IGRIS\node_token.txt');
    if FileExists(TokenFile) then
      DeleteFile(TokenFile);
  end;
end;

[UninstallDelete]
Type: files; Name: "{localappdata}\IGRIS\agent.log"
Type: files; Name: "{localappdata}\IGRIS\node_token.txt"
