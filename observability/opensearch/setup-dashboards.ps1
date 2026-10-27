param([string]$DashboardsUrl = 'http://localhost:5601')
$ErrorActionPreference = 'Stop'
$base = $DashboardsUrl.TrimEnd('/')
$uri = "$base/api/saved_objects/index-pattern/springboot-user-logs"
$headers = @{ 'osd-xsrf' = 'true' }
$existing = $null
try {
    $existing = Invoke-RestMethod -Uri $uri -Headers $headers -TimeoutSec 15
}
catch {
    if (-not $_.Exception.Response -or [int]$_.Exception.Response.StatusCode -ne 404) { throw }
}
$title = if ($existing) { $existing.attributes.title } else { 'springboot-user-logs*' }
$timeField = if ($existing) { $existing.attributes.timeFieldName } else { '@timestamp' }
$pattern = [Uri]::EscapeDataString($title)
# Use Dashboards field discovery so types and aggregation capabilities match the UI.
$fieldsUri = "$base/api/index_patterns/_fields_for_wildcard?pattern=$pattern&meta_fields=_source&meta_fields=_id&meta_fields=_type&meta_fields=_index&meta_fields=_score"
$discovered = Invoke-RestMethod -Uri $fieldsUri -Headers $headers -TimeoutSec 30
$fields = @($discovered.fields)
if ($fields.Count -eq 0) { throw "No fields found for $title. Wait for log ingestion and rerun setup." }
$previous = @()
if ($existing -and $existing.attributes.fields) {
    $previous = @($existing.attributes.fields | ConvertFrom-Json | ForEach-Object { $_ })
}
# Retain scripted fields and field popularity/custom labels during refresh.
foreach ($field in $fields) {
    $old = $previous | Where-Object { $_.name -eq $field.name } | Select-Object -First 1
    foreach ($property in @('count', 'customLabel')) {
        if ($old -and $old.PSObject.Properties[$property]) {
            $field | Add-Member -NotePropertyName $property -NotePropertyValue $old.$property -Force
        }
    }
}
$fields += @($previous | Where-Object { $_.scripted -and $_.name -notin $fields.name })
if ($timeField) {
    $timestamp = $fields | Where-Object { $_.name -eq $timeField -and $_.type -eq 'date' -and $_.aggregatable }
    if (-not $timestamp) { throw "Time field '$timeField' is not an aggregatable date in $title. Check ingestion and mappings before rerunning setup." }
}
$attributes = @{ fields = ConvertTo-Json -InputObject @($fields) -Depth 20 -Compress }
$method = 'Put'
$payload = @{ attributes = $attributes }
if ($existing) {
    # Partial update preserves formatting, references, and other user settings.
    $payload.version = $existing.version
}
else {
    $method = 'Post'
    $attributes.title = $title
    $attributes.timeFieldName = $timeField
}
$body = $payload | ConvertTo-Json -Depth 25
$null = Invoke-RestMethod -Method $method -Uri $uri -Headers $headers -ContentType 'application/json' -Body $body -TimeoutSec 15
$verified = Invoke-RestMethod -Uri $uri -Headers $headers -TimeoutSec 15
$savedFields = @($verified.attributes.fields | ConvertFrom-Json | ForEach-Object { $_ })
if ($timeField -and -not ($savedFields | Where-Object { $_.name -eq $timeField -and $_.type -eq 'date' })) {
    throw "Index pattern verification failed: missing time field '$timeField'."
}
Write-Output "Refreshed $title with $($savedFields.Count) fields."
Write-Output "Open or reload $base/app/discover and select $title."

