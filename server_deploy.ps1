# ============================================================
#   Report Camera — Универсальный Установщик (1-Click)
#   Устанавливает все зависимости, службы и настройки
# ============================================================

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

function Write-Step ($message) {
    Write-Host "`n[>>>] $message" -ForegroundColor Cyan
}

function Refresh-EnvVars {
    # Обновляет переменные среды в текущем процессе (чтобы свежеустановленный Python/Git был доступен сразу)
    foreach($level in "Machine","User") {
        [Environment]::GetEnvironmentVariables($level).GetEnumerator() | ForEach-Object {
            [Environment]::SetEnvironmentVariable($_.Name, $_.Value, "Process")
        }
    }
}

# 1. Установка Python 3.11 (Тихая)
Write-Step "Проверка Python..."
if (Get-Command "python" -ErrorAction SilentlyContinue) {
    Write-Host "Python уже установлен." -ForegroundColor Green
} else {
    Write-Host "Python не найден. Скачивание и тихая установка Python 3.11..." -ForegroundColor Yellow
    $pyUrl = "https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe"
    $pyInstaller = "$env:TEMP\python-installer.exe"
    Invoke-WebRequest -Uri $pyUrl -OutFile $pyInstaller
    Start-Process -FilePath $pyInstaller -ArgumentList "/quiet InstallAllUsers=1 PrependPath=1" -Wait -NoNewWindow
    Write-Host "Python успешно установлен!" -ForegroundColor Green
    Refresh-EnvVars
}

# 2. Установка Git (Тихая)
Write-Step "Проверка Git..."
if (Get-Command "git" -ErrorAction SilentlyContinue) {
    Write-Host "Git уже установлен." -ForegroundColor Green
} else {
    Write-Host "Git не найден. Скачивание и тихая установка Git..." -ForegroundColor Yellow
    $gitUrl = "https://github.com/git-for-windows/git/releases/download/v2.44.0.windows.1/Git-2.44.0-64-bit.exe"
    $gitInstaller = "$env:TEMP\git-installer.exe"
    Invoke-WebRequest -Uri $gitUrl -OutFile $gitInstaller
    Start-Process -FilePath $gitInstaller -ArgumentList "/VERYSILENT /NORESTART /COMPONENTS=`"icons,ext\reg\shellhere,assoc,assoc_sh`"" -Wait -NoNewWindow
    Write-Host "Git успешно установлен!" -ForegroundColor Green
    Refresh-EnvVars
}

# 3. Установка NSSM (Управление службами)
Write-Step "Проверка NSSM (Службы Windows)..."
$nssmPath = "C:\Windows\System32\nssm.exe"
if (Test-Path $nssmPath) {
    Write-Host "NSSM уже установлен." -ForegroundColor Green
} else {
    Write-Host "Скачивание NSSM..." -ForegroundColor Yellow
    $nssmZip = "$env:TEMP\nssm.zip"
    $nssmExtracted = "$env:TEMP\nssm_extracted"
    Invoke-WebRequest -Uri "https://nssm.cc/release/nssm-2.24.zip" -OutFile $nssmZip
    Expand-Archive -Path $nssmZip -DestinationPath $nssmExtracted -Force
    Copy-Item "$nssmExtracted\nssm-2.24\win64\nssm.exe" -Destination $nssmPath -Force
    Write-Host "NSSM успешно установлен!" -ForegroundColor Green
}

# 4. Настройка Брандмауэра (Firewall)
Write-Step "Открытие порта 6565 в брандмауэре Windows..."
$ruleName = "Report Camera Server (Port 6565)"
$ruleExists = Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue
if ($ruleExists) {
    Remove-NetFirewallRule -DisplayName $ruleName
}
New-NetFirewallRule -DisplayName $ruleName -Direction Inbound -LocalPort 6565 -Protocol TCP -Action Allow -Profile Any | Out-Null
Write-Host "Порт 6565 открыт для всех профилей." -ForegroundColor Green

# 5. Виртуальное окружение и библиотеки
Write-Step "Настройка Python окружения (venv)..."
if (-Not (Test-Path "$ScriptDir\venv")) {
    python -m venv "$ScriptDir\venv"
}
Write-Host "Установка библиотек (pip)..."
& "$ScriptDir\venv\Scripts\python.exe" -m pip install --upgrade pip | Out-Null
& "$ScriptDir\venv\Scripts\pip.exe" install -r "$ScriptDir\requirements.txt" | Out-Null
Write-Host "Библиотеки успешно установлены." -ForegroundColor Green

# 6. Установка Windows Службы (ReportCamera)
Write-Step "Регистрация службы ReportCamera..."
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
Write-Host "Служба ReportCamera успешно установлена и запущена!" -ForegroundColor Green

# 7. Планировщик задач (CI/CD Auto-updater)
Write-Step "Установка автообновлений (GitHub -> Server)..."
$taskName = "ReportCamera_AutoUpdater"
schtasks /Delete /TN $taskName /F >$null 2>&1
$updaterScript = "$ScriptDir\auto_updater.ps1"
schtasks /Create /TN $taskName /TR "powershell.exe -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$updaterScript`"" /SC MINUTE /MO 5 /RU "SYSTEM" /RL HIGHEST /F | Out-Null
Write-Host "Автообновление настроено (проверка каждые 5 минут)." -ForegroundColor Green

Write-Host "`n=========================================================" -ForegroundColor Cyan
Write-Host "УСТАНОВКА УСПЕШНО ЗАВЕРШЕНА!" -ForegroundColor Green
Write-Host "Сервер доступен по адресу: http://<IP-СЕРВЕРА>:6565" -ForegroundColor Yellow
Write-Host "=========================================================`n" -ForegroundColor Cyan
