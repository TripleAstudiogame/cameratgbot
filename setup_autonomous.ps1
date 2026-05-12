# ============================================================
#  Standalone setup: Python, venv, deps, .env, firewall,
#  startup task after reboot + first run window
# ============================================================

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

function Write-Step($msg) {
    Write-Host "`n[>>>] $msg" -ForegroundColor Cyan
}

function Update-ProcessPathFromMachine {
    foreach ($level in "Machine", "User") {
        [Environment]::GetEnvironmentVariables($level).GetEnumerator() | ForEach-Object {
            [Environment]::SetEnvironmentVariable($_.Name, $_.Value, "Process")
        }
    }
}

function Find-PythonExe {
    foreach ($name in @("python", "py")) {
        try {
            $cmd = Get-Command $name -ErrorAction Stop
            if ($name -eq "py") {
                return @{ Exe = $cmd.Source; ArgsPrefix = @("-3") }
            }
            return @{ Exe = $cmd.Source; ArgsPrefix = @() }
        } catch {}
    }
    $paths = @(
        "C:\Program Files\Python312\python.exe",
        "C:\Program Files\Python311\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe"
    )
    foreach ($p in $paths) {
        if (Test-Path $p) {
            return @{ Exe = $p; ArgsPrefix = @() }
        }
    }
    return $null
}

function Ensure-Python {
    $found = Find-PythonExe
    if ($found) { return $found }

    Write-Host "Python not found. Downloading Python 3.11 (silent, all users)..." -ForegroundColor Yellow
    $pyUrl = "https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe"
    $pyInstaller = Join-Path $env:TEMP "python-installer-report-camera.exe"
    Invoke-WebRequest -Uri $pyUrl -OutFile $pyInstaller
    $proc = Start-Process -FilePath $pyInstaller -ArgumentList "/quiet", "InstallAllUsers=1", "PrependPath=1", "Include_pip=1" -Wait -PassThru
    if ($proc.ExitCode -ne 0) {
        throw "Python installer exit code: $($proc.ExitCode)"
    }
    Remove-Item $pyInstaller -Force -ErrorAction SilentlyContinue
    Update-ProcessPathFromMachine
    Start-Sleep -Seconds 2

    $found = Find-PythonExe
    if (-not $found) {
        throw "Python installed but not in PATH. Reboot or open a new cmd, then run setup_server.bat again."
    }
    return $found
}

Write-Step "Python check"
$py = Ensure-Python
Write-Host "Using: $($py.Exe)" -ForegroundColor Green

Write-Step "venv"
$venvPy = Join-Path $ScriptDir "venv\Scripts\python.exe"
if (-not (Test-Path $venvPy)) {
    $venvArgs = @()
    $venvArgs += $py.ArgsPrefix
    $venvArgs += "-m", "venv", "$ScriptDir\venv"
    & $py.Exe @venvArgs
}
Write-Host "venv OK." -ForegroundColor Green

Write-Step "pip install -r requirements.txt"
& $venvPy "-m", "pip", "install", "--upgrade", "pip" | Out-Host
& $venvPy "-m", "pip", "install", "-r", "$ScriptDir\requirements.txt" | Out-Host
Write-Host "pip OK." -ForegroundColor Green

Write-Step ".env file"
$envPath = Join-Path $ScriptDir ".env"
if (-not (Test-Path $envPath)) {
    $secret = ([Guid]::NewGuid().ToString("N") + [Guid]::NewGuid().ToString("N"))
    $example = Join-Path $ScriptDir ".env.example"
    if (Test-Path $example) {
        $content = Get-Content $example -Raw -Encoding UTF8
        $content = $content -replace "(?m)^SECRET_KEY=\s*$", "SECRET_KEY=$secret"
        if ($content -notmatch "SECRET_KEY=$secret") {
            $content = "SECRET_KEY=$secret`r`n" + $content
        }
        $Utf8NoBom = New-Object System.Text.UTF8Encoding $false
        [System.IO.File]::WriteAllText($envPath, $content.TrimEnd(), $Utf8NoBom)
    } else {
        $body = @"
SECRET_KEY=$secret
PORT=6565
ALLOWED_HOSTS=*
ADMIN_USERNAME=Amir
MAIL_IMAP_HOST=imap.mail.ru
"@
        $Utf8NoBom = New-Object System.Text.UTF8Encoding $false
        [System.IO.File]::WriteAllText($envPath, $body.Trim(), $Utf8NoBom)
    }
    Write-Host "Created .env with new SECRET_KEY." -ForegroundColor Green
} else {
    Write-Host ".env exists, not overwriting." -ForegroundColor Green
}

