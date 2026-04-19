# Registers 3 daily Windows Task Scheduler tasks that run the Shorts pipeline.
# Run once as the current user (no admin needed for per-user tasks).
# Usage (from PowerShell):   powershell -ExecutionPolicy Bypass -File register_tasks.ps1

$scriptPath = "C:\Users\murat\Desktop\yeni\run_shorts.bat"
$workingDir = "C:\Users\murat\Desktop\yeni"

$schedule = @(
    @{ Name = "ShortsBot-Morning";   Time = "10:00" },
    @{ Name = "ShortsBot-Afternoon"; Time = "14:00" },
    @{ Name = "ShortsBot-Evening";   Time = "19:00" }
)

foreach ($item in $schedule) {
    $action  = New-ScheduledTaskAction `
        -Execute $scriptPath `
        -WorkingDirectory $workingDir

    $trigger = New-ScheduledTaskTrigger -Daily -At $item.Time

    $settings = New-ScheduledTaskSettingsSet `
        -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries `
        -StartWhenAvailable `
        -MultipleInstances IgnoreNew `
        -ExecutionTimeLimit (New-TimeSpan -Minutes 30)

    $principal = New-ScheduledTaskPrincipal `
        -UserId $env:USERNAME `
        -LogonType Interactive `
        -RunLevel Limited

    # Delete the task first if it exists (idempotent re-run)
    Unregister-ScheduledTask -TaskName $item.Name -Confirm:$false -ErrorAction SilentlyContinue

    Register-ScheduledTask `
        -TaskName $item.Name `
        -Action $action `
        -Trigger $trigger `
        -Settings $settings `
        -Principal $principal `
        -Description "Auto-uploads a history YouTube Short. Runs run_shorts.bat."
    Write-Host ("Registered: {0} at {1}" -f $item.Name, $item.Time)
}

Write-Host ""
Write-Host "All done. View or edit in Task Scheduler:"
Write-Host "  taskschd.msc -> Task Scheduler Library -> ShortsBot-*"
