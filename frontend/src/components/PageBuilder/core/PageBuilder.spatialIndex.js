const normalizeRect = (rect = {}) => ({
  x: Number(rect.x) || 0,
  y: Number(rect.y) || 0,
  width: Math.max(0, Number(rect.width) || 0),
  height: Math.max(0, Number(rect.height) || 0),
});

const cellRange = (rect, cellSize) => {
  const value = normalizeRect(rect);
  const right = value.x + Math.max(0, value.width - 0.0001);
  const bottom = value.y + Math.max(0, value.height - 0.0001);
  return {
    left: Math.floor(value.x / cellSize),
    right: Math.floor(right / cellSize),
    top: Math.floor(value.y / cellSize),
    bottom: Math.floor(bottom / cellSize),
  };
};

export const rectanglesIntersect = (first, second, gap = 0) => {
  const a = normalizeRect(first);
  const b = normalizeRect(second);
  return a.x < b.x + b.width + gap &&
    a.x + a.width + gap > b.x &&
    a.y < b.y + b.height + gap &&
    a.y + a.height + gap > b.y;
};

export class UniformGridSpatialIndex {
  constructor(cellSize = 160) {
    this.cellSize = Math.max(16, Number(cellSize) || 160);
    this.cells = new Map();
    this.entries = new Map();
  }

  keysFor(rect) {
    const range = cellRange(rect, this.cellSize);
    const keys = [];
    for (let row = range.top; row <= range.bottom; row += 1) {
      for (let column = range.left; column <= range.right; column += 1) {
        keys.push(`${column}:${row}`);
      }
    }
    return keys;
  }

  insert(id, rect, value = null) {
    this.remove(id);
    const normalized = normalizeRect(rect);
    const keys = this.keysFor(normalized);
    const entry = { id, rect: normalized, value, keys };
    this.entries.set(id, entry);
    keys.forEach((key) => {
      if (!this.cells.has(key)) this.cells.set(key, new Set());
      this.cells.get(key).add(id);
    });
    return entry;
  }

  remove(id) {
    const entry = this.entries.get(id);
    if (!entry) return;
    entry.keys.forEach((key) => {
      const cell = this.cells.get(key);
      cell?.delete(id);
      if (cell?.size === 0) this.cells.delete(key);
    });
    this.entries.delete(id);
  }

  update(id, rect, value = this.entries.get(id)?.value) {
    return this.insert(id, rect, value);
  }

  query(rect, predicate = null) {
    const candidateIds = new Set();
    this.keysFor(rect).forEach((key) => {
      this.cells.get(key)?.forEach((id) => candidateIds.add(id));
    });
    return [...candidateIds]
      .map((id) => this.entries.get(id))
      .filter(Boolean)
      .filter((entry) => !predicate || predicate(entry));
  }

  clear() {
    this.cells.clear();
    this.entries.clear();
  }
}

export const expandRect = (rect, amount = 0) => {
  const value = normalizeRect(rect);
  const inset = Number(amount) || 0;
  return {
    x: value.x - inset,
    y: value.y - inset,
    width: value.width + inset * 2,
    height: value.height + inset * 2,
  };
};
