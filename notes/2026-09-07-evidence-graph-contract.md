# Evidence Graph v1 contract

`evidence-graph/v1` is a local-only, deterministic contract. It does not add
an MCP resource, tool, generated artifact, runtime-history reader, or writer.

Nodes preserve canonical dataset identity, time-bound observations, receipt
pointers, bounded claims, and reconciliation verdicts. `observes` connects a
dataset to an observation; `derived_from`, `attested_by`, and `supports` state
provenance; `supersedes` points from the newer observation to the older one;
and `conflicts_with` is explicit rather than inferred.

A claim with `support: supported` must use its observation's exact digest, be
backed by a receipt-to-claim `supports` edge, and cannot be based on an unsafe
status. `partial`, `unsupported`, and `unknown` are preserved without being
upgraded to supported. Reconciliation dataset IDs must resolve to dataset
nodes.

`build_graph` sorts node and edge IDs and derives `generated_at` from the
latest observation (or the UTC epoch for graphs without observations). Its
`graph_id` is SHA-256 over canonical UTF-8 JSON excluding `graph_id`: sorted
keys, sorted nodes and edges, and compact separators. This makes equal graph
content byte-stable without reading the wall clock.

The schema and verifier use the DataPulse pipeline's canonical underscore
statuses (`browser_dependent`, `unknown_freshness`). They exclude free-form
query text and identity, IP, buyer, and session fields through strict node and
edge field allowlists.
