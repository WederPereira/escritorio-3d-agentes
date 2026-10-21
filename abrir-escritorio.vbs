' Abre o Escritorio dos Agentes com um clique: liga o servidor escondido (se ainda nao estiver ligado)
' e abre o Chrome no perfil onde a extensao das telas esta instalada.
Option Explicit
Const URL = "http://127.0.0.1:8765/escritorio-3d.html"
Const PERFIL = "Default"

Dim sh, fso, pasta, i
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
pasta = fso.GetParentFolderName(WScript.ScriptFullName)

Function ServidorLigado()
  On Error Resume Next
  Dim http
  Set http = CreateObject("MSXML2.ServerXMLHTTP")
  http.setTimeouts 500, 500, 500, 500
  http.open "GET", "http://127.0.0.1:8765/yt.html", False
  http.send
  ServidorLigado = (Err.Number = 0 And http.status = 200)
End Function

If Not ServidorLigado() Then
  sh.CurrentDirectory = pasta
  sh.Run "python -m http.server 8765 --bind 127.0.0.1", 0, False
  For i = 1 To 20
    WScript.Sleep 250
    If ServidorLigado() Then Exit For
  Next
End If

Dim chrome
chrome = sh.ExpandEnvironmentStrings("%ProgramFiles%") & "\Google\Chrome\Application\chrome.exe"
If Not fso.FileExists(chrome) Then chrome = sh.ExpandEnvironmentStrings("%LocalAppData%") & "\Google\Chrome\Application\chrome.exe"
sh.Run """" & chrome & """ --profile-directory=""" & PERFIL & """ " & URL, 1, False
