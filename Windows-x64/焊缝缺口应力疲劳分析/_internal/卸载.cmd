@echo off
chcp 65001 >nul
for %%I in ("%~dp0..") do set "APPDIR=%%~fI"
echo.
echo 卸载：将删除整个程序文件夹
echo   %APPDIR%
echo 其中 data、solution、report、figure 文件夹里的模型、计算任务、报告和图片也会删除，需要保留的请先复制出来。
echo 软件没有写注册表，也没有在 AppData 等系统目录中留下文件，删除该文件夹即卸载干净。
echo.
choice /c YN /m "确定卸载（Y 是 / N 否）"
if errorlevel 2 exit /b
cd /d "%TEMP%"
start "" /min cmd /c "timeout /t 2 /nobreak >nul & rmdir /s /q "%APPDIR%""
