$ErrorActionPreference = 'Stop'

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$sqlPath = Join-Path $scriptDir 'setup-pricing-agent-test-scenarios.sql'

if (-not (Test-Path $sqlPath)) {
    throw "SQL fixture file not found: $sqlPath"
}

Write-Host "Loading deterministic pricing-agent test fixtures into Postgres..."
Get-Content -Raw $sqlPath | docker compose exec -T postgres psql -U smart_pricing -d smart_pricing

$events = @(
    @{
        event_id = 'test-drop-9001'
        product_id = 9001
        competitor_name = 'FlipMart'
        old_price = '980.00'
        new_price = '820.00'
        change_percent = '-16.3'
        timestamp = [DateTime]::UtcNow.ToString('yyyy-MM-ddTHH:mm:ssZ')
    },
    @{
        event_id = 'test-increase-9002'
        product_id = 9002
        competitor_name = 'FlipMart'
        old_price = '1080.00'
        new_price = '1120.00'
        change_percent = '3.7'
        timestamp = [DateTime]::UtcNow.AddSeconds(1).ToString('yyyy-MM-ddTHH:mm:ssZ')
    }
)

foreach ($event in $events) {
    $json = $event | ConvertTo-Json -Compress
    Write-Host "Publishing Kafka event for product $($event.product_id)..."
    $json | docker compose exec -T kafka kafka-console-producer --bootstrap-server localhost:9092 --topic price-changes | Out-Null
}

Write-Host "Done. Watch the pricing agent with:"
Write-Host "  docker compose logs -f pricing-agent"
