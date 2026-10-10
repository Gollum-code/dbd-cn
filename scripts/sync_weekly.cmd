@echo off
REM dbd-cn 每周同步脚本（可挂 Windows 任务计划程序）
REM 用法: scripts\sync_weekly.cmd [db路径]
setlocal

set PYTHON=python
set ROOT=%~dp0..
set DB=%1
if "%DB%"=="" set DB=%ROOT%\data\dbd_cn.db

echo [%date% %time%] dbd-cn sync start >> "%ROOT%\data\sync.log"
"%PYTHON%" -m crawler.sync --db "%DB%" >> "%ROOT%\data\sync.log" 2>&1
"%PYTHON%" -m wiki.generate --db "%DB%" --out "%ROOT%\site" >> "%ROOT%\data\sync.log" 2>&1
echo [%date% %time%] dbd-cn sync end >> "%ROOT%\data\sync.log"

endlocal