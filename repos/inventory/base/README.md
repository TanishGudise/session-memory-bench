# inventory

Stock levels, reservations and holds for Larkspur's warehouses (SFO, EWR, RNO).

Node runs the TypeScript directly (type stripping), so there is no build step and no dependencies:
- include `.ts` in import paths and import types with `import type`
- no enums, namespaces or constructor parameter properties

- `src/db.ts`: in-memory store (`Db`)
- `src/stock.ts`: stock reads and writes
- `src/types.ts`: shared types

Run the tests with `node --test`.
