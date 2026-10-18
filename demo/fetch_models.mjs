import fs from "node:fs";
import path from "node:path";
const dir = path.resolve("demo/private/models");
// Parallel byte ranges make large public model downloads resilient to slow transfers.
async function download(name, url) {
  const probe = await fetch(url, {
    headers: { Range: "bytes=0-0" },
    signal: AbortSignal.timeout(90000),
  });
  if (probe.status !== 206)
    throw Error(name + " range unavailable " + probe.status);
  const total = Number(probe.headers.get("content-range")?.split("/")[1]);
  await probe.arrayBuffer();
  console.log(name, total);
  const size = 1048576;
  const count = Math.ceil(total / size);
  let next = 0,
    done = 0;
  const chunks = path.join(dir, name + ".chunks");
  fs.mkdirSync(chunks, { recursive: true });
  async function worker() {
    while (next < count) {
      const i = next++,
        start = i * size,
        end = Math.min(total - 1, start + size - 1),
        p = path.join(chunks, String(i));
      if (fs.existsSync(p) && fs.statSync(p).size === end - start + 1) {
        done++;
        continue;
      }
      for (let attempt = 0; attempt < 4; attempt++) {
        try {
          const r = await fetch(url, {
            headers: { Range: `bytes=${start}-${end}` },
            signal: AbortSignal.timeout(180000),
          });
          if (r.status !== 206) throw Error("range " + r.status);
          const b = Buffer.from(await r.arrayBuffer());
          if (b.length !== end - start + 1) throw Error("length");
          fs.writeFileSync(p, b);
          done++;
          if (done % 8 === 0 || done === count)
            console.log(name, done + "/" + count);
          break;
        } catch (e) {
          if (attempt === 3) throw e;
        }
      }
    }
  }
  await Promise.all(Array.from({ length: 12 }, worker));
  const fd = fs.openSync(path.join(dir, name), "w");
  for (let i = 0; i < count; i++)
    fs.writeSync(fd, fs.readFileSync(path.join(chunks, String(i))));
  fs.closeSync(fd);
  console.log("COMPLETE", name, total);
}
await Promise.all([
  download(
    "kokoro-v1.0.int8.onnx",
    "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.int8.onnx",
  ),
  download(
    "voices-v1.0.bin",
    "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin",
  ),
]);
