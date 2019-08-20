@echo on
For /f "tokens=1-2 delims=/:" %%a in ('time /t') do (set mytime=%%a.%%b)
cmd /k "start_Greedie_Bot-V3.bat 2>&1 | tee logs\log_%date%_%mytime%.txt"