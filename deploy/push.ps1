# Send the committed code to the server and restart Pawdex there. Run from the repo root:
#   .\deploy\push.ps1 -Server 203.0.113.10
# Uses your SSH key; the server needs no access to GitHub. Only committed files are sent,
# and the server's .env (secrets) is never touched.
param([Parameter(Mandatory = $true)][string]$Server, [string]$User = "root")
$ErrorActionPreference = "Stop"

$archive = Join-Path $env:TEMP "pawdex-deploy.tar"
git archive --format=tar -o $archive HEAD
if ($LASTEXITCODE -ne 0) { throw "git archive failed" }

scp $archive "${User}@${Server}:/tmp/pawdex-deploy.tar"
if ($LASTEXITCODE -ne 0) { throw "upload failed" }
Remove-Item $archive

ssh "${User}@${Server}" "mkdir -p /opt/pawdex && tar -xf /tmp/pawdex-deploy.tar -C /opt/pawdex && rm /tmp/pawdex-deploy.tar && sh /opt/pawdex/deploy/deploy.sh"
