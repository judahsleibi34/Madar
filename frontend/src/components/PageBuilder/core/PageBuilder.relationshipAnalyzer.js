import { UniformGridSpatialIndex, expandRect } from "./PageBuilder.spatialIndex";

const EPSILON = 0.001;
const now = () => globalThis.performance?.now?.() ?? Date.now();

const compareNodes = (first, second) =>
  (first.rect.y - second.rect.y) ||
  (first.rect.x - second.rect.x) ||
  (first.sourceIndex - second.sourceIndex) ||
  String(first.id).localeCompare(String(second.id));

const overlapLength = (startA, sizeA, startB, sizeB) =>
  Math.max(0, Math.min(startA + sizeA, startB + sizeB) - Math.max(startA, startB));

const verticalOverlapRatio = (first, second) => {
  const overlap = overlapLength(first.y, first.height, second.y, second.height);
  return overlap / Math.max(EPSILON, Math.min(first.height, second.height));
};

const horizontalOverlapRatio = (first, second) => {
  const overlap = overlapLength(first.x, first.width, second.x, second.width);
  return overlap / Math.max(EPSILON, Math.min(first.width, second.width));
};

class DisjointSet {
  constructor(ids) {
    this.parent = new Map(ids.map((id) => [id, id]));
  }

  find(id) {
    const parent = this.parent.get(id);
    if (parent === id) return id;
    const root = this.find(parent);
    this.parent.set(id, root);
    return root;
  }

  union(first, second) {
    const firstRoot = this.find(first);
    const secondRoot = this.find(second);
    if (firstRoot === secondRoot) return;
    const root = String(firstRoot).localeCompare(String(secondRoot)) <= 0 ? firstRoot : secondRoot;
    this.parent.set(firstRoot === root ? secondRoot : firstRoot, root);
  }
}

export const getAffectedDependencyClosure = (relationships, changedElementIds = []) => {
  const affected = new Set(changedElementIds);
  const queue = [...affected];
  while (queue.length) {
    const current = queue.shift();
    (relationships?.downstream?.[current] || []).forEach((nextId) => {
      if (affected.has(nextId)) return;
      affected.add(nextId);
      queue.push(nextId);
    });
  }
  return affected;
};

export const analyzeResponsiveRelationships = (inputNodes = [], options = {}) => {
  const startedAt = now();
  const proximity = Math.max(16, Number(options.proximity) || 72);
  const nodes = inputNodes
    .filter((node) => node?.id && node?.rect)
    .map((node, sourceIndex) => ({ ...node, sourceIndex: node.sourceIndex ?? sourceIndex }))
    .sort(compareNodes);
  const nodeById = Object.fromEntries(nodes.map((node) => [node.id, node]));
  const index = new UniformGridSpatialIndex(options.cellSize || 160);
  nodes.forEach((node) => index.insert(node.id, node.rect, node));
  const indexedAt = now();

  const rowSet = new DisjointSet(nodes.map((node) => node.id));
  const adjacency = new Map(nodes.map((node) => [node.id, new Set()]));
  const downstream = Object.fromEntries(nodes.map((node) => [node.id, []]));
  const candidatePairs = new Set();

  nodes.forEach((node) => {
    const searchRect = expandRect(node.rect, proximity);
    index.query(searchRect).forEach((entry) => {
      const other = entry.value;
      if (!other || other.id === node.id) return;
      const pairKey = String(node.id).localeCompare(String(other.id)) < 0
        ? `${node.id}\u0000${other.id}`
        : `${other.id}\u0000${node.id}`;
      if (candidatePairs.has(pairKey)) return;
      candidatePairs.add(pairKey);

      const verticalRatio = verticalOverlapRatio(node.rect, other.rect);
      const horizontalRatio = horizontalOverlapRatio(node.rect, other.rect);
      const nodeCenterY = node.rect.y + node.rect.height / 2;
      const otherCenterY = other.rect.y + other.rect.height / 2;
      const centerTolerance = Math.max(12, Math.min(node.rect.height, other.rect.height) * 0.45);
      const sameRow = verticalRatio >= 0.35 || Math.abs(nodeCenterY - otherCenterY) <= centerTolerance;

      if (sameRow) {
        rowSet.union(node.id, other.id);
        adjacency.get(node.id).add(other.id);
        adjacency.get(other.id).add(node.id);
        return;
      }

      const first = compareNodes(node, other) <= 0 ? node : other;
      const second = first === node ? other : node;
      const verticalGap = second.rect.y - (first.rect.y + first.rect.height);
      const centerDistance = Math.abs(
        (first.rect.x + first.rect.width / 2) - (second.rect.x + second.rect.width / 2)
      );
      if (
        verticalGap >= -EPSILON &&
        verticalGap <= proximity * 2 &&
        (horizontalRatio >= 0.2 || centerDistance <= Math.max(first.rect.width, second.rect.width) * 0.65)
      ) {
        downstream[first.id].push(second.id);
        adjacency.get(first.id).add(second.id);
        adjacency.get(second.id).add(first.id);
      }
    });
  });

  const rowGroupsByRoot = new Map();
  nodes.forEach((node) => {
    const root = rowSet.find(node.id);
    if (!rowGroupsByRoot.has(root)) rowGroupsByRoot.set(root, []);
    rowGroupsByRoot.get(root).push(node);
  });
  const rows = [...rowGroupsByRoot.values()]
    .map((rowNodes) => rowNodes.sort((a, b) =>
      (a.rect.x - b.rect.x) || (a.sourceIndex - b.sourceIndex) || String(a.id).localeCompare(String(b.id))
    ))
    .sort((first, second) => compareNodes(first[0], second[0]))
    .map((rowNodes, indexValue) => ({
      id: `row-${indexValue}`,
      elementIds: rowNodes.map((node) => node.id),
      sourceTop: Math.min(...rowNodes.map((node) => node.rect.y)),
      sourceBottom: Math.max(...rowNodes.map((node) => node.rect.y + node.rect.height)),
    }));

  Object.keys(downstream).forEach((id) => {
    downstream[id] = [...new Set(downstream[id])].sort((firstId, secondId) =>
      compareNodes(nodeById[firstId], nodeById[secondId])
    );
  });

  const completedAt = now();
  return {
    order: nodes.map((node) => node.id),
    rows,
    downstream,
    adjacency: Object.fromEntries(
      [...adjacency].map(([id, neighbors]) => [id, [...neighbors].sort()])
    ),
    candidatePairCount: candidatePairs.size,
    profile: {
      spatialIndexMs: indexedAt - startedAt,
      relationshipInferenceMs: completedAt - indexedAt,
    },
  };
};
