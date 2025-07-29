@echo off
echo Starting simulation loop...

setlocal enabledelayedexpansion

for /L %%i in (1,1,12) do (
    echo Simulating %%i/12...
    curl http://localhost:8080/simulate >nul 2>&1
    timeout /t 5 >nul
)

echo Done.
