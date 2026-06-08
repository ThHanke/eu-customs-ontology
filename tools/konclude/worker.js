/**
 * Web Worker entry point for the Konclude OWL-DL reasoner.
 *
 * Lifecycle:
 *   1. On module load: eagerly calls `createKoncludeModule()` → `initPromise`
 *   2. After init: posts `{type:'ready'}` to the main thread
 *   3. On each incoming message: awaits initPromise, dispatches to the
 *      `KoncludeReasoner` instance, posts `{id, result}` or `{id, error}`
 *
 * The `KoncludeReasoner` instance is stateful within a single Worker lifetime:
 *   loadTripleBuffer → classification | realization (→ getInferredTripleBuffer or consistency)
 */
// At runtime this file lives in `dist/` alongside `dist/konclude.mjs`.
// The module is mocked in unit tests (see tests/unit/worker.test.ts).
import createKoncludeModule from "./konclude.mjs";
// ---------------------------------------------------------------------------
// Eager initialisation
// ---------------------------------------------------------------------------
const initPromise = createKoncludeModule({ print: () => { }, printErr: (msg) => console.error(msg) })
    .then((mod) => {
    self.postMessage({ type: "ready" });
    return mod;
})
    .catch((err) => {
    const message = err instanceof Error ? err.message : String(err);
    self.postMessage({ type: "error", error: message });
    throw err;
});
// ---------------------------------------------------------------------------
// Per-worker stateful reasoner instance
// ---------------------------------------------------------------------------
let _reasoner = null;
function getOrCreateReasoner(mod) {
    if (_reasoner === null) {
        _reasoner = new mod.KoncludeReasoner();
    }
    return _reasoner;
}
// ---------------------------------------------------------------------------
// Message dispatch
// ---------------------------------------------------------------------------
/**
 * Handle a single `WorkerRequest`, dispatching to the appropriate
 * `KoncludeReasoner` method.
 *
 * Exported for unit-test access (tests import and call this directly instead
 * of spinning up a real Worker thread).
 */
export async function handleMessage(event) {
    const { id, method, args } = event.data;
    let result;
    try {
        const mod = await initPromise;
        const reasoner = getOrCreateReasoner(mod);
        switch (method) {
            case "loadTripleBuffer": {
                const r = getOrCreateReasoner(mod);
                r.reset();
                const tripleAB = args[0];
                const strTableAB = args[1];
                const tripleCount = tripleAB.byteLength / 12; // 3 × u32 per triple
                const tripleBytes = tripleAB.byteLength;
                const strBytes = strTableAB.byteLength;
                const triplePtr = mod._malloc(tripleBytes);
                const strTablePtr = mod._malloc(strBytes);
                try {
                    mod.HEAPU8.set(new Uint8Array(tripleAB), triplePtr);
                    mod.HEAPU8.set(new Uint8Array(strTableAB), strTablePtr);
                    r.loadTripleBuffer(triplePtr, tripleCount, strTablePtr, strBytes);
                }
                finally {
                    mod._free(triplePtr);
                    mod._free(strTablePtr);
                }
                result = true;
                break;
            }
            case "classification": {
                result = reasoner.classification();
                break;
            }
            case "realization": {
                result = reasoner.realization();
                break;
            }
            case "consistency": {
                result = reasoner.consistency();
                break;
            }
            case "getInferredTripleBuffer": {
                const len = reasoner.buildInferredTripleBuffer();
                if (len > 0) {
                    const ptr = reasoner.getInferredTripleBufferPtr();
                    // HEAPU8.buffer may be a SharedArrayBuffer — slice() copies to a plain AB
                    // so it can be transferred (postMessage transfer requires non-shared AB).
                    const plain = mod.HEAPU8.slice(ptr, ptr + len);
                    const response = { id, result: plain.buffer };
                    self.postMessage(response, [plain.buffer]);
                    return;
                }
                // Empty result — 8-byte combined buffer: [strTableLen=4][count=0]
                const empty = new ArrayBuffer(8);
                new DataView(empty).setUint32(0, 4, true);
                const emptyResponse = { id, result: empty };
                self.postMessage(emptyResponse, [empty]);
                return;
            }
            case "getPropertyTripleBuffer": {
                const len = reasoner.buildPropertyTripleBuffer();
                if (len > 0) {
                    const ptr = reasoner.getInferredTripleBufferPtr();
                    const plain = mod.HEAPU8.slice(ptr, ptr + len);
                    const response = { id, result: plain.buffer };
                    self.postMessage(response, [plain.buffer]);
                    return;
                }
                // Empty result — 8-byte combined buffer: [strTableLen=4][count=0]
                const empty = new ArrayBuffer(8);
                new DataView(empty).setUint32(0, 4, true);
                const emptyResponse = { id, result: empty };
                self.postMessage(emptyResponse, [empty]);
                return;
            }
            case "getUnsatisfiableClassBuffer": {
                result = reasoner.buildUnsatisfiableClassBuffer();
                break;
            }
            default: {
                const response = {
                    id,
                    error: `Unknown method: ${method}`,
                };
                self.postMessage(response);
                return;
            }
        }
        const response = { id, result };
        self.postMessage(response);
    }
    catch (err) {
        const message = err instanceof Error ? err.message : String(err);
        const response = { id, error: message };
        self.postMessage(response);
    }
}
// Wire up the global onmessage handler.
self.onmessage = handleMessage;
//# sourceMappingURL=worker.js.map