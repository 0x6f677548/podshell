# TrayEnabled parameter is used to enable/disable the tray icon
param(
    [Parameter(Mandatory = $false)]
    [bool]$TrayEnabled = $false
)


function Add-WTProfileForContainer {
    param(
        [Parameter(Mandatory = $true)]
        [string]$containerName
    )

    $profileName = "Docker: $containerName"
    $newProfile = @{
        name = $profileName
        commandline = "docker exec -it $containerName /bin/sh"
        suppressApplicationTitle = $true
        guid = [guid]::NewGuid().ToString("B")
    }
    return $newProfile
}

function Backup-WTSettings {
    param(
        [Parameter(Mandatory = $true)]
        [string]$wtSettingsFilePath
    )
    # //TODO: we might need to delete old backup files if there are too many of them
    $backupFilePath = $wtSettingsFilePath `
        -replace "\.json$", ".backup.$(Get-Date -Format 'yyyyMMddHHmmss').json"
    Copy-Item -Path $wtSettingsFilePath -Destination $backupFilePath
    Write-DebugMessage "Settings backed up to $backupFilePath"
}

function Save-WTSettings {
    param(
        [Parameter(Mandatory = $true)]
        [string]$wtSettingsFilePath,
        [Parameter(Mandatory = $true)]
        [object]$settings
    )
    # Convert back to JSON and write to the file
    $settings | ConvertTo-Json -Depth 10 | Set-Content -Path $wtSettingsFilePath
    Write-DebugMessage "Settings updated"
}


function Get-WTSettings {
    param(
        [Parameter(Mandatory = $true)]
        [string]$wtSettingsFilePath
    )
    # Read the current JSON content
    $currentSettings = Get-Content -Raw -Path $wtSettingsFilePath | ConvertFrom-Json
    return $currentSettings
}

function Write-ToTray {
    param(
        [Parameter(Mandatory = $true)]
        [string]$message
    )
    if ($TrayEnabled) {
        # truncate the message to 128 characters. This is the maximum length of the tray icon text
        $message = $message.Substring(0, [Math]::Min(127, $message.Length))
        $trayIcon.Text = $message
    }  
}
enum Status {
    Healthy
    Working
    Warning
}

function Set-TrayIconStatus {
    param(
        [Parameter(Mandatory = $true)]
        [Status]$status
    )
    if ($TrayEnabled) {
        if ($status -eq [Status]::Healthy) {
            $trayIcon.Icon = $ICON_OK
        }
        elseif ($status -eq [Status]::Working) {
            $trayIcon.Icon = $ICON_WORKING
        }
        else {
            $trayIcon.Icon = $ICON_OFF
        }
    }
}

function Write-ErrorMessage {
    param(
        [Parameter(Mandatory = $true)]
        [string]$message
    )
    $message = "Fatal: $message"
    Write-ToTray $message
    #high beep
    [console]::beep(700, 50)
}   Write-Host $message -ForegroundColor Red
 

function Write-WarnMessage {
    param(
        [Parameter(Mandatory = $true)]
        [string]$message
    )
    $message = "Warn: $message"
    Write-ToTray $message
    Write-Host $message -ForegroundColor Yellow
}

function Write-InfoMessage {
    param(
        [Parameter(Mandatory = $true)]
        [string]$message
    )
    $message = "Info: $message"
    Write-ToTray $message
    Write-Host $message -ForegroundColor Green
}

function Write-DebugMessage {
    param(
        [Parameter(Mandatory = $true)]
        [string]$message
    )
    $message = "Debug: $message"
    Write-Host $message -ForegroundColor Gray
}


function Remove-ContainerProfiles {
    param(
        [Parameter(Mandatory = $true)]
        [string]$wtSettingsFilePath
    )
    Write-DebugMessage "Removing container profiles..."
    $currentSettings = Get-WTSettings -wtSettingsFilePath $wtSettingsFilePath

    # check for orphaned profiles and remove them. 
    # Orphaned profiles have a name starting with "Docker: " but no longer have a corresponding container
    $currentSettings.profiles.list = $currentSettings.profiles.list | Where-Object { $_.name -notlike "Docker: *" }

    # persist the changes to the settings.json file
    Save-WTSettings -wtSettingsFilePath $wtSettingsFilePath -settings $currentSettings

}
function Sync-ContainerProfilesStatus {
    param(
        [Parameter(Mandatory = $true)]
        [string]$wtSettingsFilePath
    )
    Write-DebugMessage "Syncing container profiles with running containers..."
    $currentSettings = Get-WTSettings -wtSettingsFilePath $wtSettingsFilePath

    # check for orphaned profiles and remove them. 
    # Orphaned profiles have a name starting with "Docker: " but no longer have a corresponding container
    $currentSettings.profiles.list = $currentSettings.profiles.list | Where-Object { $_.name -notlike "Docker: *" }

    # check for running containers and add a profile for each of them
    docker ps --format '{{.Names}}' | ForEach-Object {
        Write-DebugMessage "Container '$_' is running. Adding profile..."
        $newProfile = Add-WTProfileForContainer -containerName $_
        $currentSettings.profiles.list += $newProfile
    }

    # persist the changes to the settings.json file
    Save-WTSettings -wtSettingsFilePath $wtSettingsFilePath -settings $currentSettings

}

function Sync-ContainerProfilesBasedOnEvents {
    param(
        [Parameter(Mandatory = $true)]
        [string]$wtSettingsFilePath
    )
    Write-InfoMessage "Listening for docker events..."
    # Listening to docker events. We'll get notified when a container starts or stops
    docker events --format '{{json .}}' `
        --filter 'type=container' --filter 'event=start' --filter 'event=die' | ForEach-Object { 

        Set-TrayIconStatus -status Working
        $eventObject = $_ | ConvertFrom-Json
        $containerName = $eventObject.Actor.Attributes.Name

        # Read the current JSON content. We might have changes in the file from other sources
        $currentSettings = Get-WTSettings -wtSettingsFilePath $wtSettingsFilePath

        $profileName = "Docker: $containerName"


        if ($eventObject.Action -eq "start" -and $eventObject.Type -eq "container") {
            # Add a new profile for the started container
            $newProfile = Add-WTProfileForContainer -containerName $containerName
            $currentSettings.profiles.list += $newProfile
            Write-InfoMessage "Container '$containerName' started. Added profile."
        }
        elseif ($eventObject.Action -eq "die" -and $eventObject.Type -eq "container") {
            # Remove the profile for the stopped container
            $currentSettings.profiles.list = $currentSettings.profiles.list | Where-Object { $_.name -ne $profileName }
            Write-InfoMessage "Container '$containerName' died. Removed profile."
        }

        Save-WTSettings -wtSettingsFilePath $wtSettingsFilePath -settings $currentSettings
        Set-TrayIconStatus -status Healthy
    }
}

