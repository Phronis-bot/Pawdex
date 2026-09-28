# Send the committed code to the server and restart Pawdex there. Run from the repo root:
#   .\deploy\push.ps1 -Server 203.0.113.10          # API only
#   .\deploy\push.ps1 -Server 203.0.113.10 -Web     # also rebuild and upload the web app
# Uses your SSH key; the server needs no access to GitHub. Only committed files are sent,
# and the server's .env (secrets) is never touched.
param([Parameter(Mandatory = $true)][string]$Server, [string]$User = "root", [switch]$Web)

# Not "Stop": Windows PowerShell treats anything a native tool writes to stderr (Docker's
# progress output, for one) as an error. Success is checked with $LASTEXITCODE instead.
$ErrorActionPreference = "Continue"

if ($Web) {
    # The Telegram Mini App: the same Flutter app built for the web, served at /play/.
    Push-Location app
    # --no-web-resources-cdn: serve CanvasKit from our server, not Google's CDN, so the
    # Mini App doesn't depend on an extra slow (or blocked) download on phones.
    flutter build web --release --base-href /play/ --no-web-resources-cdn
    $built = $LASTEXITCODE
    Pop-Location
    if ($built -ne 0) { throw "flutter build web failed" }
    $webTar = Join-Path $env:TEMP "pawdex-web.tar"
    tar -cf $webTar -C app/build/web .
    scp -q $webTar "${User}@${Server}:/tmp/pawdex-web.tar"
    if ($LASTEXITCODE -ne 0) { throw "web upload failed" }
    Remove-Item $webTar
    # Empty the folder rather than deleting it: Caddy's bind mount points at this exact
    # directory, and a re-created one would stay invisible to it (the Mini App got 404s).
    ssh "${User}@${Server}" "mkdir -p /opt/pawdex/web && find /opt/pawdex/web -mindepth 1 -delete && tar -xf /tmp/pawdex-web.tar -C /opt/pawdex/web && rm /tmp/pawdex-web.tar"
    if ($LASTEXITCODE -ne 0) { throw "web unpack failed" }
}

$archive = Join-Path $env:TEMP "pawdex-deploy.tar"
git archive --format=tar -o $archive HEAD
if ($LASTEXITCODE -ne 0) { throw "git archive failed" }

scp -q $archive "${User}@${Server}:/tmp/pawdex-deploy.tar"
if ($LASTEXITCODE -ne 0) { throw "upload failed" }
Remove-Item $archive

# 2>&1 on the server side, so progress output arrives as ordinary text.
ssh "${User}@${Server}" "mkdir -p /opt/pawdex/web && tar -xf /tmp/pawdex-deploy.tar -C /opt/pawdex && rm /tmp/pawdex-deploy.tar && sh /opt/pawdex/deploy/deploy.sh 2>&1"
if ($LASTEXITCODE -ne 0) { throw "deploy failed on the server (exit code $LASTEXITCODE)" }
