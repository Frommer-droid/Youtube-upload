#ifndef AppVersion
  #error AppVersion must be provided by build_installer.py
#endif
#ifndef SourceDir
  #error SourceDir must be provided by build_installer.py
#endif

[Setup]
AppId={{F987791A-EF2B-4ABA-8275-DAF1F64FBF72}
AppName=Загрузчик видео на YouTube
AppVersion={#AppVersion}
AppPublisher=Frommer-droid
AppPublisherURL=https://github.com/Frommer-droid/Youtube-upload
DefaultDirName={code:GetDefaultInstallDir}
DefaultGroupName=Загрузчик видео на YouTube
UsePreviousAppDir=no
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=modern
LanguageDetectionMethod=none
ShowLanguageDialog=no
Compression=lzma2
SolidCompression=yes
OutputBaseFilename=YouTubePrivateUploader_v{#AppVersion}_Setup
SetupIconFile=..\logo.ico
UninstallDisplayIcon={app}\YouTubePrivateUploader.exe
MinVersion=10.0

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Excludes: "client_secret.json,token.json,*.log"; Flags: ignoreversion recursesubdirs createallsubdirs

[Dirs]
Name: "{app}\config"

[Icons]
Name: "{group}\Загрузчик видео на YouTube"; Filename: "{app}\YouTubePrivateUploader.exe"
Name: "{autodesktop}\Загрузчик видео на YouTube"; Filename: "{app}\YouTubePrivateUploader.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Создать ярлык на рабочем столе"; GroupDescription: "Дополнительные задачи:"

[Run]
Filename: "{app}\YouTubePrivateUploader.exe"; Description: "Запустить загрузчик видео на YouTube"; Flags: nowait postinstall skipifsilent runasoriginaluser

[UninstallDelete]
Type: files; Name: "{app}\.installation-id"

[Code]
function GetDefaultInstallDir(Param: String): String;
begin
  if DirExists('D:\') then
    Result := 'D:\Apps\YouTubePrivateUploader'
  else
    Result := 'C:\Apps\YouTubePrivateUploader';
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  Marker: String;
  InstallationId: String;
begin
  if CurStep <> ssPostInstall then
    Exit;
  Marker := ExpandConstant('{app}\.installation-id');
  if FileExists(Marker) then
    Exit;
  InstallationId := GetSHA256OfUnicodeString(
    ExpandConstant('{tmp}') + GetDateTimeString('yyyymmddhhnnsszzz', '-', '-')
  );
  if not SaveStringToFile(Marker, InstallationId, False) then
    RaiseException('Не удалось создать идентификатор установки.');
end;
