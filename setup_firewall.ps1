# ============================================================
#   Report Camera — Настройка Windows Firewall
#   Запускать от имени Администратора!
# ============================================================

if (!([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Warning "Запустите этот скрипт от имени Администратора (Run as Administrator)."
    Pause
    exit
}

$port = 6565
$ruleName = "ReportCamera-TCP-$port"

# Удалить старое правило если есть
Remove-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue

# Создать входящее правило
New-NetFirewallRule `
    -DisplayName $ruleName `
    -Direction Inbound `
    -Protocol TCP `
    -LocalPort $port `
    -Action Allow `
    -Profile Domain,Private `
    -Description "Report Camera NVR SaaS — порт $port"

Write-Host ""
Write-Host "Правило файрвола создано: TCP порт $port открыт (Domain + Private сети)" -ForegroundColor Green
Write-Host ""
Write-Host "ВНИМАНИЕ: Порт открыт только для Domain и Private сетей." -ForegroundColor Yellow
Write-Host "Для Public сети добавьте вручную если нужно." -ForegroundColor Yellow
Write-Host ""
Pause
