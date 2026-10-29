# Connector operation and development

[Handbook index](README.md)

## Marketplace

Open **Marketplace** from the Manage menu. **All extensions** lists connector add-ons, device catalogs and icon packs as compact repository rows. Filter by type/status, group by status or type, and sort by name, GitHub stars or activity. Update, installed and available groups can be collapsed. **Installed** shows installed packages, including recognized existing connector/catalog installations. **Sources** manages public GitHub catalog repositories. The initial source is [42bios/atlas-marketplace](https://github.com/42bios/atlas-marketplace).

A source supplies `catalog.json` with `schemaVersion: 1` and up to 200 packages. Entries declare a type, unique ID, name, description, repository, full Git commit, displayed version/license, documentation and declared access. Packages are deduplicated by type/repository across sources. Disabling/removing a source retains installed packages. A failed refresh retains the last successful index and displays the error. No source code is executed during discovery.

Click a repository row to open its own detail page, including the pinned README, version/author/source chips, release links and package actions. Detail URLs can be bookmarked. Documentation loads as safe Markdown: raw HTML and unsafe links are not executed. Public GitHub stars/activity and documentation are cached for six hours; metadata failures retain the catalog and display unknown values. Download counts are not inferred.

Choose **Download & review**, inspect the pinned package and type the repository identity before installation. A connector still requires a configured instance in **Sources & settings**; installation alone does not connect or scan anything. A hardware catalog supplies reusable models; it does not create physical device instances. An icon pack supplies static images and has no credentials or execution hooks. Installed icons can match application names/images/roles automatically or be explicitly selected under **Edit application → Application icon**. Icons appear in application cards and dependency/application maps. A removed icon selection falls back to the default graphic.

**Check for updates** refreshes source metadata only. Package updates remain explicit and commit-pinned. Details link to repository documentation and release notes and highlight changed declared access. Previous versions installed through Marketplace support rollback when a compatible previous package is available; connector jobs must finish and configuration must remain compatible. Source IDs, credentials and imported inventory are retained during updates/rollback. Legacy bundled connector instances are recognized. Choose **Migrate existing connector** on the matching official package to switch them explicitly without creating another instance.

Uninstalling a connector removes its instances and credentials; imported inventory remains. Removing a hardware catalog removes available model definitions, while instantiated devices retain their copied specifications. Removing an icon pack retains applications. Direct repository installations remain available through the existing installer; private GitHub access applies there, while Marketplace sources/data packages are public.

See the marketplace repository's contribution guide for the public index format. [Homelab essentials](https://github.com/42bios/atlas-icon-pack-homelab) documents the icon manifest: up to 200 static PNG/JPEG/WebP images, 150 KB each, 4 MB total, SHA-256 checksums, maximum dimensions 1024 × 1024. Atlas normalizes installed icons to local 128px PNGs. SVG/HTML and executable install hooks are rejected. This restriction applies to icon packs; existing device artwork support is unchanged.

## Package versus instance

Install one add-in package, then create one or more instances with distinct source IDs and upstream configurations. Installing code does not automatically authorize a network scan or establish a working connection. Start with a manual run and inspect imported records before enabling a schedule.

Use **Sources & settings → Developer tools → Add GitHub repository**. Atlas resolves the selected ref to a commit, downloads the manifest and declared files, verifies checksums and shows a review. Confirm the exact repository identity when installing trusted code. Review updates explicitly; there is no automatic marketplace rollout.

Installed add-ins remain visible without adding another repository. Uninstalled planned or bundled packages are not automatically advertised as marketplace entries. Removing an instance or uninstalling code retains imported inventory. Installed code in persistent storage is not automatically replaced by an application image update.

## Current repositories

| Adapter | Repository | Scope and verification limits |
| --- | --- | --- |
| Portainer | [atlas-plugin-portainer](https://github.com/42bios/atlas-plugin-portainer) | Docker environments, stacks, containers, published ports and startup ordering; live imports have been verified |
| SNMP discovery | [atlas-plugin-snmp-discovery](https://github.com/42bios/atlas-plugin-snmp-discovery) | Scoped IPv4 discovery, equipment/interface facts and neighbor observations; results depend on the switch's available MIBs |
| Kubernetes | [atlas-plugin-kubernetes](https://github.com/42bios/atlas-plugin-kubernetes) | Cluster-specific workloads and relationships; fixture validation, no local live cluster configured |
| UniFi | [atlas-plugin-unifi](https://github.com/42bios/atlas-plugin-unifi) | UniFi network inventory; adapter tests pass, live authentication/import still requires configured controller credentials |
| Proxmox | [atlas-plugin-proxmox](https://github.com/42bios/atlas-plugin-proxmox) | Hypervisor VM/LXC inventory; fixture validation, no local live Proxmox installation |

Read each repository README for its exact version, credentials, upstream API support and limitations. Do not imply that a published repository has been tested against every upstream version.

## Discovery scope and observations

SNMP autodiscovery still needs an approved target scope: explicit hosts or IPv4 prefixes, currently bounded to 1024 addresses. Knowing a subnet replaces the need to list every switch IP; it does not make the scan boundary unnecessary. Use the community/version or SNMPv3 configuration required by the targets.

Interface capabilities, VLAN information and LLDP-style neighbors depend on supported MIBs and permissions. A neighbor observation is evidence of adjacency, not proof of the physical patch-panel route. Document wall outlets and permanent patch paths separately. Discovery results are inventory facts from a collection run, not continuous port utilization monitoring.

## Credentials and TLS

Put secrets in the credential channel or the documented secret files. Do not use ordinary configuration fields for passwords. Native instance credentials live under the private add-ins directory; public API status excludes their contents. Blank credential entry can retain an existing credential where the editor supports this.

For private connector repositories, configure **GitHub access** with a dedicated read-only token and an explicit owner/repository allowlist. Authenticated downloads use commit-pinned GitHub API requests. Removing stored access removes Atlas's copy; it does not revoke the token at GitHub. Private connector access does not make private image catalogs supported.

Upstream TLS should use a trusted CA or an explicitly verified supported certificate fingerprint. A fingerprint mismatch must abort before credentials are sent. Do not solve a collector login failure by silently disabling verification.

## Native package manifest

`atlas-addin.json` uses `schemaVersion: 1`, `connectorApi: 1`, an ID/name/version, Python runtime, entrypoint, configuration fields and declared files with SHA-256 checksums. Supported configuration field types are text, URL and number. Secrets use a separate credential file.

Limits: up to 30 files, 1 MB each, 4 MB total; allowed package extensions `.py`, `.json`, `.md`, `.txt`; relative paths without traversal. Manifest size is capped at 60 KB and configuration at 20 fields. No pip install hooks, arbitrary shell entrypoints or downloaded frontend JavaScript are provided by this runtime.

The runner supplies `ATLAS_URL`, `CONNECTOR_ID`, `ATLAS_TOKEN_FILE`, `ADDIN_ID`, `ADDIN_CONFIG_FILE`, `ADDIN_CREDENTIAL_FILE` and `RUN_ONCE=true`. Exit zero only after a successful collection and import. Updates must remain compatible with existing instance configuration and cannot replace code while a job runs.

Repository and bundled collectors execute in separate Docker workers, never in the Atlas application process. Each run stages the reviewed package, its own configuration and credential files, and a fresh source-scoped token. No inventory database, sibling credentials, GitHub access token or Docker socket is mounted. Declared repository files are checksum-verified again when staging. Symlink credential paths are rejected. Credentials are copied into the worker's writable temporary directory when needed by existing adapters.

Job tokens authorize only snapshot/status writes for their active source and expire when the job ends or the instance is disabled. Worker-network requests and requests bearing job tokens are rejected for general application routes. Existing external collector key configuration remains separate. Instance and source IDs do not change when moving to this runtime. Temporary worker containers are excluded from Portainer imports using their verified Docker IDs.

Checksums prove integrity, not author trust. Workers retain network access to collect upstream data; they could misuse their own credentials or transmit data. Direct worker traffic and Docker gateway callbacks are blocked from general API routes, but an intermediary/reverse proxy can obscure origins. This runtime does not add human authentication or complete network egress isolation. Install reviewed code and use upstream read-only permissions. See [Operations](operations.md#isolated-connector-runtime) for setup and limits.

## External snapshot contract

Fetch `GET /api/v1/connector-contract` for supported runtime kinds and roles. A snapshot has `schemaVersion: 1`, `connector` and arrays `devices`, `services`, `networks`, `links`. Use stable connector-local IDs. Authenticate with a Bearer token scoped to that connector ID through the configured keys file. Never publish upstream credentials, logs, arbitrary environment variables or unrelated private labels as inventory.

Report collection failures honestly through the status endpoint. Do not send an empty successful snapshot after an authentication or partial-query failure. Keep a single scheduled collector for a source ID; adopting an existing external collector into a native instance requires stopping the old worker first.

See the [API reference](api-reference.md), the package contract above and the installed repository's pinned README. Historical deployment notes are not part of the release handbook.

## Setup and troubleshooting in the application

**Connected systems** lists configured instances first. Installed package management is available in its collapsed **Installed extension packages** section; **Developer tools** contains direct repository and private GitHub access controls. **Manual imports** and **Local snapshot files** refer to snapshot data, not installed code; an empty file directory does not imply that no add-ins are installed. Technical package/source IDs are available in a collapsed detail section.

Credentials start masked, have an explicit reveal control and use an adapter-specific label. Portainer accepts an API access token created in the Portainer user's account. Other adapters use their documented token or JSON format; the configuration dialog links to the installed revision's README. Leave a saved credential blank to retain it. TLS trust settings are under Advanced.

New instances show **Configured · not tested**. **Test & import** performs a real collection and merges the returned inventory; it is not a dry run. Use a manual first import and review the results before configuring a schedule. An existing instance offers **Import now**.

Failed workers return a fixed, non-sensitive explanation where evidence permits: DNS resolution, TLS trust, request rejection/credentials or permissions, timeout, or connection refusal. Unknown failures remain explicit generic failures. The controller retains at most 16 KiB of output in the private job result for classification and never returns raw worker output or upstream bodies. A collector that suppresses exception information may only support the generic message. Connection failures do not replace the existing inventory with an empty snapshot.

## Compatibility checks and SNMP coverage

The 1.0.1 SNMP, Kubernetes and Proxmox packages include broader compatibility and failure-case tests. Kubernetes and Proxmox remain fixture-validated. Three live switches were queried read-only; LLDP interface matching recovered 17 neighbor observations using explicit local port descriptions.

Device details distinguish unavailable SNMP tables, tables returning no entries and LLDP observations that cannot be assigned to a unique interface. Empty tables do not establish that no neighbors exist. The collector never fabricates physical cable routes. Zero responding devices or missing required interface tables abort collection and preserve previous inventory. A partial validation must not be submitted as a full-source snapshot because full snapshots mark unseen source records missing.

## Migrating legacy bundled connector instances

Portainer, SNMP and Kubernetes instances created with old bundled packages can be migrated to their matching official repositories. Migration is explicit: open the package in Marketplace, choose **Migrate existing connector**, review the package and affected instances, then confirm the exact repository name. A normal repository install does not migrate instances. New installation of old bundled add-ins through the administration API is blocked.

Migration retains instance IDs, source IDs, names, enabled state and schedules. Portainer retains its upstream URL, certificate fingerprint and token. SNMP converts the target list to the repository's text field and retains the SNMP version/credential. Kubernetes combines its token and saved CA certificate into the repository's private credential JSON. No secret is returned in the review or status API. Repository code runs in the same isolated worker runtime.

All affected imports must finish first. Configurations must satisfy the repository manifest; mismatching repositories, missing credentials, changed files and conflicting target versions are rejected. A protected migration journal and copies of old instance files/package are stored under the private add-ins directory. An interrupted conversion is restored on the next manager startup before schedules run. Old code is removed from the active package directory only after a committed migration.

After migration, run **Import now** and confirm the import succeeds with the same source. Under the instance's **Advanced & recovery**, **Restore legacy connector** can restore the protected pre-migration configuration. Restoration is blocked while an import runs or if instance settings/configuration/credentials changed after migration. It restores only migrated instances and preserves unrelated instances. Recovery may retain the repository package when it could be used by other instances. Recovery copies contain credentials and belong in protected host backups, never public repositories or screenshots.

UniFi and Proxmox are repository-only adapters and require no bundled-instance conversion. Missing live Kubernetes/Proxmox/UniFi validation remains a separate limitation.


## Setup progress and lifecycle

Marketplace shows whether an installed connector needs setup, has configured systems, has imported inventory or needs attention after a failed import. Open its primary **Configure connector** action to edit the matching instance, choose among multiple instances or add its first system. **Manage systems & import** opens the connected-systems workflow. Use **Test & import** before selecting a schedule; opening a configuration form never runs a collector.

Requests have bounded waiting and recoverable error messages. If a write request times out, refresh status before retrying: a server-side operation may have completed after the browser stopped waiting.

Current application and connection views hide objects marked missing by an import. **Include missing imports** exposes retained records, source and last-seen information. The filter is shared across inventory, maps and connection views and is included in shareable routes. It does not delete objects or release documented IP assignments, rack placement reservations or physical cable terminations. A missing import is not proof that equipment was removed or an address is available.

## Code licenses

Atlas and its five official connector repositories use GPL-3.0-only. Each new connector license release includes LICENSE.txt among its checksum-verified package files. The Marketplace index and original icon pack retain their separate licenses; manufacturer data and images are not relicensed by the application.
