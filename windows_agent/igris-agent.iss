; Inno Setup: instala IgrisAgent.exe y crea desinstalador.
#define MyAppName "IGRIS Windows Agent"
#define MyAppVersion "8.0.0"
#define MyAppPublisher "IGRIS"
#define MyAppExeName "IgrisAgent.exe"

[Setup]
AppId={{8B9C2F1D-1B1D-4B4A-9B22-7A6E4C9D1F07}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\IGRIS\agent
DisableProgramGroupPage=yes
OutputBaseFilename=IgrisAgentSetup-v8
Compression=lzma
SolidCompression=yes
OutputDir=output
PrivilegesRequired=lowest
UninstallDisplayName=IGRIS Windows Agent

[Files]
Source: "dist\IgrisAgent.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{userstartup}\IGRIS Windows Agent"; Filename: "{app}\IgrisAgent.exe"; WorkingDir: "{app}"

[Run]
Filename: "{app}\IgrisAgent.exe"; Description: "Iniciar IGRIS Windows Agent"; Flags: nowait postinstall skipifsilent

[Code]
var
  TokenPage: TInputQueryWizardPage;

procedure InitializeWizard;
begin
  TokenPage := CreateInputQueryPage(wpSelectDir, 'Conexión de IGRIS', 'Token del agente', 'Pega el NODE_TOKEN generado en el panel de administración.');
  TokenPage.Add('NODE_TOKEN:', True);
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  TokenFile: String;
begin
  if CurStep = ssPostInstall then
  begin
    TokenFile := ExpandConstant('{app}\node_token.txt');
    SaveStringToFile(TokenFile, TokenPage.Values[0], False);
  end;
end;

[UninstallDelete]
Type: files; Name: "{app}\node_token.txt"
