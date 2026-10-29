# Keeping this documentation current

[Handbook index](README.md)

## Change checklist

1. Identify affected user flows and terminology.
2. Read the implementation and package declarations; do not copy a historical review as current behavior.
3. Update the relevant handbook page, examples, limits and known limitations.
4. Regenerate the declared route table with `python scripts/build-api-docs.py` after route changes.
5. Check internal Markdown links and run affected application tests.
6. Capture new screenshots when behavior or layout changes materially; use an isolated inventory for destructive scenarios.
7. Record deployment verification separately from implementation readiness.

## Documentation ownership

The handbook is the current product reference. The root README is a short entry point. Connector repositories own version-specific upstream authentication and adapter contracts. Device libraries own manufacturer provenance, image rights and hardware coverage. Historical reviews own dated evidence and should not be silently treated as the latest UI.

For an open-source release, validate installation from a clean checkout, remove deployment-specific secrets and private data, review all image licenses, publish a tagged application version and verify all linked repositories. Do not turn test-only adapter validation into a claim of successful live imports.

Last baseline: 12 October 2026. This baseline follows the image-frame correction and current permanently available built-in features.

## Appearance palette

After changing CSS colors, run `python scripts/build-appearance-palette.py`. Interface literals use generated dark tokens with their original light values as fallbacks. The generator is idempotent; physical rack materials and brand marks are excluded. Rebuild frontend bindings after changing appearance controls. Validate Light/Dark/Auto, persisted choice, OS change handling, storage denial, popover interaction and at least one form, map, table and handbook view. Do not invert device images to simulate a theme.
