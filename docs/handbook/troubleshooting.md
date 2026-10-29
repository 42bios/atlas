# Limitations and troubleshooting

[Handbook index](README.md)

## Current boundaries

| Topic | Implemented | Boundary |
| --- | --- | --- |
| Inventory | Manual records and source imports | Not continuous health/metrics monitoring |
| IPAM | Prefixes, VLAN facts, assignments and planning | Does not configure DHCP or prove an IP is unused |
| Connections | Explicit terminations and patch traces | Does not infer a complete wall/patch route from a neighbor |
| Racks | Placement, front/rear, zoom, shelves and images | No certified mechanical, weight or airflow model |
| Applications | VM/container/stack types and dependencies | Some relationships require manual documentation |
| Kubernetes / Proxmox | Adapter implementation and fixture tests | No configured local live environment for validation |
| UniFi | Implemented adapter and tests | Live collection requires verified credentials/configuration |
| Add-ins | Reviewed GitHub packages and scoped source IDs | Docker workers isolate mounted files; network access and upstream credential trust remain |
| Catalogs | Multiple public repositories | No private image/catalog credential support |
| Marketplace | Manual repository integration | No central community marketplace or automatic updates |
| User access | Trusted deployment model | No general user/account or role-based UI access system |

## Common problems

**Image is tiny:** check whether the source has a padded canvas and whether a valid ImageFrame is present in the imported model. Refresh the catalog after updating metadata. Existing instance image URLs can resolve frame metadata from the current catalog. Do not solve this by stretching a square image into a rack face.

**Numbers/arrows appear on a device:** this is probably an annotated technical figure. Mark the view unsuitable for rack use, or provide a real clean manufacturer view. Front and rear gallery ordering is not consistent across models.

**Frontend works in raw-script tests but fails in the app:** regenerate package bindings and deploy the package declarations. Check dependency ownership and current asset versions. Inspect browser errors and validate the assembled module host.

**Devices disappear after a container recreation:** first inspect the data mount and effective Compose overrides. Stop making inventory changes until the authoritative database is identified. A different database with sample records is not evidence that records were deleted from the original database.

**409 while saving:** another session/import changed inventory. Reload and reapply the intended change. Do not retry a stale whole-state payload without reading the current revision.

**Connector installed but no inventory:** package installation is not a successful collection. Check instance enablement, required credentials, upstream address/TLS, manual-run status and the time of the last successful report. A previous report does not prove the current configuration works.

**Too many missing objects after an import:** verify that the collector completed all required upstream queries. Partial/authentication failures should report failure, not publish an empty complete snapshot. Missing objects are retained for review; do not delete them before resolving the collection issue.

**SNMP switch ports/VLANs absent:** verify target scope, reachability, SNMP version/community or v3 credentials, supported MIBs and access permissions. Different switch families expose different data. Never infer a physical patch-panel path solely from LLDP.

**Catalog refresh shows an older revision:** public raw GitHub content can be cached briefly. Verify the committed JSON and retry after the published content updates. Refresh must retain the original catalog source identity; adding a second source for a commit is not the same as refreshing it.

**New device has no free rack position:** check its fixed model height, shelf reservations, existing equipment and rack numbering/bounds. A predefined model's height cannot be edited to force a fit.

## Open improvements

Richer community catalog tooling, broader upstream-version validation and confirmed live Kubernetes/Proxmox/UniFi tests remain separate work. Treat historical roadmap documents as ideas until a feature is implemented and verified. Preserve the documentation-first scope when considering monitoring-style additions.

**LLDP tables contain data but no neighbors appear on ports:** an agent may advertise `Port N` in LLDP and `S/P` as ifName. The SNMP connector uses unique exact identities and explicit slot/port descriptions, not the local LLDP index as ifIndex. Check unassigned LLDP observations and data coverage in device details. Missing MIB support, empty tables and ambiguous identities are distinct conditions.

## Marketplace

If Browse is empty, open Sources and refresh an enabled public catalog. Check the repository contains schemaVersion 1 catalog.json with full commit pins. A source being listed does not install its extensions. GitHub rate limits or invalid files preserve the previous cached index. Retry explicitly after resolving the problem.

If a connector shows Installed but no upstream inventory exists, create a connector instance in Sources & settings and run Test & import. Existing bundled connectors retain their configuration; use Migrate existing connector explicitly to adopt their credentials and source IDs. Normal repository installation does not migrate them. Marketplace currently installs connector add-ons, device catalogs and icon packs, not arbitrary frontend feature code.

If an icon is absent, check the pack is installed and the application's explicit selection still exists. Choose Automatic matching or another installed icon. Changes to a source index do not automatically update a package. Rollback requires a previous Marketplace-installed version and compatible connector configuration.
