# Typed MCP Public Catalog Design

## 1. Context and objective

AI PPT Studio v2.2 already exposes a 43-tool MCP surface through `mcp/tool-catalog.mjs`. Five domain registration modules own the Zod schemas, while `mcp/server.mjs` owns the corresponding handler implementations. The current catalog is structurally close to the target, but its tests prove only part of the contract: operation presence, the local-asset exception, handler uniqueness, Python operation parity, server name parity, and a hash-shaped value.

R2 makes that existing surface deterministic and fail-closed. It does not add, remove, rename, or reinterpret a public tool.

## 2. Authority and fixed public surface

`mcp/tool-catalog.mjs` remains the only production source of public descriptors. The fixed surface is:

| Group | Tool count |
|---|---:|
| `project` | 15 |
| `content` | 15 |
| `review` | 4 |
| `visual` | 3 |
| `delivery-experience` | 6 |
| **Total** | **43** |

Every descriptor has exactly these fields:

```text
name | group | handler | operation | schema
```

`schema` is identical to `name`. `read_ai_ppt_project_asset` is the only descriptor whose `operation` is `null`; its Node handler reads a governed local asset without dispatching a Python business operation. All other operations are non-empty strings and must map to the authoritative Python operation set, except the already documented outer-bridge operation `create-project`.

## 3. Considered approaches

### 3.1 Tests only

Freeze the current descriptor snapshot and hash only in tests. This is low churn, but a consumer that imports a malformed catalog outside the test suite would not fail until registration or invocation. It also leaves group cardinality and descriptor shape as test-only knowledge.

### 3.2 Centralize schemas and handlers in the catalog

Move schema objects and handler functions into the catalog and generate the five domain modules. This would create strong compile-time-like coupling, but it reverses the approved architecture: domain modules would no longer own their schemas and handlers. It is an unnecessary refactor for a recovery slice.

### 3.3 Catalog self-validation plus independent contract tests

Keep the existing descriptor rows as the sole production list, export frozen group cardinality metadata, validate the constructed catalog at module initialization, and add independent tests for the fixed descriptor snapshot, canonical hash, group registration, Python parity, and server parity. This is the selected approach because it adds deterministic failure without changing domain ownership or runtime semantics.

## 4. Catalog construction and invariants

The catalog module will expose frozen group counts and validate the catalog once when the module is loaded. Validation must reject:

- a total other than 43;
- an unsupported or incomplete group;
- a group whose count differs from 15/15/4/3/6;
- a descriptor with missing, extra, or reordered contract fields;
- a blank or duplicate tool name;
- a schema identity that differs from the tool name;
- a blank or duplicate handler identity;
- a blank, duplicate, or non-string operation, except the one local-asset `null` operation;
- a catalog array or descriptor that is not frozen.

The validation function is exported for direct negative testing, but production callers do not supply alternate catalogs. The module invokes it on `PUBLIC_TOOL_CATALOG` before exporting the canonical hash.

The hash remains SHA-256 over `JSON.stringify(PUBLIC_TOOL_CATALOG)`. The test suite binds it to the accepted literal value so that descriptor changes require an explicit contract decision rather than silently producing a new valid-looking 64-character hash.

## 5. Domain registration behavior

`registerCatalogGroup(server, group, schemas, handlers)` continues to select descriptors from the central catalog and register them in catalog order. It must:

1. reject an unknown group;
2. require every catalog schema identity for that group;
3. reject schema keys not owned by that group, preventing orphan or cross-group schemas;
4. require every named handler to be a function;
5. register the descriptor name with its exact schema object;
6. invoke the exact handler with `(input, operation, extra)`.

The shared server handler map may contain handlers for all groups, so registration checks required handler completeness but does not reject handlers belonging to other groups.

The five domain files remain responsible only for their schema maps and calls to `registerCatalogGroup`. `mcp/server.mjs` remains responsible for handler implementations and must not acquire a second public-tool list.

## 6. Data flow and failure behavior

```text
fixed descriptor rows
-> frozen PUBLIC_TOOL_CATALOG
-> module-load invariant validation
-> domain schema map + server handler map
-> registerCatalogGroup
-> MCP server listTools()/callTool()
-> Node handler
-> Python Runtime operation (except local asset)
```

Structural catalog defects fail during module import. Domain wiring defects fail during server creation. MCP calls keep their existing runtime error behavior; R2 does not alter business validation, ReviewSession behavior, or Python dispatch.

## 7. Testing and acceptance

TDD first adds tests that fail against the current implementation because group metadata and exported invariant validation do not yet exist, schema-map extras are not rejected, and the canonical hash is not bound to its accepted literal.

Focused proof must cover:

1. the exact 43 descriptor rows, including name, group, handler, operation, and schema identity;
2. exact group order and counts 15/15/4/3/6;
3. total/name/handler/operation uniqueness and the sole local-asset exception;
4. frozen group metadata, catalog, and descriptors;
5. the fixed canonical SHA-256 value;
6. negative validation for malformed counts, fields, groups, identities, operations, and mutability;
7. exact group registration order, schema object identity, handler identity, operation forwarding, and `extra` forwarding;
8. rejection of unknown groups, missing/extra schemas, and missing handlers;
9. Python public-operation parity with the documented outer/private exceptions;
10. MCP server `listTools()` name and input-schema parity for all 43 tools.

Engineering exit requires focused catalog/server tests, the full Node and Python suites, Widget tests, TypeScript typecheck, Widget build, and `npm run probe:mcp` against a temporary governed project. The probe is local engineering evidence only. It cannot prove real host opening, host notification, AI receipt, G0/G3/G4, PowerPoint target rendering, release, installation, or user acceptance.

## 8. Allowed and forbidden scope

Allowed production files:

- `mcp/tool-catalog.mjs`;
- a domain tool file only if testing reveals a real schema-map identity defect;
- catalog/server tests and this slice's design/plan documents.

Forbidden scope:

- Python ReviewSession behavior or domain objects;
- content or visual UI, Widget components, styles, or ViewModels;
- Review Bridge HTTP behavior;
- public tool count, names, groups, handlers, operations, schemas, or business meaning;
- G0/G3/G4, delivery, release, installation, merge, or push.
