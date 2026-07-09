import { api } from "./api";

/** Download an authenticated API file and trigger a browser save dialog. */
export async function downloadApiFile(path: string, fallbackName = "download"): Promise<void> {
  const { data, headers } = await api.get<Blob>(path, { responseType: "blob" });
  const disposition = headers["content-disposition"] as string | undefined;
  let filename = fallbackName;
  if (disposition) {
    const utf = /filename\*=UTF-8''([^;]+)/i.exec(disposition);
    const plain = /filename="?([^";]+)"?/i.exec(disposition);
    if (utf?.[1]) {
      filename = decodeURIComponent(utf[1]);
    } else if (plain?.[1]) {
      filename = plain[1];
    }
  }

  const url = URL.createObjectURL(data);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
