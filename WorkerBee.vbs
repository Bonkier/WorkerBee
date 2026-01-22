Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

currentFolder = fso.GetParentFolderName(WScript.ScriptFullName)

dataFolder = currentFolder & "\all data"

shell.CurrentDirectory = dataFolder

shell.Run "python gui_launcher.py", 0, False