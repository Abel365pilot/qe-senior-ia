@echo off
setlocal EnableExtensions

set "QE_MVN_VERSION=3.9.11"
set "QE_PROJECT_DIR=%~dp0"
set "QE_MVN_CACHE=%QE_PROJECT_DIR%.mvn\wrapper\dists\apache-maven-%QE_MVN_VERSION%"
set "QE_MVN_BIN=%QE_MVN_CACHE%\apache-maven-%QE_MVN_VERSION%\bin\mvn.cmd"
set "QE_MVN_ZIP=%QE_MVN_CACHE%\apache-maven-%QE_MVN_VERSION%-bin.zip"
set "QE_MVN_URL=https://repo.maven.apache.org/maven2/org/apache/maven/apache-maven/%QE_MVN_VERSION%/apache-maven-%QE_MVN_VERSION%-bin.zip"
set "QE_MVN_SHA512=03e2d65d4483a3396980629f260e25cac0d8b6f7f2791e4dc20bc83f9514db8d0f05b0479e699a5f34679250c49c8e52e961262ded468a20de0be254d8207076"

if exist "%QE_MVN_BIN%" goto run_maven

if not exist "%QE_MVN_CACHE%" mkdir "%QE_MVN_CACHE%"
echo Descargando Apache Maven %QE_MVN_VERSION% (una sola vez)...
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ErrorActionPreference='Stop'; $ProgressPreference='SilentlyContinue';" ^
  "Invoke-WebRequest -Uri '%QE_MVN_URL%' -OutFile '%QE_MVN_ZIP%';" ^
  "$stream=[IO.File]::OpenRead('%QE_MVN_ZIP%'); try { $sha=[Security.Cryptography.SHA512]::Create(); $actual=([BitConverter]::ToString($sha.ComputeHash($stream))).Replace('-','').ToLowerInvariant() } finally { $stream.Dispose() };" ^
  "if($actual -ne '%QE_MVN_SHA512%'){ throw 'SHA-512 de Maven no coincide' };" ^
  "Expand-Archive -LiteralPath '%QE_MVN_ZIP%' -DestinationPath '%QE_MVN_CACHE%' -Force"

if errorlevel 1 exit /b 1

:run_maven
call "%QE_MVN_BIN%" %*
exit /b %errorlevel%
