

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
    Write-InfoMessage "Settings backed up to $backupFilePath"
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
    Write-InfoMessage "Settings updated"
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

function Write-ErrorMessage {
    param(
        [Parameter(Mandatory = $true)]
        [string]$message
    )
    $message = "Fatal: $message"
    Write-Host $message -ForegroundColor Red
}

function Write-WarnMessage {
    param(
        [Parameter(Mandatory = $true)]
        [string]$message
    )
    $message = "Warn: $message"
    Write-Host $message -ForegroundColor Yellow
}

function Write-InfoMessage {
    param(
        [Parameter(Mandatory = $true)]
        [string]$message
    )
    $message = "Info: $message"
    Write-Host $message -ForegroundColor Green
}


function Remove-ContainerProfiles {
    param(
        [Parameter(Mandatory = $true)]
        [string]$wtSettingsFilePath
    )
    Write-InfoMessage "Removing container profiles..."
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
    Write-InfoMessage "Syncing container profiles with running containers..."
    $currentSettings = Get-WTSettings -wtSettingsFilePath $wtSettingsFilePath

    # check for orphaned profiles and remove them. 
    # Orphaned profiles have a name starting with "Docker: " but no longer have a corresponding container
    $currentSettings.profiles.list = $currentSettings.profiles.list | Where-Object { $_.name -notlike "Docker: *" }

    # check for running containers and add a profile for each of them
    docker ps --format '{{.Names}}' | ForEach-Object {
        Write-InfoMessage "Container '$_' is running. Adding profile..."
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

        $eventObject = $_ | ConvertFrom-Json
        $containerName = $eventObject.Actor.Attributes.Name

        # Read the current JSON content. We might have changes in the file from other sources
        $currentSettings = Get-WTSettings -wtSettingsFilePath $wtSettingsFilePath

        $profileName = "Docker: $containerName"


        if ($eventObject.Action -eq "start" -and $eventObject.Type -eq "container") {
            Write-InfoMessage "Container '$containerName' started. Adding profile..."
            # Add a new profile for the started container
            $newProfile = Add-WTProfileForContainer -containerName $containerName
            $currentSettings.profiles.list += $newProfile
        }
        elseif ($eventObject.Action -eq "die" -and $eventObject.Type -eq "container") {
            Write-InfoMessage "Container '$containerName' died. Removing profile..." 
            # Remove the profile for the stopped container
            $currentSettings.profiles.list = $currentSettings.profiles.list | Where-Object { $_.name -ne $profileName }
        }

        Save-WTSettings -wtSettingsFilePath $wtSettingsFilePath -settings $currentSettings
    }
}

function Get-WTSettingsFilePath {
    # get the path to the settings.json file
    $terminalpackage = Get-AppxPackage "Microsoft.WindowsTerminal*"
    # test if the package is installed and exit if not
    If (-Not $terminalpackage) {
        Write-ErrorMessage "Windows Terminal is not installed"
        exit
    }
    # get the path to the settings.json file
    $wtSettingsFilePath = Join-Path $env:LOCALAPPDATA "packages" $terminalpackage.PackageFamilyName "LocalState" "settings.json"

    # test if the settings.json file exists
    if (-Not  (Test-Path $wtSettingsFilePath)) {
        #write an error message to the terminal
        Write-ErrorMessage "Windows Terminal settings file not found"
        exit
    }
    return $wtSettingsFilePath
}

function Test-DockerDaemon {
    # test if the docker command is available and exit if not
    if (-Not (Get-Command docker.exe -ErrorAction SilentlyContinue)) {
        Write-ErrorMessage "Docker is not installed"
        exit
    }

    # check if the docker daemon is running. We'll do this by checking the output of the docker server version command and see if it contains a valid version number
    $dockerVersion = docker version -f '{{.Server.Version}}'
    #if it doesn't contain a valid version number, the docker daemon is not running
    if ($dockerVersion -notmatch "\d+\.\d+\.\d+") {
        return $false
    }
    Write-InfoMessage "Connected to docker daemon version $dockerVersion"
    return $true
}

function Invoke-DoWhileFunction {
    param (
        [scriptblock]$ActionFunction,
        [scriptblock]$ConditionFunction,
        [int]$InitialSleepDurationInSeconds,
        [int]$NumberOfInitialSleeps,
        [int]$LongSleepDurationInSeconds,
        [string]$LoopMessage 
    )

    $loops = 0

    while (& $ConditionFunction) {
        & $ActionFunction
        if ($loops -lt $NumberOfInitialSleeps) {
            $sleepDuration = $InitialSleepDurationInSeconds
        }
        else {
            $sleepDuration = $LongSleepDurationInSeconds
        }
        if ($LoopMessage) {
            Write-InfoMessage "$LoopMessage in $sleepDuration seconds..."
        }
        Start-Sleep -Seconds $sleepDuration
        $loops++
    }
}

function Connect-DockerDaemon() {
    $action = {
        Write-WarnMessage "Docker daemon not available. This may be due to a docker daemon restart or quit."
    }
    
    Invoke-DoWhileFunction -ActionFunction `
        $action `
        -ConditionFunction { -Not (Test-DockerDaemon) } `
        -InitialSleepDurationInSeconds 1 `
        -NumberOfInitialSleeps 12 `
        -LongSleepDurationInSeconds 5 `
        -LoopMessage "Retrying to connect to docker daemon"
}


function Start-SyncBasedOnEvents {
    param(
        [Parameter(Mandatory = $true)]
        [string]$wtSettingsFilePath
    )

    while ($true) {
        Sync-ContainerProfilesBasedOnEvents -wtSettingsFilePath $wtSettingsFilePath
        # if we get here, the docker events command has quit. This may be due to a docker daemon restart or quit.
        Write-WarnMessage "Docker events not available. This may be due to a docker daemon restart or quit."
        Remove-ContainerProfiles -wtSettingsFilePath $wtSettingsFilePath
        # retry to connect to the docker daemon. This may take a while if the daemon is restarting
        Connect-DockerDaemon
        # sync the container status with the profiles.
        Sync-ContainerProfilesStatus -wtSettingsFilePath $wtSettingsFilePath
    }

}


$wtSettingsFilePath = Get-WTSettingsFilePath

Backup-WTSettings -wtSettingsFilePath $wtSettingsFilePath
Connect-DockerDaemon

# sync the container status with the profiles. 
# This will add profiles for running containers and remove profiles for stopped containers
Sync-ContainerProfilesStatus -wtSettingsFilePath $wtSettingsFilePath

Start-SyncBasedOnEvents -wtSettingsFilePath $wtSettingsFilePath