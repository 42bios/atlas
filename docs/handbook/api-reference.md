# REST API reference

[Handbook index](README.md)

All paths are relative to the Atlas base URL. JSON writes use `Content-Type: application/json` unless an endpoint explicitly accepts raw bytes. This is the implemented route set, not a promise of a complete per-object CRUD API or an OpenAPI specification.

## Access model

The UI and general inventory APIs currently use trusted application access without an account/login system. Several administration writes reject an explicit browser Origin that does not match the application's Host. Origin validation is not user authentication.

The versioned connector snapshot/status writes require `Authorization: Bearer TOKEN`, scoped to the body’s `connector` ID. Tokens can come from the configured external keys file or a native add-in instance. A connector token is not a general administrator API key. Responses and documentation must not expose credentials.

## Declared routes

Generated from `atlas_modules/*/plugin.json` by `python scripts/build-api-docs.py`. Route declarations are checked against registered backend implementations. The table lists application routes; static assets and legacy static aliases are outside it.

<!-- BEGIN GENERATED ROUTES -->
| Method | Path | Owner | Access model |
| --- | --- | --- | --- |
| POST | `/api/catalog/import` | catalogs | Trusted application access |
| GET | `/api/connector-schema` | connectors | Trusted application access |
| GET | `/api/connectors` | connectors | Trusted application access |
| POST | `/api/import` | connectors | Trusted application access |
| GET | `/api/state` | settings | Trusted application access |
| PUT | `/api/state` | settings | Trusted application access |
| POST | `/api/stencils/import-vssx` | hardware | Trusted application access |
| POST | `/api/sync` | connectors | Trusted application access |
| GET | `/api/v1/addins` | connectors | Trusted application access |
| POST | `/api/v1/addins/action` | connectors | Trusted application access |
| POST | `/api/v1/addins/configure` | connectors | Trusted application access |
| POST | `/api/v1/addins/migration/rollback` | connectors | Trusted application access |
| POST | `/api/v1/addins/repository/access` | connectors | Trusted application access |
| POST | `/api/v1/addins/repository/install` | connectors | Trusted application access |
| POST | `/api/v1/addins/repository/preview` | connectors | Trusted application access |
| GET | `/api/v1/applications` | applications | Trusted application access |
| GET | `/api/v1/backups` | settings | Trusted application access |
| POST | `/api/v1/backups` | settings | Trusted application access |
| GET | `/api/v1/catalogs` | catalogs | Trusted application access |
| GET | `/api/v1/connections` | connections | Trusted application access |
| GET | `/api/v1/connector-contract` | connectors | Trusted application access |
| GET | `/api/v1/connector-packages` | connectors | Trusted application access |
| GET | `/api/v1/connector-setup/package` | connectors | Trusted application access |
| POST | `/api/v1/connector-setup/package` | connectors | Trusted application access |
| POST | `/api/v1/connector-setup/preview` | connectors | Trusted application access |
| GET | `/api/v1/connectors` | connectors | Trusted application access |
| POST | `/api/v1/connectors/snapshot` | connectors | Connector-scoped Bearer token |
| POST | `/api/v1/connectors/status` | connectors | Connector-scoped Bearer token |
| GET | `/api/v1/hardware` | hardware | Trusted application access |
| GET | `/api/v1/icon-library` | connectors | Trusted application access |
| GET | `/api/v1/inventory` | settings | Trusted application access |
| GET | `/api/v1/ipam` | ipam | Trusted application access |
| GET | `/api/v1/marketplace` | connectors | Trusted application access |
| POST | `/api/v1/marketplace/details` | connectors | Trusted application access |
| POST | `/api/v1/marketplace/install` | connectors | Trusted application access |
| POST | `/api/v1/marketplace/preview` | connectors | Trusted application access |
| POST | `/api/v1/marketplace/refresh` | connectors | Trusted application access |
| POST | `/api/v1/marketplace/remove` | connectors | Trusted application access |
| POST | `/api/v1/marketplace/rollback` | connectors | Trusted application access |
| POST | `/api/v1/marketplace/source` | connectors | Trusted application access |
| GET | `/api/v1/overview` | overview | Trusted application access |
| GET | `/api/v1/topology` | topology | Trusted application access |
<!-- END GENERATED ROUTES -->

## Read inventory

`GET /api/state` returns the complete editable state, including `_revision`. `GET /api/v1/inventory` returns only `devices`, `services`, `networks` and `links`. Feature-specific read endpoints return their relevant subset or summaries; they do not provide separate per-record mutations.

```sh
curl --fail http://127.0.0.1:8097/api/v1/inventory
curl --fail http://127.0.0.1:8097/api/v1/connector-contract
```