Write-Step "Firewall TCP 6565"
try {
    $ruleName = "Report Camera Server (Port 6565)"
    $ruleExists = Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue
    if ($ruleExists) {
        Remove-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue
    }
    New-NetFirewallRule -DisplayName $ruleName -Direction Inbound -LocalPort 6565 -Protocol TCP -Action Allow -Profile Any | Out-Null
    Write-Host "Firewall rule added." -ForegroundColor Green
} catch {
    Write-Warning "Firewall: $($_.Exception.Message). Open port 6565 manually if needed."
}

Write-Step "Autostart after reboot (Task Scheduler)"
$taskName = "ReportCamera_AutoStart"
$nssmService = Get-Service -Name "ReportCamera" -ErrorAction SilentlyContinue
if ($nssmService) {
    Write-Warning "Windows service 'ReportCamera' (NSSM) is installed. Skipping scheduled task to avoid two instances on port 6565."
    Write-Warning "Stop the service if you want setup_server.bat autostart only, or use setup_as_service.bat only."
} else {
    try {
        Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
    } catch {}
    try {
        $pyExe = Join-Path $ScriptDir "venv\Scripts\python.exe"
        $appPy = Join-Path $ScriptDir "app.py"
        $action = New-ScheduledTaskAction -Execute $pyExe -Argument "`"$appPy`"" -WorkingDirectory $ScriptDir
        $trigger = New-ScheduledTaskTrigger -AtStartup
        if ($trigger.PSObject.Properties.Name -contains "Delay") {
            $trigger.Delay = "PT45S"
        }
        $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -ExecutionTimeLimit ([TimeSpan]::Zero)
        $principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
        Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal `
            -Description "Report Camera: web and bot after reboot (setup_server.bat)" -Force | Out-Null
        Write-Host "Scheduled task: $taskName (at startup, ~45s delay)." -ForegroundColor Green
    } catch {
        Write-Warning "Could not register autostart task: $($_.Exception.Message). Run start_report_camera.bat manually after reboot."
    }
}

Write-Step "Desktop shortcut"
$startBat = Join-Path $ScriptDir "start_report_camera.bat"
try {
    $WshShell = New-Object -ComObject WScript.Shell
    $desktop = [Environment]::GetFolderPath("Desktop")
    if ([string]::IsNullOrWhiteSpace($desktop)) {
        Write-Warning "Desktop folder not available. Run start_report_camera.bat from the project folder."
    } else {
        $shortcutPath = Join-Path $desktop "Report Camera.lnk"
        $sc = $WshShell.CreateShortcut($shortcutPath)
        $sc.TargetPath = $startBat
        $sc.WorkingDirectory = $ScriptDir
        $sc.WindowStyle = 1
        $sc.Description = "Report Camera"
        $sc.Save()
        Write-Host "Shortcut: $shortcutPath" -ForegroundColor Green
    }
} catch {
    Write-Warning "Shortcut failed: $($_.Exception.Message)"
}

Write-Host "`n=========================================================" -ForegroundColor Cyan
Write-Host " DONE" -ForegroundColor Green
Write-Host " Browser: http://localhost:6565" -ForegroundColor Yellow
Write-Host " Default login: see credentials.txt after first run." -ForegroundColor Gray
Write-Host " A second window will open with the server (first time)." -ForegroundColor Yellow
Write-Host " After reboot: task ReportCamera_AutoStart starts the app (unless NSSM service is used)." -ForegroundColor Yellow
Write-Host " Do not run the shortcut twice or you get port 6565 conflict." -ForegroundColor Gray
Write-Host "=========================================================`n" -ForegroundColor Cyan

Start-Sleep -Seconds 1
Start-Process -FilePath "cmd.exe" -ArgumentList @("/k", "`"$startBat`"")
