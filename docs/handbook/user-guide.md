# User guide

[Handbook index](README.md)

## Start with your actual inventory

1. Open **Sources & settings** and export the current inventory before substantial changes.
2. Check whether you are looking at sample data. Use **Start my inventory** on Overview to replace fictional sample records; export a sample backup if wanted and type `START` in the in-app confirmation. Afterward choose **Create rack**, **Add first device** or **Connect a system**. Before connecting live sources, do not treat sample devices as discovered hardware.
3. Create a rack if you have one. Give it a name, location, height and numbering direction. Optional latitude and longitude describe its physical location.
4. Add a device catalog, or create a custom device. Rack placement is optional for equipment such as desktops, access points and phones.
5. Add interfaces and addresses, then document cables and application hosting.
6. Add connector instances when the manual structure is clear. Review the first imported inventory before scheduling repeated collection.

## Navigation

| Section | Purpose |
| --- | --- |
| Overview | Inventory summaries and entry points |
| Racks | Physical placement, front/rear elevations and shelves |
| Devices | Equipment details, search and combined filters |
| Applications | Hosts, VMs, containers, stacks and dependency maps |
| Topology | Network, power, logical, VPN and location views |
| IP & networks | Prefixes, VLANs, assignments and planning |
| Connections | Cable endpoints, patch paths and relationships |
| Device catalogs | Repository sources and reusable hardware models |
| Sources & settings | Connector add-ins, imports and backup/restore |

Use workspace search to find an object, address or rack. Detail panels provide relevant links to its rack, addresses, connections, topology or hosted applications. URLs preserve important selection context. A host can have nested children, so navigating into a host includes its descendants.

## Devices and models

A **predefined model** fixes manufacturer, model, height, port count and supplied dimensions. Enter the instance name, hostname, rack position, IPs, serial number, asset tag and optional purchase date. Choose custom hardware when those specifications must be editable. Do not change the catalog model to describe a particular hostname or address.

Use **Save & connect** to continue from creation into cable documentation when a compatible second endpoint exists. For a PDU it selects **Powered by**, with the PDU supplying power on B. Otherwise save the first device and add another endpoint before documenting a cable. Interfaces can carry multiple IPv4 or IPv6 addresses. A LAG is a logical interface with physical members on the same device; document the member interfaces and cables separately. Interface speed describes recorded capability or imported facts, not a continuous live measurement.

Combine type, location and rack filters with search. Patch panels, shelves and cable managers belong to **Rack accessories**, while PDUs remain devices. The two categories share internal record storage so connections and older exports retain stable IDs.

## Racks, shelves and power

Front, rear and side-by-side views show the same inventory. Zoom enlarges the full elevation inside a scrollable viewport. Use Top or Bottom to navigate. Positions start locked after reload; the small padlock toggles dragging. Selecting equipment remains possible while locked.

An empty U position can start device creation. Available positions and suggestions depend on height, rack bounds and occupied space. Dragging snaps to rack units; a move still requires a valid free placement. Zoom and side-by-side preferences are stored in this browser.

A shelf is rendered as a thin bottom surface while its configured total space reserves clearance for the equipment above it. Add shelf devices individually; they keep their own identity, interfaces and connections. Width percentages are a visual layout aid; physical dimensions and usable shelf dimensions provide additional fit validation. They do not certify shelf load capacity, airflow or cable clearance. Deleting a shelf leaves its contents unassigned rather than deleting the devices.

Add a PDU explicitly. Choose 0U side mounting or a rack height and front/rear placement. A new rack does not create a PDU. Document power by linking a consumer to a particular PDU outlet; occupied physical outlets cannot be assigned twice.

Repository images may provide visible image bounds. Atlas uses those bounds to display the chassis proportionally rather than shrinking the entire padded canvas. Annotated legacy figures marked unsuitable for rack use receive a schematic rack face; the original figure can remain visible in details. A schematic is not a photographic or verified mechanical drawing.

## IP address management

Create a prefix and optionally record its VLAN. Open the network to review assigned, reserved, planned and free inventory addresses. These counts reflect documented inventory, not a scan of currently responding hosts.

**Assigned** means an address is attached to a device/interface. **Reserved** holds it without an active assignment. **Planned** records future intent, such as a hostname, target date and notes. Both reservations and plans block duplicate allocation and next-address suggestions. Converting a plan to an assignment preserves other addresses. If the workflow creates an interface for this purpose, it uses a virtual `ipam0` rather than inventing a physical connector.

The graphical address grid is IPv4 and paginated. IPv6 assignments and next-address suggestions are supported without an enormous IPv6 grid. A free suggestion means unallocated in Atlas; it does not establish that an address is unused on the network. Atlas does not configure DHCP, routing or switch VLANs.

## Connections

Start with the relationship category, then endpoint A and endpoint B, then their terminations. **Network** and **Powered by** use physical port/outlet selectors. Logical application relationships and VPNs do not reserve cable sockets.

