Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "start_silent.bat", 0, False
WshShell.Run "http://localhost:5000", 1, False
