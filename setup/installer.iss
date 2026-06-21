;============================================================
; TCP 聊天室 — Inno Setup 安装脚本
; 编译工具: Inno Setup 6.x (https://jrsoftware.org/isinfo.php)
; 用法: ISCC.exe installer.iss
;============================================================

#define MyAppName "TCP 聊天室"
#define MyAppShortName "TCP-Chat"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "TCP-Chat"
#define MyAppURL "https://github.com/GarmandoSHAO/TCP-Chat"
#define MyAppExeName "TCP-Chat.exe"

; 外部工具
#define BoreExe "bore.exe"
#define CrocExe "croc.exe"

[Setup]
; 安装包基础信息
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}

; 默认安装路径
DefaultDirName={autopf}\{#MyAppShortName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes

; 安装包文件
OutputDir=..\dist
OutputBaseFilename=TCP-Chat-Setup-{#MyAppVersion}

; 压缩配置
Compression=lzma2/max
SolidCompression=yes
InternalCompressLevel=max

; 卸载配置
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName} {#MyAppVersion}

; 权限配置
; 注: admin 权限用于写入防火墙规则和 Program Files 目录，
; HKCU 注册表存放用户级安装路径（供升级检测），
; 在管理员安装模式下 HKCU 指向当前用户配置单元，行为正确。
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=dialog

; 杂项
DisableProgramGroupPage=no
DisableDirPage=auto
AllowUNCPath=no
ArchitecturesInstallIn64BitMode=x64compatible
; MinVersion=6.1                ; Windows 7 SP1 (use default)
VersionInfoVersion={#MyAppVersion}
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription={#MyAppName} 安装程序
ShowLanguageDialog=yes
LanguageDetectionMethod=uilanguage

; 安装包签名（如有证书可取消注释）
; SignTool=signtool

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

;============================================================
; 自定义消息
;============================================================
[CustomMessages]
english.VCRedistMissing=Your system is missing Visual C++ Redistributable for Visual Studio 2015-2022.%n%nTCP Chat requires this to run.%n%nWould you like to download and install it now?
english.VCRedistDownload=Downloading VC++ Redistributable...
english.CheckNetwork=Checking network connection...
english.FirewallRule=Add Windows Firewall rule
english.SelectStartMenu=Create Start Menu shortcut(&S)
english.SelectDesktopIcon=Create Desktop shortcut(&D)
english.SelectAutoRun=Run after installation(&R)

;============================================================
; 文件清单（--onedir 打包，整个目录递归搬运）
;============================================================
[Files]
; 配置文件（首装时放入，升级时不覆盖）
Source: "..\dist\TCP-Chat\config.json"; DestDir: "{app}"; Flags: ignoreversion onlyifdoesntexist uninsneveruninstall
; 全部打包产物
Source: "..\dist\TCP-Chat\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion; Excludes: "config.json"

;============================================================
; 目录（程序运行时需要的可写目录）
;============================================================
[Dirs]
Name: "{app}\logs"; Permissions: users-modify
Name: "{app}\chat_cache"; Permissions: users-modify
Name: "{app}\download"

;============================================================
; 快捷方式
;============================================================
[Icons]
; 开始菜单 → 主程序
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Comment: "{#MyAppName}"
; 开始菜单 → 卸载
Name: "{group}\卸载 {#MyAppName}"; Filename: "{uninstallexe}"; WorkingDir: "{app}"
; 开始菜单 → 配置
Name: "{group}\配置文件"; Filename: "{app}\config.json"; WorkingDir: "{app}"
; 开始菜单 → 日志目录
Name: "{group}\日志目录"; Filename: "{app}\logs"; WorkingDir: "{app}"
; 桌面快捷方式
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

;============================================================
; 安装任务（用户可选）
;============================================================
[Tasks]
Name: "desktopicon"; Description: "{cm:SelectDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "startup_icon"; Description: "{cm:SelectStartMenu}"; GroupDescription: "{cm:AdditionalIcons}"

;============================================================
; 安装后运行
;============================================================
[Run]
; 安装完成后立即运行（可选）
Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: shellexec postinstall skipifsilent unchecked

;============================================================
; 卸载时清理
;============================================================
[UninstallRun]
; 清理日志和缓存
Filename: "{app}\setup_utils.py"; Parameters: "cleanup --dir ""{app}"""; Flags: runhidden; RunOnceId: "CleanupAppData"

[UninstallDelete]
Type: filesandordirs; Name: "{app}\logs"
Type: filesandordirs; Name: "{app}\download"
Type: filesandordirs; Name: "{app}\chat_cache"
Type: filesandordirs; Name: "{app}\__pycache__"

;============================================================
; 注册表
;============================================================
[Registry]
; 写入安装路径（便于后续升级检测）
Root: HKCU; Subkey: "SOFTWARE\{#MyAppShortName}"; Flags: uninsdeletekey
Root: HKCU; Subkey: "SOFTWARE\{#MyAppShortName}"; ValueType: string; ValueName: "InstallPath"; ValueData: "{app}"; Flags: uninsdeletevalue
Root: HKCU; Subkey: "SOFTWARE\{#MyAppShortName}"; ValueType: string; ValueName: "Version"; ValueData: "{#MyAppVersion}"; Flags: uninsdeletevalue

;============================================================
; Pascal 脚本 — 安装逻辑
;============================================================
[Code]

// ── 常量 ──────────────────────────────────────────────
const
  VC_REDIST_X64_URL = 'https://aka.ms/vs/17/release/vc_redist.x64.exe';
  VC_REDIST_X86_URL = 'https://aka.ms/vs/17/release/vc_redist.x86.exe';
  VC_REG_KEY = 'SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\';

// ── 全局变量 ─────────────────────────────────────────

var
  DownloadPage: TDownloadWizardPage;

// ── 下载页面辅助 ─────────────────────────────────────

function DownloadPageSetup(Url, Filename: string): Boolean;
begin
  DownloadPage := CreateDownloadPage(
    CustomMessage('VCRedistDownload'),
    CustomMessage('CheckNetwork'),
    nil
  );
  Result := Assigned(DownloadPage);
end;

function DownloadPageClear: Boolean;
begin
  if Assigned(DownloadPage) then
    DownloadPage.Clear;
  Result := True;
end;

function DownloadPageAdd(Url, Filename, Description: string): Boolean;
begin
  if Assigned(DownloadPage) then
    DownloadPage.Add(Url, Filename, Description);
  Result := True;
end;

function DownloadPageShow: Boolean;
begin
  Result := True;
  if Assigned(DownloadPage) then
  begin
    DownloadPage.Show;
    try
      DownloadPage.Download;
    except
      Result := False;
    end;
    DownloadPage.Hide;
  end;
end;

// ── 初始化 ────────────────────────────────────────────

function InitializeSetup: Boolean;
begin
  Result := True;
end;

// ── VC++ Redistributable 检测 ─────────────────────────

function IsVCRedistInstalled: Boolean;
var
  Key: string;
  Value: Cardinal;
  Bitness: string;
begin
  Result := False;

  if Is64BitInstallMode then
    Bitness := 'x64'
  else
    Bitness := 'x86';

  Key := VC_REG_KEY + Bitness;

  if RegQueryDWordValue(HKLM, Key, 'Installed', Value) then
  begin
    Result := (Value = 1);
  end;

  // 也检查 Wow6432Node（32位程序在64位系统上）
  if not Result and Is64BitInstallMode then
  begin
    if RegQueryDWordValue(HKLM, 'SOFTWARE\Wow6432Node\Microsoft\VisualStudio\14.0\VC\Runtimes\x64', 'Installed', Value) then
    begin
      Result := (Value = 1);
    end;
  end;
end;

function DownloadAndInstallVCRedist: Boolean;
var
  Url: string;
  DownloadPath: string;
  ResultCode: Integer;
begin
  Result := False;

  if Is64BitInstallMode then
    Url := VC_REDIST_X64_URL
  else
    Url := VC_REDIST_X86_URL;

  DownloadPath := ExpandConstant('{tmp}\vc_redist.exe');

  // 下载 VC++ Redistributable
  if not WizardSilent then
    SuppressibleMsgBox(FmtMessage(CustomMessage('VCRedistMissing'), ['']), mbInformation, MB_OK, IDOK);

  if not WizardSilent then
    WizardForm.StatusLabel.Caption := CustomMessage('VCRedistDownload');

  try
    if not DownloadPageSetup(Url, DownloadPath) then
    begin
      MsgBox('无法下载 VC++ 运行库。请手动访问 https://aka.ms/vs/17/release/vc_redist.x64.exe 下载并安装。', mbError, MB_OK);
      Exit;
    end;

    DownloadPageClear;
    DownloadPageAdd(Url, DownloadPath, '');

    if not DownloadPageShow then
    begin
      Exit;
    end;
  except
    MsgBox('下载失败，请检查网络连接后重试。', mbError, MB_OK);
    Exit;
  end;

  // 静默安装
  if Exec(DownloadPath, '/install /quiet /norestart', '', SW_SHOW, ewWaitUntilTerminated, ResultCode) then
  begin
    if ResultCode = 0 then
    begin
      Result := True;
    end
    else if ResultCode = 3010 then
    begin
      // 需要重启
      Result := True;
      SuppressibleMsgBox('VC++ 运行库安装完成，可能需要重启电脑才能生效。', mbInformation, MB_OK, IDOK);
    end
    else
    begin
      MsgBox('VC++ 运行库安装失败（错误码: ' + IntToStr(ResultCode) + '）。请手动安装。', mbError, MB_OK);
    end;
  end;
end;

// ── 配置生成 ───────────────────────────────────────────

procedure GenerateDefaultConfig(Dir: string);
var
  ConfigPath: string;
  ConfigContent: string;
begin
  ConfigPath := AddBackslash(Dir) + 'config.json';

  // 仅在文件不存在时生成
  if FileExists(ConfigPath) then
    Exit;

  ConfigContent :=
    '{' + #13#10 +
    '  "_comment": "TCP 聊天室配置文件",' + #13#10 +
    '  "discovery_port": 9999,' + #13#10 +
    '  "default_port": 8888,' + #13#10 +
    '  "default_nickname": "用户",' + #13#10 +
    '  "default_room_name": "聊天室",' + #13#10 +
    '  "appearance": "light",' + #13#10 +
    '  "theme": "green",' + #13#10 +
    '  "corner_radius": 16,' + #13#10 +
    '  "window": {' + #13#10 +
    '    "login_width": 420,' + #13#10 +
    '    "login_height": 480,' + #13#10 +
    '    "chat_width": 880,' + #13#10 +
    '    "chat_height": 640' + #13#10 +
    '  }' + #13#10 +
    '}';

  SaveStringToFile(ConfigPath, ConfigContent, False);
end;

// ── 防火墙规则 ─────────────────────────────────────────

procedure AddFirewallRule(AppPath: string);
var
  ResultCode: Integer;
  RuleName: string;
begin
  RuleName := 'TCP 聊天室';

  // 添加入站规则（允许其他客户端连接）
  Exec('netsh',
    ExpandConstant('advfirewall firewall add rule name="' + RuleName + '" dir=in program="' + AppPath + '" action=allow protocol=tcp localport=8888-9999 profile=private,domain'),
    '', SW_HIDE, ewWaitUntilTerminated, ResultCode);

  // 添加出站规则
  Exec('netsh',
    ExpandConstant('advfirewall firewall add rule name="' + RuleName + '(出站)" dir=out program="' + AppPath + '" action=allow protocol=tcp profile=private,domain'),
    '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
end;

// ── 获取上次安装路径（用于升级） ──────────────────────

function GetPreviousInstallPath: string;
begin
  Result := '';
  if not RegQueryStringValue(HKCU, 'SOFTWARE\TCP-Chat', 'InstallPath', Result) then
    Result := '';
end;

// ── 安装前处理 ─────────────────────────────────────────

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  // VC++ 运行库检查
  if not IsVCRedistInstalled then
  begin
    if not DownloadAndInstallVCRedist then
    begin
      // 用户取消或不成功，仍允许继续安装
      // 程序可能因为缺 VC++ 无法运行，但安装本身应完成
    end;
  end;

  Result := '';
end;

// ── 安装后处理 ─────────────────────────────────────────

procedure CurStepChanged(CurStep: TSetupStep);
var
  AppPath: string;
begin
  if CurStep = ssPostInstall then
  begin
    AppPath := AddBackslash(ExpandConstant('{app}')) + '{#MyAppExeName}';

    // 生成默认配置（仅首次安装）
    GenerateDefaultConfig(ExpandConstant('{app}'));

    // 添加防火墙规则
    AddFirewallRule(AppPath);
  end;
end;

// ── 卸载前处理 ─────────────────────────────────────────

function InitializeUninstall: Boolean;
var
  ResultCode: Integer;
  RuleName: string;
begin
  Result := True;

  // 清理防火墙规则
  RuleName := 'TCP 聊天室';
  Exec('netsh', ExpandConstant('advfirewall firewall delete rule name="' + RuleName + '"'), '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Exec('netsh', ExpandConstant('advfirewall firewall delete rule name="' + RuleName + '(出站)"'), '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
end;