Copper, fiber, DAC and AOC are distinct cable choices. Record speed, connector and fiber information where applicable. A DAC is an electrical direct-attach assembly; an AOC is an active optical assembly. A drawing does not verify transceiver or switch compatibility.

Patch panels have separate `front:PORT` and `rear:PORT` terminations. Connect a switch to the panel front and document the permanent run at the rear; continue to the outlet or remote endpoint. Trace follows the paired faces and recorded cable segments. It stops at missing documentation and prevents cycles. It does not discover hidden physical patching automatically.

Wi-Fi connects a client to an access point or wireless router, with optional SSID, band and BSSID. Multiple clients can share an AP without consuming a wired port. A client need not be in a rack. VPN records document protocol and routes; they do not create tunnels.

## Applications and topology

Choose the correct runtime type independently of its role: for example a Container with role Reverse proxy, or a Virtual machine hosting containers. **Runs on** establishes hosting; a Stack groups application members through the same hierarchy. Kubernetes objects retain their own kinds and parent relationships.

A host or stack opens its descendants. An individual application focuses the dependency map. Distinguish **Requires**, **Routes to**, **Uses storage** and **Starts after**. Compose startup ordering is not proof of a runtime dependency. Document missing relationships manually rather than assuming discovery can infer them all.

Use the List alternative and relationship list when a graph is too dense. Topology presents recorded physical and logical relationships; optional coordinates support a location map. OpenStreetMap content loads when requested and needs external network access.

## Efficient interface editing

Interface rows show a compact name/type/address summary. Open **Edit** on a row for its addresses, connector, speed and VLAN settings. **Find interface** filters the rows without removing their values from the draft. Select at least two Ethernet/fiber ports, enter a unique **New LAG name**, and choose **Create LAG from selected ports**. Put addresses on the LAG interface where appropriate and document member-port cables independently. Existing imported observations are retained when editing.

The inventory distinguishes **Primary IP** from interface addresses. An interface address does not silently become the primary IP. The device table and global search show the relevant interface addresses; the IP view lists all assignments.

## Choosing a device model without losing your draft

An empty model pool does not prevent creating a custom device. You can import a public catalog repository inside the device editor; names, hostnames and other instance fields remain in the draft. Selecting **Add this device** in a catalog opens the editor with that model already selected. Use **Change model / use custom device** to reopen the selector. Repository manufacturer, model, dimensions, height and hardware port counts remain fixed.

## Reading the maps

Dependency maps remove empty lanes and retain a readable minimum scale when fitting. A small screen may require horizontal panning instead of shrinking text indefinitely. Hosting context is shown separately unless hosting links are enabled. Empty application inventories offer creation/import actions; empty filtered results suggest changing filters. Workload types are grouped into common workloads and Kubernetes resources. Role describes purpose; Group is a display category. Runs on describes hosting/stack membership. Connections describe application dependencies.

Topology reports how many unconnected objects are hidden by the current view and filters. **Show** includes them. Power distribution devices belong to the Power view unless a network connection is explicitly documented.

Use **Help** in the top bar for the current workflow's handbook chapter.

## Appearance

Open **Appearance** in the top-right toolbar beside Help and choose **Light**, **Dark** or **Auto**. Auto is the default and follows the operating system's preferred color scheme, including changes while Atlas remains open. An explicit Light/Dark choice takes priority over the system setting.

The preference is saved for this browser and Atlas origin, survives reloads and synchronizes with other open tabs. It is not part of inventory exports and does not change another browser's setting. The theme is applied before styles load to reduce startup flashes. The handbook follows the same preference. Device pictures and physical rack hardware are not color-inverted.


## Working with current inventory and history

Use **Include missing imports** to switch between current source objects and retained import history. Historical records show source and last-seen details. They remain available for manual annotations and reappearing source identities; Atlas does not delete them when they are hidden. IP allocations and physical placement reservations are not automatically released.

Device details open in an independent panel. Its sections separate Summary, Interfaces, Connections, Applications and History. Escape closes the panel and returns to the inventory row. Creating a device from the global list starts with **Unassigned** placement; opening creation from a rack retains that rack and its free-position recommendations.

Application scopes can be searched by host or stack and are grouped by execution hosts versus workload groups. Recent scopes are saved for this browser. Map counts distinguish top-level items from nested objects. An empty dependency map explains when the source supplied no relationships and offers manual documentation without inventing dependencies.

In Topology, **Discovered neighbors** keeps the mode navigation. LLDP reports are grouped by device pair and every underlying observation remains in the text list. **Fit all** fits the full diagram. **Document cable…** opens an editable proposal; verify both ports and any passive path before saving.

See [Add equipment](catalog-guide.md) for model selection and [Operations](operations.md) for protected host backups and restore rehearsals.
