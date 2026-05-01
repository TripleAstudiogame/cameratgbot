# ============================================================
#   Report Camera - Universal 1-Click Installer
#   Installs all dependencies, services and configurations
# ============================================================

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

function Write-Step ($message) {
    Write-Host "`n[>>>] $message" -ForegroundColor Cyan
}

function Refresh-EnvVars {
    foreach($level in "Machine","User") {
        [Environment]::GetEnvironmentVariables($level).GetEnumerator() | ForEach-Object {
            [Environment]::SetEnvironmentVariable($_.Name, $_.Value, "Process")
        }
    }
}

# 1. Install Python 3.11 (Silent)
Write-Step "Checking Python..."
if (Get-Command "python" -ErrorAction SilentlyContinue) {
    Write-Host "Python is already installed." -ForegroundColor Green
} else {
    Write-Host "Python not found. Downloading and installing Python 3.11..." -ForegroundColor Yellow
    $pyUrl = "https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe"
    $pyInstaller = "$env:TEMP\python-installer.exe"
    Invoke-WebRequest -Uri $pyUrl -OutFile $pyInstaller
    Start-Process -FilePath $pyInstaller -ArgumentList "/quiet InstallAllUsers=1 PrependPath=1" -Wait -NoNewWindow
    Write-Host "Python installed successfully!" -ForegroundColor Green
    Refresh-EnvVars
}

# 2. Install Git (Silent)
Write-Step "Checking Git..."
if (Get-Command "git" -ErrorAction SilentlyContinue) {
    Write-Host "Git is already installed." -ForegroundColor Green
} else {
    Write-Host "Git not found. Downloading and installing Git..." -ForegroundColor Yellow
    $gitUrl = "https://github.com/git-for-windows/git/releases/download/v2.44.0.windows.1/Git-2.44.0-64-bit.exe"
    $gitInstaller = "$env:TEMP\git-installer.exe"
    Invoke-WebRequest -Uri $gitUrl -OutFile $gitInstaller
    Start-Process -FilePath $gitInstaller -ArgumentList "/VERYSILENT /NORESTART /COMPONENTS=`"icons,ext\reg\shellhere,assoc,assoc_sh`"" -Wait -NoNewWindow
    Write-Host "Git installed successfully!" -ForegroundColor Green
    Refresh-EnvVars
}

# 3. Install NSSM
Write-Step "Checking NSSM..."
$nssmPath = "C:\Windows\System32\nssm.exe"
if (Test-Path $nssmPath) {
    Write-Host "NSSM is already installed." -ForegroundColor Green
} else {
    Write-Host "Downloading NSSM..." -ForegroundColor Yellow
    $nssmZip = "$env:TEMP\nssm.zip"
    $nssmExtracted = "$env:TEMP\nssm_extracted"
    Invoke-WebRequest -Uri "https://nssm.cc/release/nssm-2.24.zip" -OutFile $nssmZip
    Expand-Archive -Path $nssmZip -DestinationPath $nssmExtracted -Force
    Copy-Item "$nssmExtracted\nssm-2.24\win64\nssm.exe" -Destination $nssmPath -Force
    Write-Host "NSSM installed successfully!" -ForegroundColor Green
}

# 4. Configure Firewall
Write-Step "Opening port 6565 in Windows Firewall..."
$ruleName = "Report Camera Server (Port 6565)"
$ruleExists = Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue
if ($ruleExists) {
    Remove-NetFirewallRule -DisplayName $ruleName
}
New-NetFirewallRule -DisplayName $ruleName -Direction Inbound -LocalPort 6565 -Protocol TCP -Action Allow -Profile Any | Out-Null
Write-Host "Port 6565 is now open." -ForegroundColor Green

# 5. Virtual Environment and Pip
Write-Step "Setting up Python venv..."
if (-Not (Test-Path "$ScriptDir\venv")) {
    python -m venv "$ScriptDir\venv"
}
Write-Host "Installing pip requirements..."
& "$ScriptDir\venv\Scripts\python.exe" -m pip install --upgrade pip | Out-Null
& "$ScriptDir\venv\Scripts\pip.exe" install -r "$ScriptDir\requirements.txt" | Out-Null
Write-Host "Dependencies installed successfully!" -ForegroundColor Green

# 6. Install Windows Service
Write-Step "Registering ReportCamera service..."
$serviceName = "ReportCamera"
$serviceStatus = Get-Service -Name $serviceName -ErrorAction SilentlyContinue
if ($serviceStatus) {
    nssm stop $serviceName | Out-Null
    nssm remove $serviceName confirm | Out-Null
}
nssm install $serviceName "$ScriptDir\venv\Scripts\python.exe" "app.py" | Out-Null
nssm set $serviceName AppDirectory "$ScriptDir" | Out-Null
nssm set $serviceName AppStdout "$ScriptDir\service_stdout.log" | Out-Null
nssm set $serviceName AppStderr "$ScriptDir\service_stderr.log" | Out-Null
nssm set $serviceName Start SERVICE_AUTO_START | Out-Null
nssm set $serviceName AppRestartDelay 3000 | Out-Null
nssm start $serviceName | Out-Null
Write-Host "Service ReportCamera installed and started successfully!" -ForegroundColor Green

# 7. CI/CD Auto-updater Task
Write-Step "Setting up Auto-updater (GitHub -> Server)..."
$taskName = "ReportCamera_AutoUpdater"
schtasks /Delete /TN $taskName /F >$null 2>&1
$updaterScript = "$ScriptDir\auto_updater.ps1"
schtasks /Create /TN $taskName /TR "powershell.exe -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$updaterScript`"" /SC MINUTE /MO 5 /RU "SYSTEM" /RL HIGHEST /F | Out-Null
Write-Host "Auto-updater configured (checks every 5 minutes)." -ForegroundColor Green

Write-Host "`n=========================================================" -ForegroundColor Cyan
Write-Host "INSTALLATION COMPLETED SUCCESSFULLY!" -ForegroundColor Green
Write-Host "Dashboard is available at: http://<SERVER-IP>:6565" -ForegroundColor Yellow
Write-Host "=========================================================`n" -ForegroundColor Cyan
