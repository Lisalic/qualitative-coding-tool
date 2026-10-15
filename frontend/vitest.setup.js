// Node 25+ ships its own `localStorage`/`sessionStorage` globals that read
// as `undefined` (or throw) unless `--localstorage-file` is given, and
// vitest's jsdom environment only forwards window keys that are NOT
// already on the global -- so under jsdom the storage globals end up
// undefined and every test touching them fails. Install an in-memory
// Storage for the jsdom-opted files on those Node versions. CI pins
// Node 20, where this is a no-op.
function makeMemoryStorage() {
  const items = new Map();
  return {
    get length() {
      return items.size;
    },
    key(index) {
      return Array.from(items.keys())[index] ?? null;
    },
    getItem(key) {
      return items.has(String(key)) ? items.get(String(key)) : null;
    },
    setItem(key, value) {
      items.set(String(key), String(value));
    },
    removeItem(key) {
      items.delete(String(key));
    },
    clear() {
      items.clear();
    },
  };
}

if (typeof window !== "undefined") {
  for (const name of ["localStorage", "sessionStorage"]) {
    let usable = false;
    try {
      usable = Boolean(globalThis[name]) && typeof globalThis[name].getItem === "function";
    } catch {
      usable = false;
    }
    if (usable) continue;
    Object.defineProperty(globalThis, name, {
      value: makeMemoryStorage(),
      configurable: true,
      writable: true,
    });
  }
}
