# Data model and architecture

[Handbook index](README.md)

## Shared inventory

Atlas uses a Python HTTP application, SQLite persistence and a browser UI built from plain JavaScript, CSS and SVG. Docker runs the application. There is one shared inventory store; modules are implementation boundaries, not separate databases.

| Collection | Main responsibility | Important relationships |
| --- | --- | --- |
| `racks` | Enclosure height, numbering, location and coordinates | Devices reference rack IDs |
| `devices` | Equipment and passive accessories | Interfaces, rack/unit, shelf, hardware snapshot |
| `services` | Applications and virtual workloads | Hosting parent and runtime/role |
| `networks` | Prefixes and VLAN documentation | Address assignments and plans |
| `links` | Physical and logical connections | Source/target IDs and optional terminations |
| `deviceCatalog` | Reusable model definitions | Namespaced catalog source/model IDs |
| `catalogSources` | Repository identity and availability | Independent refresh/enable/remove |

Additional compatibility fields and planning collections can appear in the full state. Treat the application validator and current exported state as authoritative; this table is a conceptual map, not an exhaustive JSON schema.

Record IDs are references. Renaming a display name must not change identity. Imported records use connector-scoped IDs so different sources do not collide. Catalog models are namespaced by source independently of connector IDs.

## Ownership and refresh

A model describes hardware; an instance describes a specific piece of equipment. Selecting a model stores a hardware specification snapshot. Refreshing a catalog changes reusable definitions, not already instantiated hardware fields. Removing a catalog source does not delete inventory.

Connector snapshots describe upstream facts. The merge preserves supported manual overrides and placement. Missing upstream records remain marked for review rather than being automatically deleted. Collectors must retain stable local IDs and must not publish an incomplete collection as a complete successful snapshot.

Whole-inventory writes use `_revision` for optimistic concurrency. A stale write receives 409 instead of silently replacing a newer state. Import handlers merge under the application lock and increment revision. SQLite backups should use SQLite's backup API or a stopped database, not a casual copy of an actively written file.

## Feature packages

`atlas_modules/<id>/plugin.json` owns a feature's dependencies, routes, frontend assets and binding declarations. Packages cover core, overview, hardware, applications, IPAM, connections, topology, catalogs, connectors and settings. Built-in features remain permanently available; the UI does not ask users to activate every feature.

Backend modules are loaded for their declared routes. The package registry validates route/page/asset ownership and dependency relationships. Frontend compatibility code runs in private package contexts. Shared declarations resolve through `AtlasPluginHost`; page registration and lifecycle use `AtlasModules`. This separation is not a sandbox for untrusted code.

After adding or renaming shared frontend functions, run `node scripts/build-plugin-bindings.cjs`. Deploy the changed package declarations as well as JavaScript. Otherwise code can work in an isolated script test while the actual module context cannot resolve the new helper. Node is a development dependency, not a requirement inside the deployed container.

## Two extension contracts

**Device catalogs** contain JSON and images. Importing them does not execute repository code.

**Connector add-ins** contain trusted collector code. Native add-ins execute bounded Python child processes with the application's permissions. External collectors can run in their own container/process and push source-scoped REST snapshots. These are distinct runtimes; neither implies that a full community marketplace or arbitrary frontend feature installation exists.

## Rendering

Rack equipment spans integer rack units; shelf drawings are thin surfaces with separately reserved clearance. ImageFrame metadata describes the visible region of an unchanged source canvas. SVG viewBox rendering preserves image proportions. Annotated technical figures can be excluded from rack elevations while remaining available as documentation.

Network topology and application dependency maps render documented relationships. Imported neighbor observations should be distinguished from confirmed manual cable paths. UI color and line style aid classification; they are not operational health indicators.
