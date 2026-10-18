import { bundle } from "@remotion/bundler";
import { selectComposition, renderStill } from "@remotion/renderer";
import path from "node:path";
const serveUrl = await bundle({ entryPoint: path.resolve("src/index.tsx") });
const browserExecutable =
  "C:/Program Files/Google/Chrome/Application/chrome.exe";
const composition = await selectComposition({
  serveUrl,
  id: "DubGuard",
  browserExecutable,
});
for (const [name, frame] of [
  ["create", 1980],
  ["upload", 2310],
  ["preview", 2370],
  ["result", 2730],
  ["finding", 2970],
  ["source", 3360],
  ["export", 5430],
  ["transition", 5520],
]) {
  await renderStill({
    serveUrl,
    composition,
    browserExecutable,
    frame,
    output: path.resolve("../private/preview-" + name + ".png"),
  });
  console.log(name);
}
