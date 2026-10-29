[Setup]
AppId={{EBC39804-3103-4CDE-986E-256316B571E2}
AppName=IOC Evidence Packager
AppVersion=0.8.0
AppPublisher=saltyma
DefaultDirName={localappdata}\Programs\IOC Evidence Packager
DefaultGroupName=IOC Evidence Packager
PrivilegesRequired=lowest
OutputDir=..\dist\installer
OutputBaseFilename=ioc-evidence-packager-0.8.0-setup
Compression=lzma2
SolidCompression=yes
UninstallDisplayIcon={app}\IOCEvidencePackager.exe
LicenseFile=..\LICENSE

[Files]
Source: "..\dist\IOCEvidencePackager\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\IOC Evidence Packager"; Filename: "{app}\IOCEvidencePackager.exe"

[Run]
Filename: "{app}\IOCEvidencePackager.exe"; Description: "Open IOC Evidence Packager"; Flags: nowait postinstall skipifsilent
