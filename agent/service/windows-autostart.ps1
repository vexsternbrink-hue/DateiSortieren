# Windows: Agent bei der Anmeldung automatisch starten (PowerShell als normaler Nutzer ausführen)
$exe = (Get-Command dateisortieren).Source
$action = New-ScheduledTaskAction -Execute $exe -Argument "run"
$trigger = New-ScheduledTaskTrigger -AtLogOn
$settings = New-ScheduledTaskSettingsSet -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit 0
Register-ScheduledTask -TaskName "DateiSortieren Agent" -Action $action -Trigger $trigger -Settings $settings -Description "KI-Dateiorganisation"
Write-Host "Fertig. Start sofort mit: Start-ScheduledTask -TaskName 'DateiSortieren Agent'"
