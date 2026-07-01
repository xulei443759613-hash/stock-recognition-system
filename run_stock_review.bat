@echo off
setlocal
cd /d "%~dp0"

if "%~1"=="" (
  echo Stock Recognition System
  echo.
  echo Common commands:
  echo   run_stock_review.bat review --message-file examples\group_message.txt --current-price 21.90 --simulate
  echo   run_stock_review.bat review --message-file examples\group_message.txt --auto-market-data --simulate
  echo   run_stock_review.bat simulate-list
  echo   run_stock_review.bat simulate-refresh
  echo   run_stock_review.bat simulate-summary --all
  echo.
  python -m stock_recognition_system.cli --help
  echo.
  pause
  exit /b 0
)

python -m stock_recognition_system.cli %*
