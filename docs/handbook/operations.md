# Installation, maintenance and recovery

[Handbook index](README.md)

## Docker deployment

Prerequisites: a Linux Docker host, Docker Engine, Docker Compose v2 or newer, Python 3 and access to the local Docker socket. Run setup from the project checkout on that host. Docker Desktop and rootless Docker are not validated targets for this release.

The application image uses Python 3.13 Alpine and Pillow; SNMP tooling is confined to the connector worker image. It runs as UID/GID 1000, with a read-only root filesystem, dropped capabilities and a temporary `/tmp`. Persistent inventory is mounted at `/data`; local connector snapshots are mounted read-only at `/connectors`.

```sh
cp .env.example .env
# Configure ATLAS_BIND and ATLAS_PORT for the intended private interface.
./scripts/setup-connector-runner.sh
```

Run the setup script on the Docker host. It builds the worker image, prepares an empty data directory and private job directory for UID 1000, creates a Docker network, records the socket group and worker subnet in `.env`, then builds and starts Atlas and the controller. Existing inventory files are not recursively re-owned. If an existing data mount is not writable by UID 1000, inspect its ownership before starting; do not blindly change a populated inventory. Existing unrelated environment settings are preserved. The controller holds the Docker socket; Atlas and collector workers do not. Back up deployment configuration before an upgrade.

The default bind is `127.0.0.1` and the default external port is 8097. Inside the container the HTTP application listens on 8765. Configure a LAN bind only when intended. Full UI/state administration currently has no account login or general API token gate; keep deployment within the intended trusted access boundary. Connector push tokens are separate from this UI access model.

## Inspect before updating

Before a rebuild, identify the container's **actual** data mount with `docker inspect`. Read the effective Compose configuration, including override files. A Compose override can silently select a different database on recreation even when the previous container used another directory. Never assume that a directory containing an `atlas.db` file is the current authoritative inventory.

Preserve installed add-ins, credentials, keys and snapshots. Rebuild does not require replacing data. Verify health, record count/IDs and representative rack placements after an update. Check that the effective mounted path still matches the pre-update path or a deliberate verified migration.

## Backups

Use two backup levels:

1. **Inventory export:** portable documented records for inspection/restore. It does not contain native add-in credentials or the Marketplace package registry/icon library.
2. **Protected host backup:** the persistent data directory, add-in registry/code/credentials, external connector key files, secret files and deployment configuration. Secrets may reside outside `/data` according to the installation.

Marketplace source indexes, reviewed data packages, installed icons and rollback metadata live in a separate table in the same SQLite database. Include the complete database in protected backups; inventory JSON exports do not include that table. Native connector package code and its previous version remain in the private add-ins directory, so protect that directory as well.

Use SQLite's online backup API while running, or stop the application before copying its database files. Do not rely on copying only an active database file if journal/WAL state can be involved. Store backups outside the live writable directory and test restoration in an isolated deployment.

When restoring an inventory through the UI or API, keep an export of the current inventory first. Whole-state API writes require the current revision. Host filesystem restoration and portable inventory import are different operations; neither should be performed blindly against a running production instance.

## Updates and rollback

Back up modified application files and keep a tagged previous Docker image before a functional update. Deploy the matching code, package manifests and frontend assets together. Regenerate binding declarations when shared frontend names change, and change asset versions when necessary to prevent stale browser code.

For rollback, restore the previous application/image while retaining the correct active data mount. If the data format changed, use the explicitly compatible migration/backup strategy for that change. Do not overwrite new user edits with an old database merely to roll back a visual change.

Update connector code through a repository review. Application image updates do not automatically update the copies of installed native add-ins. Confirm each instance's configuration still matches the new adapter version before a live run.

## Development validation

```sh
python -m unittest discover -s tests
node tests/test_frontend.cjs
node tests/test_device_images.cjs
node tests/test_modules.cjs
node tests/test_plugin_activation.cjs
```

Use a separate database for tests and browser CRUD checks. Tests may start an isolated temporary HTTP server; they must not point to live inventory. Do not repeat destructive UI scenarios on production. After frontend binding changes run `node scripts/build-plugin-bindings.cjs` and validate the assembled module contexts, not just raw files.

Operational verification should include a healthy container, the correct mount, expected inventory identity, a representative front/rear rack view and a connector status check appropriate to the change. Never print secret files as a diagnostic shortcut.

## Isolated connector runtime

The trusted `connector-runner` controller has no network interface and polls a private filesystem queue. It mounts the Docker socket and queue, but no inventory or stored add-in directory. Treat control of this service or Docker socket as host administration. Atlas mounts the inventory and queue but no socket. Workers receive only one job directory, mounted read-only, with that package and instance's credentials.

