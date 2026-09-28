# Send the committed code to the server and restart Pawdex there. Run from the repo root:
#   .\deploy\push.ps1 -Server 203.0.113.10
# Uses your SSH key; the server needs no access to GitHub. Only committed files are sent,
# and the server's .env (secrets) is never touched.
param([Parameter(Mandatory = $true)][string]$Server, [string]$User = "root")

# Not "Stop": Windows PowerShell treats anything a native tool writes to stderr (Docker's
# progress output, for one) as an error. Success is checked with $LASTEXITCODE instead.
$ErrorActionPreference = "Continue"

$archive = Join-Path $env:TEMP "pawdex-deploy.tar"
git archive --format=tar -o $archive HEAD
if ($LASTEXITCODE -ne 0) { throw "git archive failed" }

scp -q $archive "${User}@${Server}:/tmp/pawdex-deploy.tar"
if ($LASTEXITCODE -ne 0) { throw "upload failed" }
Remove-Item $archive

# 2>&1 on the server side, so progress output arrives as ordinary text.
ssh "${User}@${Server}" "mkdir -p /opt/pawdex && tar -xf /tmp/pawdex-deploy.tar -C /opt/pawdex && rm /tmp/pawdex-deploy.tar && sh /opt/pawdex/deploy/deploy.sh 2>&1"
if ($LASTEXITCODE -ne 0) { throw "deploy failed on the server (exit code $LASTEXITCODE)" }