function Get-WTSettingsFilePath {
    # get the path to the settings.json file
    $terminalpackage = Get-AppxPackage "Microsoft.WindowsTerminal*"
    # test if the package is installed and exit if not
    If (-Not $terminalpackage) {
        Write-ErrorMessage "Windows Terminal is not installed"
        DisableTrayIcon
        exit
    }
    # get the path to the settings.json file
    $wtSettingsFilePath = Join-Path $env:LOCALAPPDATA "packages" $terminalpackage.PackageFamilyName "LocalState" "settings.json"

    # test if the settings.json file exists
    if (-Not  (Test-Path $wtSettingsFilePath)) {
        #write an error message to the terminal
        Write-ErrorMessage "Windows Terminal settings file not found"
        DisableTrayIcon
        exit
    }
    return $wtSettingsFilePath
}

function Test-DockerDaemon {
    Set-TrayIconStatus -status Working
    # test if the docker command is available and exit if not
    if (-Not (Get-Command docker.exe -ErrorAction SilentlyContinue)) {
        Write-ErrorMessage "Docker is not installed"
        DisableTrayIcon
        exit
    }

    # check if the docker daemon is running. We'll do this by checking the output of the docker server version command and see if it contains a valid version number
    $dockerVersion = docker version -f '{{.Server.Version}}'
    #if it doesn't contain a valid version number, the docker daemon is not running
    if ($dockerVersion -notmatch "\d+\.\d+\.\d+") {
        Set-TrayIconStatus -status Warning
        return $false
    }
    Set-TrayIconStatus -status Healthy
    Write-DebugMessage "Connected to docker daemon version $dockerVersion"
    return $true
}


