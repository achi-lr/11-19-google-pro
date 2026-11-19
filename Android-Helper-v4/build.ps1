# Rebuild the native C# application and bundled Python worker.
param([string]$Python = 'python', [string]$Output = (Join-Path $PSScriptRoot 'build'))
$ErrorActionPreference = 'Stop'
$Output = [IO.Path]::GetFullPath($Output)
$taskSource = Join-Path $PSScriptRoot 'src'
$taskCompiler = Join-Path $env:WINDIR 'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
if (-not (Test-Path -LiteralPath $taskCompiler)) { throw '.NET Framework 4.x compiler is required.' }
New-Item -ItemType Directory -Path $Output,(Join-Path $Output 'runtime'),(Join-Path $Output 'temporary-build') -Force | Out-Null
& $taskCompiler /nologo /target:winexe /optimize+ /reference:System.Windows.Forms.dll /reference:System.Drawing.dll /reference:System.Web.Extensions.dll ('/out:' + (Join-Path $Output 'AndroidHelper.exe')) (Join-Path $taskSource 'AndroidHelper.cs') (Join-Path $taskSource 'UiText.cs') (Join-Path $taskSource 'Preferences.cs')
if ($LASTEXITCODE -ne 0) { throw 'C# compilation failed.' }
& $Python -m PyInstaller --noconfirm --clean --onedir --console --name AndroidWorker --distpath (Join-Path $Output 'runtime/worker-build') --workpath (Join-Path $Output 'temporary-build') --specpath (Join-Path $Output 'temporary-build') --paths $taskSource --add-data ((Join-Path $taskSource 'billing.js') + ';.') --add-data ((Join-Path $taskSource 'billing-module.apk') + ';.') (Join-Path $taskSource 'desktop_worker.py')
if ($LASTEXITCODE -ne 0) { throw 'Python worker compilation failed.' }
New-Item -ItemType Directory -Path (Join-Path $Output 'runtime/worker') -Force | Out-Null
Get-ChildItem -LiteralPath (Join-Path $Output 'runtime/worker-build/AndroidWorker') | Copy-Item -Destination (Join-Path $Output 'runtime/worker') -Recurse -Force
foreach($taskFile in @('adb.exe','AdbWinApi.dll','AdbWinUsbApi.dll','NOTICE.txt')) { Copy-Item -LiteralPath (Join-Path $PSScriptRoot "runtime/$taskFile") -Destination (Join-Path $Output 'runtime') }
foreach($taskFile in @('START.bat','START HERE.txt','НАЧНИТЕ ЗДЕСЬ.txt')) { Copy-Item -LiteralPath (Join-Path $PSScriptRoot $taskFile) -Destination $Output }
Write-Host 'Built AndroidHelper.exe and runtime/. Run START.bat.'

