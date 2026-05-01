Set WshShell = CreateObject("WScript.Shell")
scriptDir = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
' Run start.bat completely hidden (0 means vbHide)
WshShell.Run chr(34) & scriptDir & "\start.bat" & Chr(34), 0
Set WshShell = Nothing
