Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
strPath = fso.GetParentFolderName(WScript.ScriptFullName)

' Jalankan server web via pythonw (tanpa console window)
WshShell.Run """C:\Program Files\Python310\pythonw.exe"" """ & strPath & "\web\server.py""", 0, False

' Tunggu 2 detik lalu buka browser
WScript.Sleep 2000
WshShell.Run "http://localhost:5050"
