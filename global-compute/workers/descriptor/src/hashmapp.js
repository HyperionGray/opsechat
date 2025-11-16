// src/hashmapp.js
// Minimal consistent-hashing ring to pick a stable exit point (e.g., Cloudflare PoP)
// - Deterministic: same key -> same exit (unless ring membership changes)
// - Locality hint: prefer current colo if it’s in the ring
// - Small default ring of common PoPs; can be overridden with env.EXITS (comma-separated)

// FNV-1a 32-bit (sufficient for ring placement)
function fnv1a32(str) {
  let h = 0x811c9dc5 >>> 0;
  for (let i = 0; i < str.length; i++) {
    h ^= str.charCodeAt(i);
    h = Math.imul(h, 0x01000193) >>> 0;
  }
  return h >>> 0;
}

function makeVirtualNodes(id, vnodes = 128) {
  const pts = [];
  for (let i = 0; i < vnodes; i++) {
    const h = fnv1a32(`${id}#${i}`);
    pts.push({ hash: h, id });
  }
  return pts;
}

export class Hashmapp {
  constructor(exits) {
    // exits: array of strings (PoP or logical exit names)
    const nodes = Array.from(new Set((exits || []).map(s => String(s).trim()).filter(Boolean)));
    if (nodes.length === 0) {
      throw new Error('Hashmapp requires at least one exit');
    }
    this.exits = nodes;
    this.ring = [];
    for (const id of nodes) {
      this.ring.push(...makeVirtualNodes(id));
    }
    this.ring.sort((a, b) => (a.hash - b.hash) | 0);
  }

  // Find first ring entry with hash >= keyHash (wrap if needed)
  _lookup(keyHash) {
    let lo = 0, hi = this.ring.length - 1;
    let ans = 0;
    while (lo <= hi) {
      const mid = (lo + hi) >>> 1;
      if (this.ring[mid].hash >= keyHash) {
        ans = mid;
        hi = mid - 1;
      } else {
        lo = mid + 1;
      }
    }
    return this.ring[ans];
  }

  pick(key, opts = {}) {
    const { preferColo } = opts;
    if (preferColo && this.exits.includes(preferColo)) {
      // Strong locality: if the local colo is a valid exit, prefer it
      return preferColo;
    }
    const h = fnv1a32(String(key));
    return this._lookup(h).id;
  }
}

// Build with reasonable defaults
export function buildExitSelector(env, currentColo) {
  const defaultExits = ['MIA','LAX','DFW','ORD','JFK','FRA','LHR','NRT','SYD','SJC','AMS','SIN'];
  const exits = (env?.EXITS ? String(env.EXITS).split(',') : defaultExits).map(s => s.trim()).filter(Boolean);
  const ring = new Hashmapp(exits);
  return (key) => ring.pick(key, { preferColo: currentColo });
}
