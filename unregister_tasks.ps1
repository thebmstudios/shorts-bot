# Removes all ShortsBot scheduled tasks.
# Usage:   powershell -ExecutionPolicy Bypass -File unregister_tasks.ps1

$names = "ShortsBot-Morning", "ShortsBot-Afternoon", "ShortsBot-Evening"
foreach ($n in $names) {
    Unregister-ScheduledTask -TaskName $n -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "Removed: $n"
}
