Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
strPath = fso.GetParentFolderName(WScript.ScriptFullName)

' Bersihkan proses lama agar tidak bentrok
WshShell.Run "taskkill /f /im pythonw.exe", 0, True
WScript.Sleep 500

' Jalankan server baru
WshShell.Run """C:\Program Files\Python310\pythonw.exe"" """ & strPath & "\run.py""", 0, False

' Buka browser
WScript.Sleep 1500
WshShell.Run "http://localhost:5050"
