// Packs per-origin *.pbf in ../data/<city>/<variant>/ into hours/<hour>.pbf
// so the map fetches one file per city+variant+hour, not one per origin.
// Run after convert.js. The site copies hours/ + manifest + boundary, not origin pbfs.
//
// Usage: node pack_hours.js <city> <variant: static|rt>
const fs = require("fs");
const path = require("path");
const geobuf = require("geobuf");
const Pbf = require("pbf");

const city = process.argv[2];
const variant = process.argv[3];
if (!city || !["static", "rt"].includes(variant)) {
  console.error("Usage: node pack_hours.js <city> <variant: static|rt>");
  process.exit(1);
}

const cityDir = path.join(__dirname, "..", "data", city);
const srcDir = path.join(cityDir, variant);
const manifest = JSON.parse(fs.readFileSync(path.join(cityDir, "manifest.json"), "utf8"));
const files = fs.readdirSync(srcDir).filter((f) => /^\d+\.pbf$/.test(f));
const byHour = new Map();
for (const h of manifest.hours) byHour.set(h, []);

for (let i = 0; i < files.length; i++) {
  const originId = files[i].replace(/\.pbf$/, "");
  const fc = geobuf.decode(new Pbf(fs.readFileSync(path.join(srcDir, files[i]))));
  for (const f of fc.features) {
    if (!f.geometry || !f.geometry.coordinates) continue;
    const hour = f.properties.hour;
    const bucket = byHour.get(hour);
    if (!bucket) continue;
    bucket.push({
      type: "Feature",
      properties: { origin: originId, cutoff_min: f.properties.cutoff_min, hour },
      geometry: f.geometry,
    });
  }
  if ((i + 1) % 400 === 0) console.log(city, variant, i + 1, "/", files.length);
}

const outDir = path.join(srcDir, "hours");
fs.mkdirSync(outDir, { recursive: true });
for (const h of manifest.hours) {
  const packed = { type: "FeatureCollection", features: byHour.get(h) };
  const buf = Buffer.from(geobuf.encode(packed, new Pbf.PbfWriter()));
  fs.writeFileSync(path.join(outDir, h + ".pbf"), buf);
  console.log(city, variant, "h" + h, (buf.length / 1e6).toFixed(2) + "MB", packed.features.length, "feats");
}
