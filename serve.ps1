param(
    [int]$Port = 8420
)

Add-Type -AssemblyName System.Net.HttpListener -ErrorAction SilentlyContinue

$root = $PSScriptRoot
$listener = New-Object System.Net.HttpListener
$prefix = "http://localhost:$Port/"
$listener.Prefixes.Add($prefix)

try {
    $listener.Start()
} catch {
    Write-Host "Konnte Port $Port nicht oeffnen: $($_.Exception.Message)"
    exit 1
}

$mime = @{
    ".html" = "text/html; charset=utf-8"
    ".css"  = "text/css; charset=utf-8"
    ".js"   = "application/javascript; charset=utf-8"
    ".json" = "application/json; charset=utf-8"
    ".svg"  = "image/svg+xml"
    ".png"  = "image/png"
    ".ico"  = "image/x-icon"
}

function Resolve-PythonExe {
    $found = Get-ChildItem "$env:LOCALAPPDATA\Programs\Python\Python3*\python.exe" -ErrorAction SilentlyContinue |
        Select-Object -First 1 -ExpandProperty FullName
    if ($found) { return $found }
    $candidate = (Get-Command python -ErrorAction SilentlyContinue).Source
    if ($candidate -and $candidate -notlike "*WindowsApps*") { return $candidate }
    return $null
}

function Write-JsonResponse($response, $statusCode, $obj) {
    $json = $obj | ConvertTo-Json -Compress -Depth 5
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($json)
    $response.StatusCode = $statusCode
    $response.ContentType = "application/json; charset=utf-8"
    $response.ContentLength64 = $bytes.Length
    $response.OutputStream.Write($bytes, 0, $bytes.Length)
}

Write-Host "Basis-Dashboard laeuft auf $prefix (Strg+C zum Beenden)"

while ($listener.IsListening) {
    $context = $listener.GetContext()
    $request = $context.Request
    $response = $context.Response

    $relPath = [System.Uri]::UnescapeDataString($request.Url.AbsolutePath)

    if ($request.HttpMethod -eq "POST" -and $relPath -eq "/api/sync") {
        $pythonExe = Resolve-PythonExe
        if (-not $pythonExe) {
            Write-JsonResponse $response 500 @{ ok = $false; log = "Konnte keine Python-Installation finden." }
            $response.OutputStream.Close()
            continue
        }
        $syncDir = Join-Path $root "sync"
        $psi = New-Object System.Diagnostics.ProcessStartInfo
        $psi.FileName = $pythonExe
        $psi.Arguments = "sync.py"
        $psi.WorkingDirectory = $syncDir
        $psi.RedirectStandardOutput = $true
        $psi.RedirectStandardError = $true
        $psi.UseShellExecute = $false
        $psi.StandardOutputEncoding = [System.Text.Encoding]::UTF8
        $psi.StandardErrorEncoding = [System.Text.Encoding]::UTF8
        try {
            $proc = [System.Diagnostics.Process]::Start($psi)
            $stdout = $proc.StandardOutput.ReadToEnd()
            $stderr = $proc.StandardError.ReadToEnd()
            $proc.WaitForExit()
            $ok = $proc.ExitCode -eq 0
            Write-JsonResponse $response 200 @{ ok = $ok; log = ($stdout + $stderr).Trim() }
        } catch {
            Write-JsonResponse $response 500 @{ ok = $false; log = $_.Exception.Message }
        }
        $response.OutputStream.Close()
        continue
    }

    if ($relPath -eq "/") { $relPath = "/index.html" }
    $filePath = Join-Path $root ($relPath.TrimStart("/"))

    if (Test-Path $filePath -PathType Leaf) {
        $ext = [System.IO.Path]::GetExtension($filePath).ToLower()
        $contentType = $mime[$ext]
        if (-not $contentType) { $contentType = "application/octet-stream" }
        $bytes = [System.IO.File]::ReadAllBytes($filePath)
        $response.ContentType = $contentType
        $response.ContentLength64 = $bytes.Length
        $response.OutputStream.Write($bytes, 0, $bytes.Length)
    } else {
        $response.StatusCode = 404
        $notFound = [System.Text.Encoding]::UTF8.GetBytes("404 - nicht gefunden: $relPath")
        $response.OutputStream.Write($notFound, 0, $notFound.Length)
    }
    $response.OutputStream.Close()
}
