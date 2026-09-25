# Origin Hut UN Comtrade Refresh Scheduler

Origin Hut uses Windows Task Scheduler to launch the local Comtrade
refresh orchestrator.

Task name:

    Origin Hut - UN Comtrade Refresh

Runner:

    infra/windows/Run-ComtradeRefresh.ps1

Local configuration:

    services/data/config/comtrade_refresh.local.json

The local configuration and runtime logs are not committed.

Dry run:

    .\infra\windows\Run-ComtradeRefresh.ps1 -DryRun

The scheduled task is installed disabled. It must remain disabled
until UN_COMTRADE_API_KEY has been configured and authenticated_data
has been live-tested.

Runtime logs:

    logs/comtrade-refresh/

The runner also uses the named mutex:

    Local\OriginHutComtradeRefresh

This prevents overlapping refresh processes.

## Verified local state

Verified on the Origin Hut Windows runtime:

- Task name: Origin Hut - UN Comtrade Refresh
- Trigger: daily at 03:00 local time
- State: Disabled
- Runner: infra/windows/Run-ComtradeRefresh.ps1
- Local config: services/data/config/comtrade_refresh.local.json
- Dry-run launcher: Passed
- Python exit code: 0
- Production scheduled execution: Not yet enabled

The task must remain disabled until authenticated UN Comtrade Data API
access has been configured and live-tested.
