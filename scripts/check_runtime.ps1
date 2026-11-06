$ErrorActionPreference = "Continue"

Write-Host "Python launchers:"
py -0p

Write-Host ""
Write-Host "Selected Python 3.13:"
py -3.13 --version

Write-Host ""
Write-Host "Node.js:"
node --version
npm --version

Write-Host ""
Write-Host "Ollama:"
ollama --version
ollama list
