For /f "tokens=1-2 delims=/:" %%a in ('time /t') do (set mytime=%%a.%%b)
start_launcher_Greedie_Bot-V3 2>&1 | tee "logs\log_%date%_%mytime%.txt"