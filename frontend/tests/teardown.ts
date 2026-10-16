import { rmSync } from "node:fs";
export default async function teardown() {
  if (process.env.DUBGUARD_E2E_DIR)
    rmSync(process.env.DUBGUARD_E2E_DIR, { recursive: true, force: true });
}
