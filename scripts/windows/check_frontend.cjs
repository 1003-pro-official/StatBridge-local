// Fingerprint manifests and verify direct package versions after npm ci.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const root = path.resolve(process.argv[2]);
const mode = process.argv[3] || 'check';
try {
  const manifest = fs.readFileSync(path.join(root, 'package.json'));
  const lockBytes = fs.readFileSync(path.join(root, 'package-lock.json'));
  const lock = JSON.parse(lockBytes);
  const pkg = JSON.parse(manifest);
  for (const name of Object.keys({...pkg.dependencies, ...pkg.devDependencies})) {
    const wanted = lock.packages[`node_modules/${name}`]?.version;
    const installed = JSON.parse(fs.readFileSync(path.join(root, 'node_modules', name, 'package.json'))).version;
    if (!wanted || wanted !== installed) throw new Error(`${name}: installed ${installed}, locked ${wanted}`);
  }
  const hash = crypto.createHash('sha256').update(manifest).update(lockBytes)
    .update(`${process.platform}-${process.arch}`).digest('hex');
  const stamp = path.join(root, 'node_modules', '.statbridge-dependencies');
  if (mode === 'record') fs.writeFileSync(stamp, hash);
  else if (fs.readFileSync(stamp, 'utf8') !== hash) throw new Error('dependency manifests changed');
} catch (error) {
  console.error(error.message);
  process.exitCode = 1;
}
