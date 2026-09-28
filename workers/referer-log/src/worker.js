import { buildNavigationRow } from "./filter.js";

export default {
  async fetch(request, env, ctx) {
    const row = buildNavigationRow(request);
    if (row) {
      ctx.waitUntil(env.REFERER_LOG.writeDataPoint(row));
    }

    return fetch(request);
  },
};
