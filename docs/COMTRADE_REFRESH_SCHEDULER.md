# Origin Hut UN Comtrade Refresh Scheduler

Origin Hut uses Windows Task Scheduler to launch the local UN
Comtrade refresh orchestrator.

Task name:

    Origin Hut - UN Comtrade Refresh

Runner:

    infra/windows/Run-ComtradeRefresh.ps1

Configuration:

    services/data/config/comtrade_refresh.local.json

The local configuration, .env credentials, ingestion artifacts,
refresh state, and runtime logs remain outside Git.


## Runtime safety

The runner uses the named Windows mutex:

    Local\OriginHutComtradeRefresh

Only one refresh process can execute at a time.

The scheduled task also uses Task Scheduler IgnoreNew behavior.

For a production invocation the runner:

1. verifies the local runtime files;
2. starts the Origin Hut PostgreSQL Docker service if necessary;
3. waits for the PostgreSQL health check;
4. launches the refresh orchestrator;
5. records the exit status in the local runtime log.

Dry-run execution deliberately skips PostgreSQL startup and makes no
provider, PostgreSQL, checkpoint, or call-budget state changes.


## Authentication

Authenticated UN Comtrade access uses the local:

    UN_COMTRADE_API_KEY

from the ignored repository-root .env file.

The secret is transported only as the documented subscription-key
query parameter on the actual provider request.

Persisted audit URLs exclude the credential.

Authenticated live validation confirmed that the key does not appear
in ingestion artifacts, tracked files, refresh state, or runner logs.


## Controlled authenticated refresh verification

The authenticated production path was validated before scheduler
activation.

Configured plan:

    India reporter 699
    UAE partner 784
    HS 380210
    annual
    export and import
    rolling 2024 and 2025

Verified result:

    4 tasks completed
    2 observation runs
    2 valid no-data runs
    16 provider calls reserved as retry headroom

2024 export:

    existing canonical observation reused
    canonical source provenance remains public_preview
    authenticated acquisition preserved in its ingestion run

2025 export:

    new authenticated source record inserted
    new authenticated canonical trade flow inserted

Post-refresh database counts:

    data_sources: 5
    ingestion_runs: 11
    source_records: 123982
    ingestion_run_records: 123985
    entity_source_links: 123976
    trade_flows: 3


## Registration

Register or refresh the task but leave it disabled:

    .\infra\windows\Register-ComtradeRefreshTask.ps1 -At "03:00"

Register and enable after final validation:

    .\infra\windows\Register-ComtradeRefreshTask.ps1 -At "03:00" -Enable


## Logs

Runtime logs:

    logs/comtrade-refresh/


## Local runtime behavior

The task uses the current Windows user's interactive principal.

It therefore runs in the local Origin Hut Windows runtime when that
user session is available. StartWhenAvailable is enabled so a missed
schedule can execute when the runtime becomes available again.

Long-term cloud scheduling can replace this local runner without
changing the Comtrade ingestion model.
