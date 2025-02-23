Dim objShell
Set objShell = CreateObject("WScript.Shell")
objShell.Run "cmd.exe /c python atualizar_sistema.py", 0, False
Set objShell = Nothing
