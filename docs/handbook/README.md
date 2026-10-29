# Atlas handbook

**Documentation baseline: 25 October 2026.** This handbook describes the implemented Atlas application and its extension contracts. UI labels and examples are English. Older review documents elsewhere in `docs/` record earlier milestones; use this handbook for current workflows.

Atlas documents a homelab's equipment, placement, addresses, cables, power, applications and dependencies. Manual inventory and connector imports share one data model. It is not a monitoring platform, switch configuration tool, DHCP server or hypervisor controller.

## Read by purpose

| Audience / task | Document |
| --- | --- |
| First setup and daily use | [User guide](user-guide.md) |
| Understanding record ownership and relationships | [Data model and architecture](architecture.md) |
| Automating reads and imports | [REST API reference](api-reference.md) |
| Installing or developing a connector | [Connector guide](connectors.md) |
| Creating and sharing hardware definitions | [Device catalog specification](device-catalogs.md) |
| Deployment, backup, updates and recovery | [Operations guide](operations.md) |
| Finding gaps and diagnosing problems | [Limitations and troubleshooting](troubleshooting.md) |

## Vocabulary

**Device:** a physical inventory instance, whether rack-mounted or elsewhere. **Model:** reusable manufacturer specifications from a catalog. **Accessory:** passive rack equipment such as a patch panel or shelf. **Application:** a VM, container, stack, service or Kubernetes object. **Interface:** a named network or power termination on an instance. **Connection:** a documented physical or logical relationship. **Connector instance:** one configured upstream source with its own stable source ID. **Add-in:** trusted collector code that can supply one or more instances. **Catalog source:** a GitHub model collection; it contains data, not executable connector code.

## Documentation policy

Document what the current code and tested workflows support. Mark fixture-only adapters and missing live validation explicitly. Never put credentials, real tokens or private upstream payloads in documentation examples. Update the handbook in the same change that alters a workflow, record contract or endpoint. Use [maintenance instructions](maintenance.md) before declaring documentation current.

The screenshots and technical reviews under the parent `docs/` directory provide supporting evidence, but historical test counts and screenshots are not promises about subsequent releases.

Open **Help** in the application for the built-in handbook reader. It serves only the bundled handbook chapters; audit evidence and private host files are not exposed.
