# Device catalog specification

[Handbook index](README.md)

## Sources and refresh

Add one or more **public GitHub** repositories under Device catalogs. A root repository URL resolves to `main/catalog.json`; a GitHub JSON file link can select a different branch or folder. Model IDs are namespaced by source, so two catalogs may use the same local model ID.

Each source can be refreshed, enabled/disabled or removed independently. Refresh replaces that source's available model definitions. Existing instance hardware snapshots remain fixed. Disable/remove does not delete already instantiated equipment. Manufacturer imagery must belong to the same repository as the catalog JSON. Browser image display needs access to GitHub.

Private GitHub credentials currently apply to connector packages, not device catalogs. A catalog is limited to 500 records and 1 MB JSON. It is parsed as data; repository code is not executed.

## Minimal record

```json
{
  "version": 1,
  "devices": [{
    "id": "example-switch-24",
    "name": "Example 24-port switch",
    "manufacturer": "Example",
    "model": "EX-24",
    "kind": "Switch",
    "height": 1,
    "ports": 24,
    "widthMm": 440,
    "depthMm": 240,
    "heightMm": 44,
    "frontImage": "images/ex-24/front.png"
  }]
}
```

`id` and `name` must be nonempty; text fields are bounded. `manufacturer` and `model` may be empty text. Supported kinds include Server, NAS, Router, Switch, Access point, Patch panel, Cable manager, Rack shelf, UPS, PDU and Other. Heights are integers 0–60, with 0 permitted only for PDUs. Port counts are integers 0–96. Dimensions use separate positive finite millimetre values, not an ambiguous three-number string.

Optional interfaces describe name, type, connector, speed and LAG membership using the supported hardware schema. Interface names must be unique and relationships valid. IP addresses belong to instances and are cleared from imported model definitions. Optional shelf dimensions/space and notes are validated by the importer.

Images may be SVG, PNG, JPEG or WebP repository paths or raw GitHub image URLs from the same repository. Supply a real corresponding rear view or leave it absent; do not relabel a side or dismantled front view as the rear.

## Visible image frames

A padded manufacturer PNG can have a large square canvas around a thin chassis. Supply `frontImageFrame` and/or `rearImageFrame` to describe the visible region without changing source pixels:

```json
{
  "x": 100,
  "y": 250,
  "width": 800,
  "height": 75,
  "canvasWidth": 1000,
  "canvasHeight": 1000,
  "rackSuitable": true
}
```

These are coordinates in the original image canvas. Width/height/canvas dimensions must be positive, coordinates nonnegative, all values finite and at most 20000. The region must fit inside the canvas and requires its corresponding image. `rackSuitable` is a boolean and defaults to true. Atlas frames that region proportionally through an SVG viewBox; it does not stretch the device to match the canvas.

Mark annotated quick-start illustrations `rackSuitable: false`. They remain documentation images; rack elevations use a schematic rather than placing callout numbers on the hardware face. A schematic must not be presented as a manufacturer photo. Dimensions and visual framing are different: neither can fix incorrect rack height or a wrong front/rear assignment.

## Publishing a library

Keep stable model IDs, empty instance IPs, explicit dimensions and source attribution. Verify connector/media types and distinguish network, management, console and power sockets. Shared RJ45/SFP combo sockets are not independent logical ports. Regional power ratings must be labelled.

Record official source URLs, review dates and image checksums. Do not assign a blanket software license to third-party manufacturer photos. Document your scope and missing views; do not claim every historical model from a partial manufacturer listing.

The [Ubiquiti library](https://github.com/42bios/atlas-device-library-ubiquiti) currently contains 74 reviewed native full-width 19-inch models. Desktop adapters and vertical 0U equipment outside that scope are excluded. The older USG-Pro-4 has no supplied rear asset. See the [library README and provenance](https://github.com/42bios/atlas-device-library-ubiquiti#pictures-and-provenance) for verification details and third-party image attribution.

## Alpha distribution and artwork

The separate Ubiquiti picture library is omitted from the default Marketplace index while manufacturer image redistribution permission is unresolved. Existing imported models and device snapshots are retained. Atlas does not bundle those photographs or grant rights to third-party artwork. Prefer catalogs with explicit asset licensing; publishers must document the permissions for distributed images.
