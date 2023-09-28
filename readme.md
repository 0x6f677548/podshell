[![Lint](https://github.com/0x6f677548/podshell/actions/workflows/lint-quick.yml/badge.svg)](https://github.com/0x6f677548/podshell/actions/workflows/lint-quick.yml)
# PodShell
<img align="left" src="https://github.com/0x6f677548/podshell/assets/64972114/6391cf0c-1655-4122-949d-ccbcd9550746" height="50" width="50"/>
PodShell sychronizes your favorite terminal with your running docker containers or ssh configurations. 
Just spin up your containers, and PodShell will automatically add them to your terminal. 

## Supported terminals
### iTerm2 Dynamic Profiles
![demo-iTerm2](https://github.com/0x6f677548/podshell/assets/64972114/7c0f482c-4879-41e6-b3a7-b71ee68b3c7f)

### Windows Terminal Profiles
![demo-windowsTerminal](https://github.com/0x6f677548/podshell/assets/64972114/f707e629-d0c1-48c2-93b4-1bdeeacb662c)

## Supported pod sources
### Docker (local)
PodShell monitors your docker events and creates profiles for any running container.

### SSH (config)
PodShell monitors your ssh config file and creates profiles based on Host config

## Installation and usage
### Windows
1. Download [latest release](https://github.com/0x6f677548/podshell/releases/latest/download/podshell-windows.zip)
2. Extract the zip file
3. Run `podshell.exe` to start the application

If you prefer, a console version is also available. You can run it with `podshell-console.exe`.

If you get prompted by Windows Defender, click on "More info" and then "Run anyway" (this is because the application is not signed)

### MacOS
1. Download [latest release](https://github.com/0x6f677548/podshell/releases/latest/download/podshell-macos.zip)
2. Extract the zip file
3. Run `podshell` to start the application

If you prefer, a console version is also available. You can run it with `podshell-console`.

This application is not signed, so you will have to allow it in your security settings. To do so, go to "System Preferences" > "Security & Privacy" > "General" and click on "Open Anyway". You will have to do this only once. Alternatively, you can right click on the application and click on "Open".

### Run from source
You can also run the application from source. To do so, you will need to have [Python >=3.7 installed](https://www.python.org/downloads/). Then, you can run the following commands:
```bash
git clone https://www.github.com/0x6f677548/podshell
cd podshell
python -m pip install -r requirements.txt
```
To run the gui version, run:
```bash
python main.py
```

To run the console version, run:
```bash
python console.py
```
### Build binaries for your platform
You can build binaries for your platform by running the following commands:
```bash
git clone https://www.github.com/0x6f677548/podshell
cd podshell
python -m pip install -r requirements.txt
pip install pyinstaller
pip install pillow
pyinstaller podshell.spec
pyinstaller podshell-console.spec
```

### Gui Version
When running on Gui, a tray icon is shown where you can activate or deactivate sources and terminals. When starting, the app detects sources and terminals installed. You can toggle on/off the sources and terminal integration. A single terminal is supported per platform (win32/MacOS) but more terminals will be integrated in the future.

![system-tray-icon](https://github.com/0x6f677548/podshell/assets/64972114/f20bb879-9d08-4baf-bafa-afb05b0486dc)
