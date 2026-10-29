# Known limitations — v0.1.0-alpha.1

- Early alpha: interfaces and data formats can change. Keep backups and test upgrades separately.
- No human login or general UI/API authorization layer. Deploy only within a trusted private access boundary.
- Linux Docker host validated. Docker Desktop, rootless Docker and additional CPU architectures need separate testing.
- Portainer has live import validation; SNMP has live read-only switch observations. Kubernetes and Proxmox remain fixture-tested; UniFi controller authentication needs live validation.
- Update tests cover the immediately preceding deployed runtime, not every historical or future version.
- Imported observations are not authoritative physical cabling or inferred application dependencies. Document and verify those relationships explicitly.
- Missing imported objects remain as history. IP allocations, cable endpoints and rack reservations are not automatically freed when an upstream object disappears.
- An inventory export excludes connector credentials and installed package state. Atlas-data backups exclude deployment configuration, images and external mounts.
- Manufacturer image redistribution permission is unresolved for the separate Ubiquiti catalog. It is omitted from the default Marketplace offering for this release; no such images are bundled with Atlas.
- This is a documentation application, not a monitoring or availability system.
