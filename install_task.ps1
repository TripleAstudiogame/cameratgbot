# Требуются права Администратора!
if (!([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Warning "Пожалуйста, запустите этот скрипт от имени Администратора (Run as Administrator)."
    Pause
    exit
}

$taskName = "MailToTelegramBot"
$taskDesc = "Фоновый процесс бота для пересылки писем с камер в Telegram"
$scriptPath = Join-Path -Path $PSScriptRoot -ChildPath "start_hidden.vbs"

# Создаем действие
$action = New-ScheduledTaskAction -Execute "wscript.exe" -Argument "`"$scriptPath`"" -WorkingDirectory $PSScriptRoot

# Создаем триггер (при запуске системы)
$trigger = New-ScheduledTaskTrigger -AtStartup

# Настраиваем условия (не останавливать, если перешли на батарею)
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit 0

# Создаем саму задачу от имени системы (чтобы запускалась даже если пользователь не залогинился)
Write-Host "Создание фоновой задачи $taskName..."
Register-ScheduledTask -Action $action -Trigger $trigger -Settings $settings -TaskName $taskName -Description $taskDesc -User "NT AUTHORITY\SYSTEM" -RunLevel Highest -Force

Write-Host "Готово! Задача создана. Бот теперь будет автоматически запускаться при перезагрузке сервера."
Write-Host "Прямо сейчас бот еще не запущен. Вы можете запустить его вручную или перезагрузить сервер."
Pause
