# ============================================================
#  Автономная установка: Python, venv, зависимости, .env, firewall
#  Затем можно запускать start_report_camera.bat (окно, как на обычном ПК)
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
    $candidates = @()
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

    Write-Host "Python не найден. Скачиваю Python 3.11 (тихая установка для всех пользователей)..." -ForegroundColor Yellow
    $pyUrl = "https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe"
    $pyInstaller = Join-Path $env:TEMP "python-installer-report-camera.exe"
    Invoke-WebRequest -Uri $pyUrl -OutFile $pyInstaller
    $proc = Start-Process -FilePath $pyInstaller -ArgumentList "/quiet", "InstallAllUsers=1", "PrependPath=1", "Include_pip=1" -Wait -PassThru
    if ($proc.ExitCode -ne 0) {
        throw "Установка Python завершилась с кодом $($proc.ExitCode)."
    }
    Remove-Item $pyInstaller -Force -ErrorAction SilentlyContinue
    Update-ProcessPathFromMachine
    Start-Sleep -Seconds 2

    $found = Find-PythonExe
    if (-not $found) {
        throw "Python установлен, но не найден в PATH. Перезапустите окно команд или ПК и снова запустите setup_server.bat."
    }
    return $found
}

Write-Step "Проверка Python"
$py = Ensure-Python
Write-Host "Используется: $($py.Exe)" -ForegroundColor Green

Write-Step "Виртуальное окружение venv"
$venvPy = Join-Path $ScriptDir "venv\Scripts\python.exe"
if (-not (Test-Path $venvPy)) {
    $venvArgs = @()
    $venvArgs += $py.ArgsPrefix
    $venvArgs += "-m", "venv", "$ScriptDir\venv"
    & $py.Exe @venvArgs
}
Write-Host "venv готово." -ForegroundColor Green

Write-Step "Установка зависимостей (pip)"
& $venvPy "-m", "pip", "install", "--upgrade", "pip" | Out-Host
& $venvPy "-m", "pip", "install", "-r", "$ScriptDir\requirements.txt" | Out-Host
Write-Host "Зависимости установлены." -ForegroundColor Green

Write-Step "Файл настроек .env"
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
        Set-Content -Path $envPath -Value $content.TrimEnd() -Encoding UTF8
    } else {
        @(
            "SECRET_KEY=$secret",
            "PORT=6565",
            "ALLOWED_HOSTS=*",
            "ADMIN_USERNAME=Amir",
            "MAIL_IMAP_HOST=imap.mail.ru"
        ) | Set-Content -Path $envPath -Encoding UTF8
    }
    Write-Host "Создан .env с новым SECRET_KEY." -ForegroundColor Green
} else {
    Write-Host ".env уже есть — не перезаписываю." -ForegroundColor Green
}

Write-Step "Брандмауэр Windows (порт 6565)"
try {
    $ruleName = "Report Camera Server (Port 6565)"
    $ruleExists = Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue
    if ($ruleExists) {
        Remove-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue
    }
    New-NetFirewallRule -DisplayName $ruleName -Direction Inbound -LocalPort 6565 -Protocol TCP -Action Allow -Profile Any | Out-Null
    Write-Host "Правило для TCP 6565 добавлено." -ForegroundColor Green
} catch {
    Write-Warning "Не удалось настроить брандмауэр: $($_.Exception.Message). При необходимости откройте порт 6565 вручную."
}

Write-Step "Создание ярлыка запуска на рабочем столе"
$startBat = Join-Path $ScriptDir "start_report_camera.bat"
try {
    $WshShell = New-Object -ComObject WScript.Shell
    $desktop = [Environment]::GetFolderPath("Desktop")
    if ([string]::IsNullOrWhiteSpace($desktop)) {
        Write-Warning "Папка рабочего стола недоступна — ярлык не создан. Запускайте start_report_camera.bat из папки программы."
    } else {
        $shortcutPath = Join-Path $desktop "Report Camera.lnk"
        $sc = $WshShell.CreateShortcut($shortcutPath)
        $sc.TargetPath = $startBat
        $sc.WorkingDirectory = $ScriptDir
        $sc.WindowStyle = 1
        $sc.Description = "Report Camera NVR — веб-панель и бот"
        $sc.Save()
        Write-Host "Ярлык: $shortcutPath" -ForegroundColor Green
    }
} catch {
    Write-Warning "Не удалось создать ярлык: $($_.Exception.Message). Используйте start_report_camera.bat вручную."
}

Write-Host "`n=========================================================" -ForegroundColor Cyan
Write-Host " УСТАНОВКА ЗАВЕРШЕНА" -ForegroundColor Green
Write-Host " Откройте в браузере: http://localhost:6565" -ForegroundColor Yellow
Write-Host " Логин по умолчанию смотрите в credentials.txt после первого запуска." -ForegroundColor Gray
Write-Host " Сейчас откроется отдельное окно с сервером — его не закрывайте." -ForegroundColor Yellow
Write-Host "=========================================================`n" -ForegroundColor Cyan

Start-Sleep -Seconds 1
Start-Process -FilePath "cmd.exe" -ArgumentList @("/k", "`"$startBat`"")
