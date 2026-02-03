param(
  [string]$Python = "python"
)

& $Python -m pip install -r requirements.txt
& $Python -m PyInstaller monitor.spec
