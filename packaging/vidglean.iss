; VidGlean 安装包脚本（Inno Setup 6+）
; 编译：ISCC.exe packaging\vidglean.iss
; 依赖：先执行 pyinstaller packaging\vidglean.spec，产物在 dist\VidGlean\

#define AppName "VidGlean"
#define AppVersion "0.1.0"
#define AppExe "VidGlean.exe"

[Setup]
; 相对路径按仓库根目录解析（脚本在 packaging/ 下）
SourceDir=..
AppId={{8A7F31B4-6F2E-4C1B-9D2A-3E5C7B9A1D42}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=VidGlean
DefaultDirName={autopf}\VidGlean
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputDir=..\dist
OutputBaseFilename=VidGlean-{#AppVersion}-setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#AppExe}

[Languages]
; 简体中文语言包随仓库提供（Inno Setup 自带语言里没有中文）
; 路径相对 SourceDir（仓库根目录）
Name: "chinesesimplified"; MessagesFile: "packaging\ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加任务:"
Name: "startmenu"; Description: "创建开始菜单项"; GroupDescription: "附加任务:"

[Files]
Source: "dist\VidGlean\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: startmenu
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "启动 {#AppName}"; Flags: nowait postinstall skipifsilent

[Code]
var
  RemoveData: Boolean;
  DataDir: String;

function GetDataDir(Param: String): String;
begin
  Result := ExpandConstant('{localappdata}\VidGlean');
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    DataDir := GetDataDir('');
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
  begin
    // 卸载时询问是否删除用户数据；默认保留
    if DirExists(DataDir) then
    begin
      if MsgBox('是否同时删除 VidGlean 的本地数据（文档、字幕、分类、任务记录）？' + #13#10 +
                '选择“否”将保留数据，便于以后重新安装继续使用。' + #13#10 +
                '注意：删除后不可恢复。', mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
      begin
        DelTree(DataDir, True, True, True);
      end;
    end;
  end;
end;
