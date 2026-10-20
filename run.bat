@echo off
rem 宏观监测看板 - Windows 入口
setlocal
rem 输出为 UTF-8，把控制台切到 UTF-8 代码页避免中文乱码
chcp 65001 >nul
set "ROOT=%~dp0"
rem %~dp0 末尾带反斜杠，会破坏后面的引号，必须去掉
set "ROOT=%ROOT:~0,-1%"
set "PYTHONPATH=%ROOT%\src;%PYTHONPATH%"
rem 无参数双击时默认执行完整月度流水线（幂等：同月重复运行不重复消费），结束后停住窗口显示结果
if "%~1"=="" goto run
python -m macro_monitor.cli --project "%ROOT%" %*
goto done
:run
python -m macro_monitor.cli --project "%ROOT%" run
pause
:done
endlocal
