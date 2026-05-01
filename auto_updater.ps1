# ============================================================
#   Report Camera — Auto Updater
#   Скрипт для CI/CD на Windows Server
# ============================================================

$repoDir = "C:\Amir\mailru_integrator\MailToTelegram"
$logFile = "$repoDir\update.log"

function Log-Update ($Message) {
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -Path $logFile -Value "[$timestamp] $Message"
}

cd $repoDir

# 1. Загружаем свежую информацию из удаленного репозитория
git fetch origin main | Out-Null

# 2. Проверяем, отстаёт ли локальная ветка от удалённой
$local = git rev-parse HEAD
$remote = git rev-parse origin/main

if ($local -ne $remote) {
    Log-Update "Обнаружено обновление! (Local: $local, Remote: $remote)"
    
    # 3. Останавливаем службу
    Log-Update "Останавливаем службу ReportCamera..."
    nssm stop ReportCamera | Out-Null
    Start-Sleep -Seconds 2

    # 4. Обновляем код
    Log-Update "Загружаем новый код (git reset --hard origin/main)..."
    git reset --hard origin/main | Out-Null
    
    # 5. Обновляем зависимости
    Log-Update "Устанавливаем зависимости из requirements.txt..."
    & .\venv\Scripts\pip.exe install -r requirements.txt | Out-Null
    
    # 6. Запускаем службу
    Log-Update "Запускаем службу ReportCamera..."
    nssm start ReportCamera | Out-Null
    
    Log-Update "Обновление успешно завершено!`n"
} else {
    # Код актуален, ничего не делаем (чтобы не спамить логи, можно закомментировать)
    # Log-Update "Система актуальна."
}
