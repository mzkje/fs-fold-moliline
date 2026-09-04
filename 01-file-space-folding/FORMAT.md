# .fs Format Spec (v1, FSF781)
- Magic: 8 bytes `FSF781\x00\x01`
- JsonLen: 8 bytes little-endian = manifest length
- Manifest: UTF-8 JSON (not compressed):
  - tech, n_files, entries[{rel,size,hash}], pool_hashes[], pool_sizes[]
- Pool: blobs concatenated in `pool_hashes` order; each blob = zlib(raw file, level 6)
- Lossless guarantee: entry hash = sha256(raw); restore checks size+hash
- Security: restore must reject entries whose rel escapes out_dir; honor max_total

## v2 (planned)
- manifest compressed with zlib-9; chunk-level dedupe optional (after
  file-level dedupe, block-level dedupe adds ~0.3%)


