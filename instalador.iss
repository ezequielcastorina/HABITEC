; Script de Inno Setup (https://jrsoftware.org/isinfo.php) para crear un instalador clásico
; de Windows a partir de dist\SIP_Paneles.exe. Pasos: 1) correr crear_exe.bat,
; 2) abrir este archivo con Inno Setup y pulsar Compilar. Genera dist\SIP_Paneles_Setup.exe.
[Setup]
AppName=Hojas de taller SIP
AppVersion=1.0
DefaultDirName={autopf}\SIP Paneles
DefaultGroupName=SIP Paneles
OutputDir=dist
OutputBaseFilename=SIP_Paneles_Setup
Compression=lzma
SolidCompression=yes
DisableProgramGroupPage=yes

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "Crear un acceso directo en el escritorio"; Flags: unchecked

[Files]
Source: "dist\SIP_Paneles.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Hojas de taller SIP"; Filename: "{app}\SIP_Paneles.exe"
Name: "{autodesktop}\Hojas de taller SIP"; Filename: "{app}\SIP_Paneles.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\SIP_Paneles.exe"; Description: "Abrir el programa"; Flags: nowait postinstall skipifsilent
