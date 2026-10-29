# Add equipment to Atlas

## Choose a model or create a custom device

1. Open **Device catalogs**. If there are no models, open **Marketplace**, select a device catalog, review its repository and install it.
2. Search by model or manufacturer. Use the **Type**, **Rack height** and **Repository** filters to narrow the list.
3. Open a model to inspect its front and rear views, dimensions and port count. A missing view means the publisher has not supplied it.
4. Select **Add this device** or **Add this accessory**. Enter the instance name, hostname and optional addresses. Manufacturer, model, height and port specifications remain fixed to the selected model.
5. Choose **Unassigned** for desktop or standalone equipment. Choose a rack for rack-mounted hardware. Only positions that fit its height are offered.
6. Expand **Interfaces & addresses** to record extra IPs, VLANs or a LAG. Use **Save & connect** when you want to document the next cable.

You can also open **Devices → Add device**, search for a model with a preview, or choose **Continue with custom device** and enter your own specifications. A custom device can have its own photo and separate front and rear views.

## Place equipment in a rack

Open **Racks** and select the rack. Clicking an empty unit opens creation at that position. Front and rear views share physical occupancy. Unlock the placement padlock only while arranging equipment; zooming and scrolling do not move devices.

A PDU is explicitly added equipment. Choose its front/rear placement and 0U, 1U or 2U mounting. Patch panels, shelves and cable managers appear under **Rack accessories**.

## Inspect an existing device

Select a device to open its scrollable detail panel. Use **Summary**, **Interfaces**, **Connections**, **Applications** and **History**. The History section records the import source, last-seen date and whether the object is missing from the latest snapshot. Escape closes device details and returns focus to the inventory.

## Update a catalog

Use **Marketplace → Check for updates** for catalog packages. Direct repository sources can also be managed under **Device catalogs → Repository sources**. Updates change available model definitions; instantiated devices keep their hardware snapshots and placement.

## Publish your own models

The [catalog specification](device-catalogs.md) describes repository format, image framing and publisher responsibilities. You do not need to understand that format to use an installed catalog.
