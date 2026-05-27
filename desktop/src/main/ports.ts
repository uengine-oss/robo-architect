/**
 * Free-port selection for backend / Neo4j children (T013, FR-018).
 *
 * Strategy: ephemeral bind+release on 127.0.0.1:0 — the kernel picks an
 * unused port, we close the socket and hand the number to the child to bind.
 * There IS a small race (another process could grab the port between close
 * and the child's bind). `pickFreePort` accepts a `retries` hint; callers
 * who care should retry their bind on failure.
 *
 * `get-port` is intentionally NOT used here: it's ESM-only from v7 and
 * pulling in an ESM dep into a CommonJS main process adds friction. The
 * underlying technique is identical.
 */

import net from "node:net";

export interface PickFreePortOptions {
  /** Bind preference. Always `127.0.0.1` for this app. */
  host?: string;
}

export async function pickFreePort(opts: PickFreePortOptions = {}): Promise<number> {
  const host = opts.host ?? "127.0.0.1";
  return await new Promise<number>((resolve, reject) => {
    const server = net.createServer();
    server.unref();
    server.on("error", reject);
    server.listen({ host, port: 0 }, () => {
      const address = server.address();
      if (!address || typeof address === "string") {
        server.close();
        reject(new Error("ports.pick_free_port: server.address() returned unexpected shape"));
        return;
      }
      const port = address.port;
      server.close(() => resolve(port));
    });
  });
}

/**
 * Run `op(port)` with a freshly picked port; if `op` throws an EADDRINUSE-like
 * error (i.e. someone else grabbed the port between pick and use), retry up
 * to `attempts` times. Throws the last error if all attempts fail.
 */
export async function withFreePort<T>(
  op: (port: number) => Promise<T>,
  attempts = 3,
): Promise<T> {
  let lastErr: unknown;
  for (let i = 0; i < attempts; i++) {
    const port = await pickFreePort();
    try {
      return await op(port);
    } catch (err) {
      lastErr = err;
      if (!isAddressInUse(err)) throw err;
    }
  }
  throw lastErr;
}

function isAddressInUse(err: unknown): boolean {
  if (!err || typeof err !== "object") return false;
  const code = (err as { code?: string }).code;
  return code === "EADDRINUSE" || code === "EACCES";
}
