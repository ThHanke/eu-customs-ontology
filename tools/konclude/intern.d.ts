import type { Quad, Term } from "@rdfjs/types";
export interface EncodedBuffers {
    tripleBuffer: ArrayBuffer;
    strTableBuffer: ArrayBuffer;
}
export declare class InternTable {
    private readonly namedNodes;
    private readonly blankNodes;
    private readonly literals;
    private readonly entries;
    private addEntry;
    encodeTerm(term: Term): number;
    buildStrTableBuffer(): ArrayBuffer;
}
export declare function decodeBuffers(combined: ArrayBuffer): Quad[];
export declare function encodeToBuffers(quads: Iterable<Quad>): EncodedBuffers;
/**
 * Compute a stable content hash (djb2, hex) for a collection of quads,
 * ignoring quads in the INFERRED_GRAPH_IRI and HYPOTHETICAL_IRI graphs.
 *
 * The fingerprint is order-independent: quads are serialized to N-Triples
 * canonical strings, sorted, concatenated, then hashed with djb2.
 */
export declare function computeStoreFingerprint(quads: Quad[]): string;
//# sourceMappingURL=intern.d.ts.map