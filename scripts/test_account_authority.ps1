$ErrorActionPreference = 'Stop'
$containerName = 'robo-auth-test-20261012'
$image = 'uengine/ontological-db:0.1.0-wb50d7aaa-ae1e8e9ab-s0aae44'
$passwordBytes = [byte[]]::new(32)
[Security.Cryptography.RandomNumberGenerator]::Fill($passwordBytes)
$testPassword = [Convert]::ToHexString($passwordBytes)
$oldTestDsn = $env:AUTH_TEST_PG_DSN
$oldPgDsn = $env:OG_PG_DSN
$created = $false
try {
    $existing = docker ps -a --filter "name=^/$containerName$" --format '{{.Names}}'
    if ($LASTEXITCODE -ne 0) { throw 'Docker not available' }
    if ($existing) { throw 'Test container already exists; inspect it before retrying' }
    $null = docker run -d --name $containerName --label org.uengine.robo.purpose=auth-isolated-test --tmpfs /var/lib/postgresql/data -p 127.0.0.1::5432 -e POSTGRES_USER=auth_operator -e "POSTGRES_PASSWORD=$testPassword" -e POSTGRES_DB=auth_test -e OG_GRAPH_DESIGN=auth_test -e OG_GRAPH_ANALYSIS=auth_analysis $image
    if ($LASTEXITCODE -ne 0) { throw 'Test container startup failed' }
    $created = $true
    $ready = $false
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        $null = docker exec $containerName pg_isready -U auth_operator -d auth_test
        if ($LASTEXITCODE -eq 0) { $ready = $true; break }
        Start-Sleep -Seconds 1
    }
    if (-not $ready) { throw 'Test DB did not become ready' }
    $portJson = docker inspect --format '{{json (index .NetworkSettings.Ports "5432/tcp")}}' $containerName
    $port = ($portJson | ConvertFrom-Json)[0].HostPort
    $env:AUTH_TEST_PG_DSN = "host=127.0.0.1 port=$port dbname=auth_test user=auth_operator password=$testPassword connect_timeout=5"
    $env:OG_PG_DSN = $env:AUTH_TEST_PG_DSN
    & .\.venv\Scripts\python.exe -m pytest api/features/accounts api/features/code_templates/test_template_overrides.py api/features/code_templates/test_code_templates.py api/features/code_templates/test_template_syntax.py api/features/code_templates/test_history_database.py api/features/auth/test_swp.py api/features/auth/test_figma_pairing.py api/features/ingestion/tests/test_runs.py api/features/ingestion/hybrid/tests/test_run_record_before_wipe.py --basetemp .pytest-authority-isolated -q
    $testExit = $LASTEXITCODE
    if ($testExit -ne 0) { throw "Authority tests failed ($testExit)" }
} finally {
    $env:AUTH_TEST_PG_DSN = $oldTestDsn
    $env:OG_PG_DSN = $oldPgDsn
    if ($created) {
        $null = docker rm -f $containerName
        if ($LASTEXITCODE -ne 0) { throw 'Test container cleanup failed; inspect robo-auth-test-20261012' }
        Write-Output 'Isolated test container removed; production DB unchanged.'
    }
}
