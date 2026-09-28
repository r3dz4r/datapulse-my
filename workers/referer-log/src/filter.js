const STATIC_FILE_PATTERN = /\.(?:avif|bmp|css|csv|eot|gif|ico|jpe?g|js|map|mp3|mp4|ogg|otf|pdf|png|svg|ttf|txt|webm|webp|woff2?)$/i;

function refererHost(value) {
  if (!value) {
    return "";
  }

  try {
    return new URL(value).hostname;
  } catch {
    return "";
  }
}

function isExcludedPath(pathname) {
  return (
    pathname.startsWith("/cdn-cgi/") ||
    pathname === "/mcp" ||
    pathname.startsWith("/mcp/") ||
    pathname.startsWith("/assets/") ||
    STATIC_FILE_PATTERN.test(pathname)
  );
}

/**
 * Returns the Analytics Engine dimensions for genuine document navigation, or
 * null for every other request type. No IP address or complete referer is read.
 */
export function buildNavigationRow(request) {
  if (request.method !== "GET") {
    return null;
  }

  if (request.headers.get("Sec-Fetch-Mode") !== "navigate") {
    return null;
  }

  if (!request.headers.get("Accept")?.toLowerCase().includes("text/html")) {
    return null;
  }

  const url = new URL(request.url);
  if (isExcludedPath(url.pathname)) {
    return null;
  }

  const cf = request.cf ?? {};
  return {
    blobs: [
      url.pathname,
      refererHost(request.headers.get("Referer")),
      cf.country ?? "",
      cf.colo ?? "",
      cf.deviceType ?? "",
    ],
  };
}