function Connect-DockerDaemon{
    $loops = 0

    while (-Not (Test-DockerDaemon)) {
        Write-WarnMessage "Docker daemon not available. This may be due to a docker daemon restart or quit."
        if ($loops -lt $12) {
            $sleepDuration = 1
        }
        else {
            $sleepDuration = 5
        }

        Write-InfoMessage "Retrying to connect to docker daemon in $sleepDuration seconds..."
        Start-Sleep -Seconds $sleepDuration
        $loops++
    }
    Set-TrayIconStatus -status Healthy
}


function Start-SyncBasedOnEvents {
    param(
        [Parameter(Mandatory = $true)]
        [string]$wtSettingsFilePath
    )

    while ($true) {

        # try to connect to the docker daemon. This may take a while if the daemon is restarting
        Connect-DockerDaemon

        # sync the container status with the profiles. 
        # This will add profiles for running containers and remove profiles for stopped containers
        Sync-ContainerProfilesStatus -wtSettingsFilePath $wtSettingsFilePath
    
        Set-TrayIconStatus -status Healthy
        Sync-ContainerProfilesBasedOnEvents -wtSettingsFilePath $wtSettingsFilePath
        #beep to indicate that the docker events command has quit
        [console]::beep(500, 100)
        Set-TrayIconStatus -status Warning

        # if we get here, the docker events command has quit. This may be due to a docker daemon restart or quit.
        Write-WarnMessage "Docker events not available. This may be due to a docker daemon restart or quit."
        Remove-ContainerProfiles -wtSettingsFilePath $wtSettingsFilePath
    }

}

function NewTrayIcon(){
    $TrayIcon = New-Object System.Windows.Forms.NotifyIcon
    $TrayIcon.Visible = $true
    $TrayIcon.Icon = $ICON_OFF

    return $TrayIcon
}
function DisableTrayIcon(){
    if ($TrayEnabled) {
        $TrayIcon.Visible = $false
        $TrayIcon.Dispose()
    }
}





# starting the script


if ($TrayEnabled) {

    [System.Reflection.Assembly]::LoadWithPartialName('System.Windows.Forms') | Out-Null
    # Convert my png (bitmap) to an icon
    $ICON_OK  = [System.Drawing.Icon]::FromHandle(([System.Drawing.Bitmap]::FromFile($(Join-Path $PSScriptRoot '\icon_on.png'))).GetHicon()) 
    $ICON_OFF = [System.Drawing.Icon]::FromHandle(([System.Drawing.Bitmap]::FromFile($(Join-Path $PSScriptRoot '\icon_off.png'))).GetHicon())
    $ICON_WORKING = [System.Drawing.Icon]::FromHandle(([System.Drawing.Bitmap]::FromFile($(Join-Path $PSScriptRoot '\icon_working.png'))).GetHicon())
    


    # We'll use tray icon to keep the script running until the user clicks on the icon
    # and as a visual indicator that the script is running
    $trayIcon = NewTrayIcon
    $trayIcon.Add_Click(
        {
            DisableTrayIcon
            # removing container profiles on exit
            Remove-ContainerProfiles -wtSettingsFilePath $wtSettingsFilePath
            Stop-Process $pid
        }
    )
}


$wtSettingsFilePath = Get-WTSettingsFilePath
Backup-WTSettings -wtSettingsFilePath $wtSettingsFilePath
Start-SyncBasedOnEvents -wtSettingsFilePath $wtSettingsFilePath
