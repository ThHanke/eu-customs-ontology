/**
 * Main thread TypeScript wrapper for the Konclude OWL-DL reasoner.
 *
 * `RdfReasoner` is the public API. It spawns a Web Worker running the WASM
 * reasoning kernel and exposes:
 *   - `ready` — resolves when the Worker has finished loading the WASM module
 *   - `reason(quads, opts?)` — runs OWL-DL inference over the input quads
 *   - `classify(quads)` — alias for reason(quads, {mode:'classify'})
 *   - `checkConsistency(quads)` — checks whether the ontology is consistent
 *   - `terminate()` — terminates the underlying Worker
 *
 * Named graphs in the input quads are silently dropped (NTriples is
 * triple-only). All returned quads are placed in the DefaultGraph.
 */
import type { Quad } from "@rdfjs/types";
import { Store } from "n3";
export type { ReasoningOptions, ReasoningResult, StoreReasoningOptions, MaterializeOptions, MaterializeStoreOptions, ClassifyPropertiesStoreOptions, InferenceDelta, WhatIfOptions, ExplainOptions, ClassWarning, ValidationResult, ValidateOptions } from "./types.js";
export { INFERRED_GRAPH_IRI, HYPOTHETICAL_IRI } from "./types.js";
import type { ReasoningOptions, StoreReasoningOptions, MaterializeOptions, MaterializeStoreOptions, ClassifyPropertiesStoreOptions, InferenceDelta, WhatIfOptions, ExplainOptions, ValidationResult, ValidateOptions } from "./types.js";
export declare class RdfReasoner {
    /** Resolves when the Worker WASM module is ready; rejects on init failure. */
    readonly ready: Promise<void>;
    private readonly worker;
    private nextId;
    private readonly pending;
    /**
     * Serialization queue: each reason() / checkConsistency() call chains onto
     * this promise so that concurrent calls never interleave their
     * loadTripleBuffer → realization → getInferredTripleBuffer sequences.
     */
    private _queue;
    private _classifyCache;
    private _materializeCache;
    private _classifyPropertiesCache;
    private _consistencyCache;
    constructor();
    /**
     * Send a method call to the Worker and return a Promise for the result.
     * Pass `transfer` to transfer ownership of ArrayBuffers (zero-copy).
     */
    private _call;
    /** Run OWL-DL reasoning over a Store. Inferred triples are written into
     *  `opts.inferredGraph` (default `INFERRED_GRAPH_IRI`). The graph is cleared
     *  before each call. Concurrent calls are serialized. */
    reason(store: Store, opts?: StoreReasoningOptions): Promise<void>;
    /**
     * @deprecated Use `classify()`, `materialize()`, or `checkConsistency()` instead.
     *
     * Run OWL-DL reasoning over the provided quads.
     *
     * Named graphs in the input are dropped (NTriples wire format is
     * triple-only). All returned quads are in the DefaultGraph.
     *
     * Concurrent calls are serialized: each call waits for the previous one to
     * complete before sending its first Worker message.
     */
    reason(quads: Iterable<Quad>, opts?: ReasoningOptions): Promise<Quad[]>;
    private _reasonOnStore;
    private _reasonOnQuads;
    /** Classify a Store. Inferred rdfs:subClassOf and owl:equivalentClass triples
     *  are written into `opts.inferredGraph` (default `INFERRED_GRAPH_IRI`). The
     *  graph is cleared before each call. Concurrent calls are serialized.
     *
     *  Internally sends a single `classification` command to the WASM worker, which
     *  runs TBox-only reasoning (class hierarchy + property hierarchy). No ABox
     *  realization is performed. For individual rdf:type entailments use
     *  `materialize(store)` instead. */
    classify(store: Store, opts?: StoreReasoningOptions): Promise<void>;
    /**
     * @deprecated Use `classify(store)` instead. For ABox/rdf:type results, use `materialize(store)`.
     *
     * Classify the given quads. Returns the inferred rdfs:subClassOf quads in the
     * default graph. Internally sends a single `classification` command to the
     * WASM worker (TBox-only; no ABox realization).
     */
    classify(quads: Iterable<Quad>): Promise<Quad[]>;
    /** Check consistency of a Store. Does not write inferred triples. */
    checkConsistency(store: Store): Promise<boolean>;
    /**
     * @deprecated Use `checkConsistency(store)` instead.
     *
     * Check whether the given quads form a consistent ontology.
     *
     * Internally: loadTripleBuffer → classification → consistency.
     * Concurrent calls are serialized: each call waits for the previous one to
     * complete before sending its first Worker message.
     */
    checkConsistency(quads: Iterable<Quad>): Promise<boolean>;
    /** Materialize ABox entailments (rdf:type, owl:sameAs, role assertions) into
     *  a Store. Inferred triples are written into `opts.inferredGraph` (default
     *  `INFERRED_GRAPH_IRI`). The graph is cleared before each call. When
     *  `opts.includeClassHierarchy` is `true`, rdfs:subClassOf and
     *  owl:equivalentClass triples are also included. Concurrent calls are
     *  serialized.
     *
     *  Individuals are recognized from any `rdf:type <domain-class>` assertion —
     *  explicit `rdf:type owl:NamedIndividual` declarations are not required.
     *  If the ontology contains no individuals, only TBox inferences are produced
     *  (same result as `classify(store)` with `includeClassHierarchy: true`).
     *
     *  Internally sends a single `realization` command to the WASM worker.
     *  Classification (TBox: class hierarchy + property hierarchy) is always a
     *  prerequisite inside the realization pipeline — it is NOT a separate call.
     *  Both TBox and ABox steps are submitted together in one `prepareOntology()`
     *  invocation at the C++ level.
     *
     *  Pass `{ returnDelta: true }` to receive `{ delta: InferenceDelta }` with the
     *  quads added and removed compared to the previous inferred state. */
    materialize(store: Store, opts: MaterializeStoreOptions & {
        returnDelta: true;
    }): Promise<{
        delta: InferenceDelta;
    }>;
    materialize(store: Store, opts?: MaterializeStoreOptions): Promise<void>;
    /**
     * Materialize ABox entailments (rdf:type assertions) for the given quads.
     *
     * Internally sends a single `realization` command to the WASM worker.
     * Classification (TBox: class hierarchy + property hierarchy) is always a
     * prerequisite inside the realization pipeline — it runs as part of the same
     * `prepareOntology()` call, not as a separate step. By default only rdf:type
     * entailments are returned. Pass `{ includeClassHierarchy: true }` to also
     * receive rdfs:subClassOf and owl:equivalentClass triples.
     *
     * Named graphs in the input are dropped (NTriples wire format is
     * triple-only). All returned quads are in the DefaultGraph.
     *
     * Concurrent calls are serialized: each call waits for the previous one to
     * complete before sending its first Worker message.
     */
    materialize(quads: Iterable<Quad>, opts?: MaterializeOptions): Promise<Quad[]>;
    private _materializeOnStore;
    private _materializeOnQuads;
    /** Classify property hierarchy of a Store. Inferred rdfs:subPropertyOf triples
     *  are written into `opts.inferredGraph` (default `INFERRED_GRAPH_IRI`). The
     *  graph is cleared before each call. Concurrent calls are serialized. */
    classifyProperties(store: Store, opts?: ClassifyPropertiesStoreOptions): Promise<void>;
    /**
     * Classify the property hierarchy for the given quads.
     *
     * Returns the inferred rdfs:subPropertyOf quads in the default graph.
     *
     * Named graphs in the input are dropped (NTriples wire format is
     * triple-only). All returned quads are in the DefaultGraph.
     *
     * Concurrent calls are serialized: each call waits for the previous one to
     * complete before sending its first Worker message.
     */
    classifyProperties(quads: Iterable<Quad>): Promise<Quad[]>;
    private _classifyPropertiesOnStore;
    private _classifyPropertiesOnQuads;
    private _opForPredicate;
    private _classifyInline;
    private _materializeInline;
    private _classifyPropertiesInline;
    /**
     * Private helper — like _classifyInline but also calls getUnsatisfiableClassBuffer
     * and returns the list of unsatisfiable class IRIs.  Updates _classifyCache and
     * writes inferred triples into the store on cache miss (same invariant as
     * _classifyInline).  Must be called from inside a _queue slot only.
     */
    private _getUnsatisfiableClassesInternal;
    /** Return the IRIs of all classes that are unsatisfiable (equivalent to
     *  owl:Nothing) in the ontology.  owl:Nothing itself is excluded.
     *  Classes absent from the taxonomy are NOT included (open-world). */
    getUnsatisfiableClasses(store: Store): Promise<string[]>;
    /** Return `false` if `classIRI` is equivalent to owl:Nothing in the ontology.
     *  Returns `true` for any class absent from the taxonomy (open-world assumption).
     *  owl:Nothing is always unsatisfiable; returns `false` without a Worker call. */
    isSatisfiable(store: Store, classIRI: string): Promise<boolean>;
    /** Check whether a single axiom is entailed by the store's ontology. Returns
     *  null for unsupported predicates (a warning is logged). Triggers reasoning
     *  internally if the store has changed since the last call. */
    isEntailed(store: Store, axiom: Quad): Promise<boolean | null>;
    /** Check whether each axiom in a batch is entailed. Returns null for
     *  individual unsupported predicates. Reasoning is triggered at most once
     *  per required operation type. */
    isEntailed(store: Store, axioms: Quad[]): Promise<(boolean | null)[]>;
    /** Reason over a hypothetical extension of the store without mutating it.
     *
     * Computes full-materialize inferences over `store ∪ additions \ removals`
     * without changing the store's base triples or INFERRED_GRAPH_IRI.
     *
     * Returns `{ added, removed }` relative to the current INFERRED_GRAPH_IRI
     * content (both quads carry `graph = INFERRED_GRAPH_IRI` named node).
     *
     * If `opts.outputGraph` is provided the hypothetical inferences are also
     * written to that named graph in the store (must not equal INFERRED_GRAPH_IRI).
     */
    whatIf(store: Store, additions: Quad[], opts?: WhatIfOptions): Promise<{
        added: Quad[];
        removed: Quad[];
    }>;
    /**
     * Identical to _call. Named separately to mark it safe for use inside a
     * _queue.then() body (no queue gating — callers must already hold the slot).
     * Calling the public methods (classify, materialize, etc.) from inside a
     * _queue body would deadlock.
     */
    private _callDirect;
    private _isBuiltInDeclaration;
    private _opForAxiom;
    private _checkEntailmentDirect;
    /**
     * Returns true if the candidate subset is inconsistent.
     * Uses the consistency Worker pipeline (not triple lookup).
     * Safe to call from inside a _queue body.
     */
    private _checkInconsistencyDirect;
    /**
     * Returns true if `classIRI` is unsatisfiable in the candidate set.
     * Uses buildUnsatisfiableClassBuffer as the oracle (not _checkEntailmentDirect,
     * because buildInferredTripleBuffer suppresses `X rdfs:subClassOf owl:Nothing`).
     * Safe to call from inside a _queue body.
     */
    private _checkUnsatisfiabilityDirect;
    /** Compute minimal justifications for an axiom using the BlackBox algorithm.
     *
     * Returns a list of minimal subsets of the store's base quads, each of which
     * alone entails the axiom. Returns [] if the axiom is not entailed.
     * Each inner Quad[] is a minimal justification.
     *
     * Throws for unsupported predicates (unlike isEntailed which returns null).
     *
     * All BlackBox sub-calls run inside this method's single _queue slot using
     * _callDirect. Do NOT call the public methods classify/materialize from inside.
     */
    explain(store: Store, axiom: Quad, opts?: ExplainOptions): Promise<Quad[][]>;
    /** Compute minimal inconsistent sub-ontologies (MIPS) for an inconsistent
     *  ontology. Returns [] if the ontology is consistent.
     *
     * Uses the consistency oracle directly (loadTripleBuffer → classification →
     * consistency) for all BlackBox iterations. Does not depend on
     * owl:Thing rdfs:subClassOf owl:Nothing being emitted as an inferred triple.
     */
    explainInconsistency(store: Store, opts?: ExplainOptions): Promise<Quad[][]>;
    /** Run a combined diagnostic: check consistency, find unsatisfiable classes,
     *  and (optionally) compute minimal justifications for each.
     *
     *  Returns `{ consistent, errors, warnings }` where:
     *  - `consistent` — `true` when the ontology has at least one model
     *  - `errors` — MIPS (minimal inconsistent sub-ontologies); non-empty only when inconsistent
     *  - `warnings` — one `ClassWarning` per unsatisfiable class (owl:Nothing excluded)
     *
     *  All BlackBox iterations run inside this method's single _queue slot.
     *  Do NOT call public methods from inside — use private helpers only.
     */
    validate(store: Store, opts?: ValidateOptions): Promise<ValidationResult>;
    /** Terminate the underlying Worker and reject all pending calls. */
    terminate(): void;
}
//# sourceMappingURL=index.d.ts.map