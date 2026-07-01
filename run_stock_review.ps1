param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$CliArgs
)

Set-Location $PSScriptRoot

if (-not $CliArgs -or $CliArgs.Count -eq 0) {
    Write-Host "Stock Recognition System"
    Write-Host ""
    Write-Host "Common commands:"
    Write-Host "  .\run_stock_review.ps1 review --message-file examples\group_message.txt --current-price 21.90 --simulate"
    Write-Host "  .\run_stock_review.ps1 review --message-file examples\group_message.txt --auto-market-data --simulate"
    Write-Host "  .\run_stock_review.ps1 simulate-list"
    Write-Host "  .\run_stock_review.ps1 simulate-refresh"
    Write-Host "  .\run_stock_review.ps1 simulate-summary --all"
    Write-Host ""
    python -m stock_recognition_system.cli --help
    return
}

python -m stock_recognition_system.cli @CliArgs