A worker runs as UID 1000 with no capabilities, no new privileges, a read-only root, 256 MiB memory, one CPU, 64 processes and bounded temporary storage. At most two jobs run concurrently; jobs time out after one hour. Disabling an instance cancels its worker and revokes its job token. No local subprocess fallback exists: imports require a recent healthy controller heartbeat and the worker image.

After a controller restart, workers belonging to its queue are removed and interrupted jobs fail explicitly. After an application restart, RAM-held job tokens expire. Completed jobs are removed from the queue. Check private queue ownership and available disk space if staging fails. Do not delete the queue while imports run. Keep it out of Git, general static file serving and unprotected backups.

The callback uses the private Docker network alias `atlas-connector-callback:8765`, independently of the UI port binding. If you change the network or alias, rerun setup and keep callback settings consistent. The setup script persists worker subnets so the request guard remains active when the controller stops. Avoid sharing that network with unrelated services.

Container limits follow [Docker run options](https://docs.docker.com/engine/containers/run/) and [resource constraints](https://docs.docker.com/engine/containers/resource_constraints/). This reduces access and resource exposure; it does not guarantee safe execution of arbitrary code. Review packages and upstream credential permissions before installation.

## Connector migration recovery

Private `data/addins/migrations/<id>/` bundles contain old credentials, code and registry records. Preserve directory permissions (0700) and file permissions (0600). Include these with the protected host backup. A journal in applying/rollback-applying phase is recovered on manager startup; do not edit it casually or remove its files mid-operation. Normal package rollback and restoring a legacy connector are separate actions.

The trusted application administration route `POST /api/v1/addins/migration/rollback` accepts the migration ID. The UI exposes it in a migrated instance's technical details. Do not restore an entire older inventory database merely to undo this installation migration: object IDs and the inventory data model do not change.

## Protected host backups and restore rehearsals

Open **Sources & settings → Backup & restore**. An inventory JSON export is portable documentation. It does not include the Marketplace database table, installed packages, connector credentials or private GitHub access.

**Create protected backup** writes an archive under `/data/backups` on the Atlas host. The archive contains an online SQLite snapshot and private `addins/` files, including package code, per-instance settings and credentials. Files are protected with owner-only permissions. Imports must finish before the snapshot is created. No secret-bearing archive is downloadable through the backup API.

Use **Review host backups → Validate** to check checksums, archive paths, SQLite integrity, inventory schema and module major-version compatibility. **Rehearse restore** extracts into a private temporary directory, validates the recovered inventory and removes the temporary directory afterwards. This does not replace the running inventory or start another collector.

An Atlas-data archive does **not** include deployment `.env` files, Compose overrides, the container image or external snapshot mounts. Keep a separate private host backup of those files and record the deployed image/version. Do not place credentials or recovery archives in Git repositories. The app has no access to the Docker socket or arbitrary host configuration paths.

For recovery, stop Atlas and its connector runner first. Work from the matching application source/runtime and run:

```sh
python3 scripts/recover-atlas.py /private/backups/atlas-data-YYYY-MM-DD-HHMMSS-xxxxxxxx.tar.gz --restore-to /private/recovery/atlas-data
```

The destination must not exist. The tool refuses to overwrite an installation. It restores the database and add-in data with private permissions; it prints counts, never credential values. After verification, point the deployment's `/data` mount at the recovered directory, restore its deployment configuration and start one Atlas/runner pair. Verify instance IDs, source IDs, schedules and a manual import before discarding the previous installation.

Keep the previous directory and image until recovery has been verified. Rehearsal validates data recovery; it does not certify connectivity to every upstream controller or restore third-party infrastructure.

The recovery tool is also included in the Atlas container image. With a private backup directory and an empty writable recovery parent, a data-only rehearsal can use the matching image without network access:

```sh
docker run --rm --network none --read-only --cap-drop ALL --security-opt no-new-privileges:true --tmpfs /tmp:size=768m -v /private/backups:/backups:ro -v /private/recovery:/recovery atlas-homelab-atlas python scripts/recover-atlas.py /backups/atlas-data-YYYY-MM-DD-HHMMSS-xxxxxxxx.tar.gz --restore-to /recovery/restored
```

Replace the example archive name and host paths. The recovery parent must be writable by Atlas UID 1000; `/recovery/restored` must not already exist. This starts the recovery command only, without Atlas web services or scheduled imports. It leaves the recovered data private for inspection before any deployment switch.
