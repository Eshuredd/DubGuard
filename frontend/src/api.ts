import type { components } from "./generated-api";
// Pydantic serializes default_factory lists in responses even when OpenAPI marks
// them optional on input. Keep this output-only view tied to generated contracts.
type ArrayKeys<T> = {
  [K in keyof T]-?: NonNullable<T[K]> extends unknown[] ? K : never;
}[keyof T];
type Output<T> = T extends (infer U)[]
  ? Output<U>[]
  : T extends object
    ? { [K in keyof T as K extends ArrayKeys<T> ? never : K]: Output<T[K]> } & {
        [K in ArrayKeys<T>]-?: Output<NonNullable<T[K]>>;
      }
    : T;
export type Schema = Output<components["schemas"]>;
export type Policy = Schema["ScriptPolicy-Output"];
export type Transcript = Schema["Transcript"];
export type Review = Schema["ReviewResult"];
export type Workflow = Schema["WorkflowView"];
export type Scenario = Schema["DemoScenario"];
export type Quick = Schema["QuickReport"];
export type QuickConfig = Schema["QuickConfig"];
export type Summary = Schema["WorkflowSummary"];
export type PolicyRecord = Schema["PolicyRecord"];
// Operator UI uses a server-issued HttpOnly cookie. Only this non-secret UI hint
// is stored in the tab; every protected API still authenticates independently.
export const operatorSignedIn = () =>
  sessionStorage.getItem("dubguard-operator") === "signed-in";
export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}
export async function request<T>(
  path: string,
  options: RequestInit = {},
  credential = "",
): Promise<T> {
  const headers = new Headers(options.headers);
  if (credential) headers.set("Authorization", `Bearer ${credential}`);
  if (options.body && !(options.body instanceof FormData))
    headers.set("Content-Type", "application/json");
  const response = await fetch("/api" + path, {
    ...options,
    headers,
    cache: "no-store",
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const detail =
      typeof body.detail === "string"
        ? body.detail
        : response.status === 422
          ? "Some fields are invalid. Check IDs, policy constraints, timestamps and required attestations."
          : "Request failed. Please retry.";
    throw new ApiError(response.status, `${response.status}: ${detail}`);
  }
  return response.json();
}
export const post = <T>(path: string, body?: unknown, credential?: string) =>
  request<T>(
    path,
    {
      method: "POST",
      body: body === undefined ? undefined : JSON.stringify(body),
    },
    credential,
  );
export const upload = (
  path: string,
  file: File,
  credential?: string,
  headers?: HeadersInit,
) => {
  const data = new FormData();
  data.append("file", file);
  return request<{ record_id: string }>(
    path,
    { method: "POST", body: data, headers },
    credential,
  );
};
export async function audioBlob(path: string, credential = "") {
  const r = await fetch("/api" + path, {
    headers: credential ? { Authorization: `Bearer ${credential}` } : {},
    cache: "no-store",
  });
  if (!r.ok)
    throw new ApiError(r.status, "Audio unavailable or session expired.");
  return r.blob();
}
export function saveJSON(value: unknown, name: string) {
  const url = URL.createObjectURL(
    new Blob([JSON.stringify(value, null, 2)], { type: "application/json" }),
  );
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 0);
}
