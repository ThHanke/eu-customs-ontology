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
/** A request sent from the main thread to this Worker. */
export interface WorkerRequest {
    id: number;
    method: string;
    args: unknown[];
}
/** A response posted back from this Worker to the main thread. */
export interface WorkerResponse {
    id: number;
    result?: unknown;
    error?: string;
}
/** Posted once after the WASM module finishes loading. */
export interface WorkerReadyMessage {
    type: "ready";
}
/** Posted if the WASM module fails to load. */
export interface WorkerInitErrorMessage {
    type: "error";
    error: string;
}
/**
 * Handle a single `WorkerRequest`, dispatching to the appropriate
 * `KoncludeReasoner` method.
 *
 * Exported for unit-test access (tests import and call this directly instead
 * of spinning up a real Worker thread).
 */
export declare function handleMessage(event: MessageEvent<WorkerRequest>): Promise<void>;
//# sourceMappingURL=worker.d.ts.map