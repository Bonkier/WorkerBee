Set Shell = CreateObject("WScript.Shell")
Set FSO = CreateObject("Scripting.FileSystemObject")

' Get the current folder path
CurrentPath = FSO.GetParentFolderName(WScript.ScriptFullName)

IconPath = CurrentPath & "\all data\app_icon.ico"
TargetPath = CurrentPath & "\all data\WorkerBee.vbs"
ShortcutPath = CurrentPath & "\WorkerBee.lnk"

Set Link = Shell.CreateShortcut(ShortcutPath)
Link.TargetPath = TargetPath
Link.IconLocation = IconPath
Link.WindowStyle = 7 
Link.Save

MsgBox "Shortcut created successfully! You can now use 'WorkerBee'.", 64, "Installation Complete"

FSO.DeleteFile WScript.ScriptFullName
