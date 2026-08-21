# Frischt den mitgebrachten Stand auf und veroeffentlicht ihn, wenn er sich
# geaendert hat. Fuer die Windows-Aufgabenplanung gedacht:
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File scraper\stand_auffrischen.ps1
#
# festivalticker antwortet diesem Rechner, dem taeglichen Lauf auf fremden
# Servern dagegen mit 403. Was hier geholt wird, geht als
# data/schnappschuss/festivalticker.json.gz mit in die Versionsverwaltung -
# der Push stoesst zugleich den Serverlauf an, der es dann mitliest.

$ErrorActionPreference = 'Stop'
$wurzel = Split-Path $PSScriptRoot -Parent
Set-Location $wurzel
$env:PYTHONIOENCODING = 'utf-8'

$protokoll = Join-Path $wurzel 'data\stand.log'
function Notiere($text) {
    $zeile = "{0:yyyy-MM-dd HH:mm}  {1}" -f (Get-Date), $text
    Add-Content -Path $protokoll -Value $zeile -Encoding utf8
}

# Ueber Dateien statt ueber die Pipeline: Windows PowerShell schreibt sonst
# UTF-16 ins Protokoll und macht aus jedem Umlaut Buchstabensalat.
$ausgabe = Join-Path $env:TEMP 'stand_auffrischen.out'
$fehler = Join-Path $env:TEMP 'stand_auffrischen.err'

Notiere 'Stand auffrischen ...'
$lauf = Start-Process -FilePath 'python' -ArgumentList 'scraper/stand_auffrischen.py' `
    -NoNewWindow -Wait -PassThru -RedirectStandardOutput $ausgabe -RedirectStandardError $fehler
foreach ($datei in @($ausgabe, $fehler)) {
    if (Test-Path $datei) {
        Get-Content $datei -Encoding utf8 | Where-Object { $_ -and $_ -notmatch '^\s+\w+: \d+/\d+$' } |
            ForEach-Object { Notiere "  $_" }
        Remove-Item $datei
    }
}

if ($lauf.ExitCode -ne 0) {
    # Nichts gefunden: Der bisherige Stand bleibt stehen, veroeffentlicht wird
    # nichts. Eine leere Ablage waere schlimmer als eine aeltere.
    Notiere "Abbruch: der Lauf brachte nichts (Code $($lauf.ExitCode))"
    exit $lauf.ExitCode
}

git add data/schnappschuss
git diff --cached --quiet
if ($LASTEXITCODE -eq 0) {
    Notiere 'Unveraendert - nichts zu veroeffentlichen'
    exit 0
}

$heute = Get-Date -Format 'yyyy-MM-dd'
git commit -q -m "Stand von festivalticker: $heute"
if (-not $?) { Notiere 'Commit fehlgeschlagen'; exit 1 }
git push -q
if (-not $?) { Notiere 'Push fehlgeschlagen - der Commit liegt lokal bereit'; exit 1 }
Notiere "Veroeffentlicht: Stand vom $heute"
