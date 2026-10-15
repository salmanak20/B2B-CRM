param(
    [Parameter(Mandatory=$true)]
    [string]$FilePath,
    [Parameter(Mandatory=$true)]
    [string]$OutPath
)

Add-Type -AssemblyName System.IO.Compression.FileSystem

$tempZip = "$FilePath.zip"
Copy-Item $FilePath $tempZip -Force

try {
    $zip = [System.IO.Compression.ZipFile]::OpenRead($tempZip)
    $entry = $zip.Entries | Where-Object { $_.FullName -eq 'word/document.xml' }

    if ($entry) {
        $stream = $entry.Open()
        $reader = New-Object System.IO.StreamReader($stream)
        $xmlStr = $reader.ReadToEnd()
        $reader.Close()

        # Strip all XML tags, replace with space
        $text = $xmlStr -replace '<w:p[^>]*>', "`r`n`r`n"
        $text = $text -replace '<w:br[^>]*>', "`r`n"
        $text = $text -replace '<[^>]+>', ''
        $text = $text -replace '&amp;', '&'
        $text = $text -replace '&lt;', '<'
        $text = $text -replace '&gt;', '>'

        [System.IO.File]::WriteAllText($OutPath, $text)
        Write-Host "Successfully extracted text to $OutPath"
    } else {
        Write-Host "Could not find word/document.xml in $FilePath"
    }
}
finally {
    if ($zip) { $zip.Dispose() }
    Remove-Item $tempZip -Force -ErrorAction SilentlyContinue
}
