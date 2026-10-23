import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const src = fileURLToPath(new URL('../src/', import.meta.url));
const layers = ['app', 'pages', 'widgets', 'features', 'entities', 'shared'];
const errors = [];
const graph = new Map();
const relative = file => path.relative(src, file).split(path.sep).join('/');

function walk(directory) {
  return fs.readdirSync(directory, { withFileTypes: true }).flatMap(entry => {
    const file = path.join(directory, entry.name);
    return entry.isDirectory() ? walk(file) : /\.(tsx?|scss)$/.test(file) ? [file] : [];
  });
}

function resolveLocal(from, specifier) {
  if (!specifier.startsWith('@/') && !specifier.startsWith('.')) return null;
  const target = specifier.startsWith('@/')
    ? path.join(src, specifier.slice(2))
    : path.resolve(path.dirname(from), specifier);
  const candidates = [target, `${target}.ts`, `${target}.tsx`, `${target}.scss`,
    path.join(target, 'index.ts'), path.join(target, 'index.tsx'),
    path.join(path.dirname(target), `_${path.basename(target)}.scss`)];
  const resolved = candidates.find(candidate => fs.existsSync(candidate) && fs.statSync(candidate).isFile());
  if (!resolved) errors.push(`${relative(from)}: не найден ${specifier}`);
  return resolved;
}

function checkBoundary(from, target) {
  const sourceParts = relative(from).split('/');
  const targetParts = relative(target).split('/');
  const [sourceLayer, sourceSlice] = sourceParts;
  const [targetLayer, targetSlice] = targetParts;
  if (sourceLayer === 'main.tsx') {
    if (targetLayer !== 'app') errors.push('main.tsx: точка входа должна импортировать только app');
    return;
  }
  if (!layers.includes(targetLayer)) {
    errors.push(`${relative(from)}: импорт за пределами слоёв FSD: ${relative(target)}`);
    return;
  }
  const sameLayer = sourceLayer === targetLayer;
  const sameSlice = sameLayer && sourceSlice === targetSlice
    && !(sourceLayer === 'shared' && sourceSlice === 'ui' && sourceParts[2] !== targetParts[2]);
  if (layers.indexOf(targetLayer) < layers.indexOf(sourceLayer)) {
    errors.push(`${relative(from)}: запрещён импорт вверх в ${relative(target)}`);
  }
  if (sameLayer && !sameSlice && !['app', 'shared'].includes(sourceLayer)) {
    errors.push(`${relative(from)}: запрещён импорт соседнего слайса ${targetSlice}`);
  }
  if (sameSlice || (sameLayer && sourceLayer === 'app')) return;
  // Sass modules in shared/styles are public; JS slices expose their index.ts API.
  if (targetLayer === 'shared' && targetSlice === 'styles' && target.endsWith('.scss')) return;
  if (sameLayer && sourceLayer === 'shared' && path.dirname(from) === path.dirname(target)) return;
  const expected = targetLayer === 'shared' && targetSlice === 'ui'
    ? `shared/ui/${targetParts[2]}/index.ts`
    : `${targetLayer}/${targetSlice}/index.ts`;
  if (relative(target) !== expected) {
    errors.push(`${relative(from)}: используйте публичный API ${expected}, а не ${relative(target)}`);
  }
}

for (const file of walk(src)) {
  const content = fs.readFileSync(file, 'utf8');
  const pattern = file.endsWith('.scss')
    ? /@(?:use|forward)\s+['"]([^'"]+)['"]/g
    : /(?:\b(?:import|export)\s+(?:type\s+)?(?:[^'";]*?\s+from\s*)?|\bimport\s*\(\s*)['"]([^'"]+)['"]/g;
  const dependencies = [];
  for (const match of content.matchAll(pattern)) {
    const target = resolveLocal(file, match[1]);
    if (!target) continue;
    dependencies.push(target);
    checkBoundary(file, target);
  }
  graph.set(file, dependencies);
}

const visited = new Set();
const active = new Set();
function visit(file, chain = []) {
  if (active.has(file)) {
    errors.push(`Цикл: ${[...chain, file].map(relative).join(' → ')}`);
    return;
  }
  if (visited.has(file)) return;
  active.add(file);
  for (const target of graph.get(file) ?? []) visit(target, [...chain, file]);
  active.delete(file);
  visited.add(file);
}
for (const file of graph.keys()) visit(file);

if (errors.length) {
  console.error(errors.join('\n'));
  process.exitCode = 1;
} else {
  console.log(`FSD: проверены ${graph.size} файлов — слои, слайсы, публичные API и циклы.`);
}
