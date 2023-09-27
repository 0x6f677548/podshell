# PodShell
<img align="left" src="https://github.com/0x6f677548/podshell/assets/64972114/6391cf0c-1655-4122-949d-ccbcd9550746" height="100" width="100"/>
PodShell sychronizes your favorite terminal with your running docker containers, or ssh configurations. 

Just spin up your containers, and PodShell will automatically add them to your terminal.

[![Lint](https://github.com/0x6f677548/podshell/actions/workflows/lint-quick.yml/badge.svg)](https://github.com/0x6f677548/podshell/actions/workflows/lint-quick.yml)
## Supported terminals
- [x] Windows Terminal
- [x] iTerm2

## Supported pod sources
- [x] Docker
- [x] SSH

## Installation and usage
### Windows
1. Download the latest release
2. Extract the zip file
3. Run `podshell.exe` to start the application

If you prefer, a console version is also available. You can run it with `podshell-console.exe`.

If you get prompted by Windows Defender, click on "More info" and then "Run anyway" (this is because the application is not signed)

### MacOS
1. Download the latest release
2. Extract the zip file
3. Run `podshell` to start the application

If you prefer, a console version is also available. You can run it with `podshell-console`.

This application is not signed, so you will have to allow it in your security settings. To do so, go to "System Preferences" > "Security & Privacy" > "General" and click on "Open Anyway". You will have to do this only once. Alternatively, you can right click on the application and click on "Open".

### Run from source
You can also run the application from source. To do so, you will need to have [Python >=3.7 installed](https://www.python.org/downloads/). Then, you can run the following commands:
```bash
git clone https://www.github.com/0x6f677548/podshell
cd podshell
cd src
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


