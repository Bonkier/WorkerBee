Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

currentFolder = fso.GetParentFolderName(WScript.ScriptFullName)

shell.CurrentDirectory = currentFolder

shell.Run "python bootstrapper.py", 0, False