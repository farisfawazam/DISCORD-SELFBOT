Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
strPath = fso.GetParentFolderName(WScript.ScriptFullName)

' Jalankan desktop GUI via pythonw (tanpa console window)
WshShell.Run """C:\Program Files\Python310\pythonw.exe"" """ & strPath & "\desktop\app.py""", 0, False