`GET /api/v1/modules` is internal installed-package metadata. A former module activation write endpoint is absent: built-in features are permanently available.

## Replace complete state

`PUT /api/state` validates and atomically writes a complete inventory. Read current state first, modify a copy, retain its current `_revision` and send the full intended state. Success returns `saved` and the new `revision`. The input must be smaller than 32 MB. Invalid records fail without a partial write. A stale revision receives 409; reload before retrying.

This operation is not an object PATCH. An incomplete state can remove data. Prefer connector snapshots for source-owned automated imports and the UI for ordinary edits. Export before a substantial whole-state replacement.

## Import a source snapshot

`POST /api/v1/connectors/snapshot` accepts a version 1 snapshot:

```json
{
  "schemaVersion": 1,
  "connector": "example-lab",
  "devices": [],
  "services": [],
  "networks": [],
  "links": []
}
```

This illustrates shape only. **Do not submit empty arrays as the “successful” result of a failed or incomplete collection.** The body is bounded to 8 MB. The Bearer token must match the declared connector ID. The import validates, merges, namespaces IDs and increments revision. A sample/demo workspace rejects live imports with 409. Success returns an imported record count.

`POST /api/v1/connectors/status` uses the same scoped authentication. Its body includes `connector`, `phase`, and optional `plugin`/`version`. Supported phases are `waiting-configuration`, `imported`, `error`. Status is collection/import reporting, not application uptime monitoring.

`GET /api/v1/connectors` returns stored source reports. The legacy `GET /api/connectors` lists locally installed inventory sources and has different response semantics. `GET /api/connector-schema` is a legacy sample/schema helper; use the versioned contract for current connector development.

Legacy `POST /api/import` and `/api/sync` support local snapshot workflows. They are not substitutes for scoped external-collector authentication and do not themselves perform every upstream collector query.

## Catalog import

`POST /api/catalog/import` accepts a JSON object with a URL:

```json
{"url":"https://github.com/42bios/atlas-device-library-ubiquiti"}
```

Request size is bounded to 5 KB; fetched catalog JSON to 1 MB and 500 models. Success returns `imported` and `source`. Refresh updates one source's models while retaining instantiated hardware and other catalog sources. For model fields and image bounds see [catalog specification](device-catalogs.md).

`GET /api/v1/catalogs` returns `deviceCatalog` and `catalogSources`.

## Add-ins and repository review

- `GET /api/v1/addins`: installed packages, instance state and repository availability metadata; credentials are excluded.
- `POST /api/v1/addins/repository/preview`: `{url, ref}` downloads/verifies a package and creates an expiring review. It does not execute the code.
- `POST /api/v1/addins/repository/install`: `{review, trust}` installs the reviewed copy after exact repository trust confirmation.
- `POST /api/v1/addins/configure`: instance configuration, including a separate private credential channel. Consult the selected package schema rather than copying another adapter's settings.
- `POST /api/v1/addins/action`: action plus applicable instance ID/package ID. Supported lifecycle actions include install, run, enable, disable, remove and uninstall; valid targets depend on installed state.
- `POST /api/v1/addins/repository/access`: private GitHub token and explicit repository allowlist, or `{remove:true}`. This stores private download access, not a general GitHub account session.

Add-in administration requests are bounded to 60 KB. Repository trust/checksum review is still required with private GitHub access. Native collectors execute in isolated Docker workers. Ephemeral active-job tokens only permit source-scoped snapshot/status writes, and worker traffic is rejected on general application routes. The general UI/API still has no human login gate.

## Setup downloads and compatibility

Connector setup preview validates configuration; package download returns an installation ZIP without executing a collector or importing inventory. The GET download route uses one URL-encoded `configuration` JSON parameter for native browser downloads. Never include credentials in that URL.

`POST /api/stencils/import-vssx` is a retained compatibility endpoint accepting raw VSSX bytes and optional URL-encoded `X-Filename`. The regular UI no longer exposes a standalone artwork library. Existing stencil references remain compatible; this endpoint is not the new device repository format.

## Errors

| Status | Common meaning |
| --- | --- |
| 200 | Operation succeeded; inspect the endpoint-specific response |
| 400 | Invalid input, unsupported format or handled collection/package error |
| 403 | Rejected browser Origin or connector credentials, depending on endpoint |
| 404 | No registered route / unsupported old activation endpoint |
| 409 | Stale inventory revision or a live import blocked by demo state |

Handled errors commonly return `{"error":"description"}`. Do not assume every error is an authentication failure. Preserve the response and inspect the corresponding schema, revision or source report before retrying.
