<#
Richtet eine Windows-Aufgabe ein, die sync.py alle 20 Minuten automatisch
ausfuehrt (auch wenn man nicht angemeldet ist, solange der PC laeuft).

Aufruf (einmalig, normales PowerShell-Fenster reicht):
    powershell -ExecutionPolicy Bypass -File setup_scheduled_task.ps1

Zum Entfernen:
    Unregister-ScheduledTask -TaskName "BasisDashboardSync" -Confirm:$false
#>

$taskName = "BasisDashboardSync"
$syncDir = $PSScriptRoot

# (Get-Command python) kann in einer frischen PowerShell-Instanz faelschlich auf
# den Microsoft-Store-Platzhalter zeigen statt auf die echte Installation -
# deshalb hier gezielt nach der echten python.exe suchen.
$pythonExe = Get-ChildItem "$env:LOCALAPPDATA\Programs\Python\Python3*\python.exe" -ErrorAction SilentlyContinue |
    Select-Object -First 1 -ExpandProperty FullName
if (-not $pythonExe) {
    $candidate = (Get-Command python -ErrorAction SilentlyContinue).Source
    if ($candidate -and $candidate -notlike "*WindowsApps*") { $pythonExe = $candidate }
}
if (-not $pythonExe) {
    Write-Error "Konnte keine echte Python-Installation finden."
    exit 1
}
Write-Host "Nutze Python: $pythonExe"

$action = New-ScheduledTaskAction -Execute $pythonExe -Argument "sync.py" -WorkingDirectory $syncDir
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 20) -RepetitionDuration (New-TimeSpan -Days 3650)
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopOnIdleEnd -ExecutionTimeLimit (New-TimeSpan -Minutes 5)

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null

Write-Host "Geplante Aufgabe '$taskName' eingerichtet - laeuft ab jetzt alle 20 Minuten."
Write-Host "Einmal sofort testen mit: Start-ScheduledTask -TaskName '$taskName'"
