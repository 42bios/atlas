# Third-party notices and asset boundaries

Atlas code is GPL-3.0-only. This does not change the licenses of independent dependencies, Marketplace metadata, icon packs, manufacturer imagery or trademarks.

## Runtime dependencies

The Docker build uses Python 3.13 on Alpine Linux and Pillow 11.3.0. The runner images additionally install Docker CLI and Net-SNMP tools. Their distributions retain their respective upstream license/notice files. Consult [Python](https://docs.python.org/3/license.html), [Pillow](https://github.com/python-pillow/Pillow/blob/11.3.0/LICENSE), [Alpine packages](https://pkgs.alpinelinux.org/), [Docker CLI](https://github.com/docker/cli/blob/master/LICENSE) and [Net-SNMP](https://www.net-snmp.org/about/license.html). The Atlas source release references these dependencies; it does not copy their source trees into this repository.

## Marketplace repositories

The community index and original Homelab essentials icon pack remain independently MIT-licensed. Connector releases each carry GPL-3.0-only license text. A Marketplace listing does not confer ownership of third-party data or assets.

## Device artwork and trademarks

Atlas does not bundle manufacturer photographs or Visio libraries. Users can attach their own device images and import separately maintained catalogs, subject to the permissions for those assets. The Ubiquiti picture catalog is omitted from the default index pending redistribution permission. Source attribution/checksums alone are not a permission grant. Existing local catalog data is not deleted by this change.

Product names and trademarks identify compatible systems; no endorsement by their owners is implied. The bundled overview screenshot contains fictional sample inventory. The favicon and schematic patch-panel SVG are part of Atlas's own source assets.
