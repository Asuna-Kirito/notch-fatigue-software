@echo off
chcp 65001 >nul
echo 卸载：将删除整个程序文件夹 %~dp0
echo 其中包括 _internal\数据 下保存的计算结果、自定义曲线和设置，需要保留的请先复制出来。
choice /c YN /m "确定卸载（Y 是 / N 否）"
if errorlevel 2 exit /b
cd /d "%TEMP%"
start "" /min cmd /c "timeout /t 2 /nobreak >nul & rmdir /s /q "%~dp0""
