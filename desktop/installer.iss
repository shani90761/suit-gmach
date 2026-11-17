; Inno Setup — קובץ התקנה לווינדוס. נבנה אוטומטית ב-GitHub Actions.
#define AppVer GetEnv("APP_VERSION")
#if AppVer == ""
  #define AppVer "1.0.0"
#endif

[Setup]
AppId={{6B7C1E2A-4F8D-4C1B-9E3A-5D2F7A9C1B44}
AppName=גמ״ח חליפות לשמחות
AppVersion={#AppVer}
AppPublisher=גמ״ח חליפות לשמחות
DefaultDirName={localappdata}\Programs\GemachSuits
DefaultGroupName=גמ״ח חליפות לשמחות
PrivilegesRequired=lowest
OutputDir=..\build\installer
OutputBaseFilename=GemachSuits-Setup
SetupIconFile=icon.ico
UninstallDisplayIcon={app}\GemachSuits.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
DisableProgramGroupPage=yes

[Languages]
Name: "he"; MessagesFile: "compiler:Languages\Hebrew.isl"

[Tasks]
Name: "desktopicon"; Description: "יצירת אייקון על שולחן העבודה"; Flags: checkedonce

[Files]
Source: "..\build\dist\GemachSuits\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\גמ״ח חליפות לשמחות"; Filename: "{app}\GemachSuits.exe"; IconFilename: "{app}\GemachSuits.exe"
Name: "{userdesktop}\גמ״ח חליפות"; Filename: "{app}\GemachSuits.exe"; IconFilename: "{app}\GemachSuits.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\GemachSuits.exe"; Description: "פתיחת המערכת עכשיו"; Flags: nowait postinstall skipifsilent

; הנתונים נשמרים בנפרד (%LOCALAPPDATA%\GemachSuits) ולא נמחקים בהסרה או בעדכון.
