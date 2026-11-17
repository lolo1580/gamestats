#define MyAppName "GameStats Agent"
#define MyAppVersion "1.1.0"
#define MyAppPublisher "GameStats"
#define MyAppExeName "GameStatsAgent.exe"

[Setup]
AppId={{D7A2F5E4-0B2C-4E72-9A1D-6C9F6A3B7C21}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\GameStats Agent
DefaultGroupName=GameStats
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=dist
OutputBaseFilename=GameStatsAgentSetup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#MyAppExeName}
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
AppMutex=GameStatsAgentMutex
CloseApplications=no

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
french.ConfigTitle=Configuration GameStats
french.ConfigSubtitle=Connexion au serveur GameStats
french.ConfigDescription=Indiquez l'adresse du backend et la clé agent. La clé se trouve dans GameStats, onglet Paramètres → Général → Clé agent.
french.ServerLabel=Adresse du backend
french.KeyLabel=Clé agent
french.ServerRequired=Indiquez l'adresse du backend GameStats.
french.ServerInvalid=L'adresse doit commencer par http:// ou https://.
french.KeyRequired=Indiquez la clé agent.
french.ConfigWriteError=Impossible d'écrire la configuration :
french.StartupTask=Démarrer GameStats Agent à l'ouverture de session
french.DesktopIcon=Créer un raccourci sur le Bureau
french.AdditionalTasks=Options supplémentaires
french.TestConnection=Tester la connexion maintenant
english.ConfigTitle=GameStats configuration
english.ConfigSubtitle=GameStats server connection
english.ConfigDescription=Enter the backend address and agent key. The key is available in GameStats under Settings → General → Agent key.
english.ServerLabel=Backend address
english.KeyLabel=Agent key
english.ServerRequired=Enter the GameStats backend address.
english.ServerInvalid=The address must start with http:// or https://.
english.KeyRequired=Enter the agent key.
english.ConfigWriteError=Unable to write the configuration file:
english.StartupTask=Start GameStats Agent at sign-in
english.DesktopIcon=Create a desktop shortcut
english.AdditionalTasks=Additional options
english.TestConnection=Test the connection now

[Files]
Source: "dist\GameStatsAgent\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "games.json"; DestDir: "{userappdata}\GameStats"; DestName: "games.json"; Flags: onlyifdoesntexist uninsneveruninstall

[Tasks]
Name: "startup"; Description: "{cm:StartupTask}"; GroupDescription: "{cm:AdditionalTasks}"; Flags: checkedonce
Name: "desktopicon"; Description: "{cm:DesktopIcon}"; GroupDescription: "{cm:AdditionalTasks}"; Flags: unchecked

[Icons]
Name: "{group}\GameStats Agent"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Tester la connexion"; Filename: "{app}\{#MyAppExeName}"; Parameters: "--once"
Name: "{group}\Désinstaller GameStats Agent"; Filename: "{uninstallexe}"
Name: "{userdesktop}\GameStats Agent"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
Name: "{userstartup}\GameStats Agent"; Filename: "{app}\{#MyAppExeName}"; Tasks: startup

[Run]
Filename: "{app}\{#MyAppExeName}"; Parameters: "--once"; Description: "{cm:TestConnection}"; Flags: postinstall nowait skipifsilent

[UninstallRun]
Filename: "{cmd}"; Parameters: "/C taskkill /IM {#MyAppExeName} /F >NUL 2>&1"; Flags: runhidden; RunOnceId: "KillAgent"

[Code]
var
  ConfigPage: TInputQueryWizardPage;
  ServerValue, KeyValue: string;

function ReadJsonString(const FileName, Key: string): string;
var
  Lines: TStringList;
  Content, Pattern, Rest: string;
  P: Integer;
begin
  Result := '';
  Lines := TStringList.Create;
  try
    try
      Lines.LoadFromFile(FileName);
    except
      exit;
    end;
    Content := Lines.Text;
    Pattern := '"' + Key + '"';
    P := Pos(Pattern, Content);
    if P = 0 then
      exit;
    Rest := Copy(Content, P + Length(Pattern), Length(Content));
    P := Pos('"', Rest);
    if P = 0 then
      exit;
    Rest := Copy(Rest, P + 1, Length(Rest));
    P := Pos('"', Rest);
    if P = 0 then
      exit;
    Result := Copy(Rest, 1, P - 1);
  finally
    Lines.Free;
  end;
end;

function ParamValue(const Name, DefaultValue: string): string;
begin
  Result := ExpandConstant('{param:' + Name + '|' + DefaultValue + '}');
end;

procedure InitializeWizard;
var
  ConfigPath: string;
begin
  ConfigPage := CreateInputQueryPage(
    wpSelectDir,
    CustomMessage('ConfigTitle'),
    CustomMessage('ConfigSubtitle'),
    CustomMessage('ConfigDescription'));
  ConfigPage.Add(CustomMessage('ServerLabel'), False);
  ConfigPage.Add(CustomMessage('KeyLabel'), True);

  ConfigPage.Values[0] := ParamValue('SERVER', 'http://localhost:8091');
  ConfigPage.Values[1] := ParamValue('KEY', '');

  ConfigPath := ExpandConstant('{userappdata}\GameStats\agent.json');
  if FileExists(ConfigPath) then
  begin
    ServerValue := ReadJsonString(ConfigPath, 'server');
    KeyValue := ReadJsonString(ConfigPath, 'api_key');
    if ServerValue <> '' then
      ConfigPage.Values[0] := ServerValue;
    if KeyValue <> '' then
      ConfigPage.Values[1] := KeyValue;
  end;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
var
  Server: string;
begin
  Result := True;
  if CurPageID = ConfigPage.ID then
  begin
    Server := Trim(ConfigPage.Values[0]);
    if Server = '' then
    begin
      MsgBox(CustomMessage('ServerRequired'), mbError, MB_OK);
      Result := False;
    end
    else if (Copy(Server, 1, 7) <> 'http://') and
            (Copy(Server, 1, 8) <> 'https://') then
    begin
      MsgBox(CustomMessage('ServerInvalid'), mbError, MB_OK);
      Result := False;
    end
    else if Trim(ConfigPage.Values[1]) = '' then
    begin
      MsgBox(CustomMessage('KeyRequired'), mbError, MB_OK);
      Result := False;
    end;
  end;
end;

function JsonEscape(const Value: string): string;
begin
  Result := Value;
  StringChangeEx(Result, '\', '\\', True);
  StringChangeEx(Result, '"', '\"', True);
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ConfigPath, DataDir, Json: string;
begin
  if CurStep = ssPostInstall then
  begin
    ServerValue := Trim(ConfigPage.Values[0]);
    KeyValue := Trim(ConfigPage.Values[1]);
    DataDir := ExpandConstant('{userappdata}\GameStats');
    ForceDirectories(DataDir);
    ConfigPath := DataDir + '\agent.json';
    if WizardSilent and FileExists(ConfigPath) and
       (ParamValue('SERVER', '') = '') and (ParamValue('KEY', '') = '') then
      exit;
    Json := '{' + #13#10 +
      '  "server": "' + JsonEscape(ServerValue) + '",' + #13#10 +
      '  "api_key": "' + JsonEscape(KeyValue) + '",' + #13#10 +
      '  "interval": 30,' + #13#10 +
      '  "games_file": "games.json",' + #13#10 +
      '  "log_file": "agent.log"' + #13#10 +
      '}' + #13#10;
    if not SaveStringToFile(ConfigPath, Json, False) then
      MsgBox(CustomMessage('ConfigWriteError') + #13#10 + ConfigPath,
             mbError, MB_OK);
  end;
end;
