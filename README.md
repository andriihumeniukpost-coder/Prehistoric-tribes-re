# Prehistoric-tribes-re

## v54 update

Added `analysis/entity_slot_state107_retry_resolution_v54.txt` and `analysis/entity_slot_state107_retry_evidence_v54.csv`. This stage narrows the state-107 transition to the runtime lookup `g.a:[B[g.a:[S[160] + 107]` when `c.I()` reaches its generic branch. The target value is deliberately left unresolved because the current decoded artifacts do not yet establish the live runtime table contents. The report preserves the distinction between a confirmed full-group early return and an unproven permanent slot leak. Original game code remains unchanged.


## v55 update

Added `analysis/entity_slot_full_pool_state107_resolution_v55.txt` and `analysis/entity_slot_full_pool_state107_evidence_v55.csv`. The runtime lookup was resolved from the original JAR resource `/a` using the exact little-endian record loader: state 107 transitions to 69, and state 69 transitions to itself. The state-107 `c.k()` flag byte is 49, so bit 8 is clear and the normal state handler reaches `c.I()` after a full-pool replacement failure. This demonstrates a concrete path where the old mapping/marker are not cleared and the state-107 retry branch is abandoned. A program-wide permanent leak is still not claimed until all independent marker writes/lifecycle paths are excluded. Original game code remains unchanged.


## v56 update
Added `analysis/entity_slot_marker_write_audit_v56.txt`, `analysis/entity_slot_marker_base1919_audit_v56.csv`, and `tools/entity_slot_marker_base1919_audit_v56.py`. This is a focused audit of literal marker-base references; computed-index and whole-array alias paths remain explicit limitations.


## v57 update — computed-index/alias audit

Added `analysis/entity_slot_computed_index_audit_v57.txt`, two bytecode-context CSV inventories, and `tools/entity_slot_computed_index_audit_v57.py`. This is a bounded context audit, not a complete JVM operand-stack proof. The full-pool path remains strongly suspicious, while a global permanent leak is not yet proven.


## v58 update

Added `analysis/entity_slot_independent_reset_paths_v58.txt`, its evidence CSV, and `tools/audit_entity_slot_independent_reset_v58.py`. This update corrects the previous audit: `c.m(int)` is an independent direct zero-write to the slot marker, and scene cleanup methods can invoke it. The permanent/global leak remains unproven.
