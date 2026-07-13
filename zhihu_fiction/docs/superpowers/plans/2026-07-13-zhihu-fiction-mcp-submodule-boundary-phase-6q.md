# Zhihu Fiction MCP Submodule Boundary Phase 6q

## Goal

Make the nested `zhihu_fiction/mcp_server` repository an explicit external boundary in the parent repository, so local MCP runtime state does not make the parent release tree dirty.

## Scope

- Add tracked submodule metadata for `zhihu_fiction/mcp_server`.
- Keep the MCP repository as an external service boundary.
- Do not stage or merge internal files from the nested MCP repository.
- Add a release contract test that prevents the gitlink from becoming invisible again.

## Implementation

1. Add a release artifact test for `.gitmodules`.
2. Declare `zhihu_fiction/mcp_server` as a submodule path.
3. Preserve the upstream MCP repository URL.
4. Set `ignore = dirty` so local cookies, browser state, and MCP config changes do not pollute parent repository status.

## Verification

- `python -m pytest zhihu_fiction/tests/test_release_artifacts.py::test_mcp_server_gitlink_has_external_boundary_metadata -q`
- `python -m pytest zhihu_fiction/tests/test_release_artifacts.py -q`

## Review Checklist

### Spec Review

- [x] The nested MCP repository remains external.
- [x] The parent repository does not stage internal MCP files.
- [x] The gitlink has explicit clone/init metadata.
- [x] Local MCP runtime state is isolated from parent release status.

### Quality Review

- [x] The test checks observable Git release metadata.
- [x] The submodule URL matches the nested repository remote.
- [x] The change does not introduce secrets, cookies, generated output, or runtime state.
- [x] The change is limited to release boundary metadata, one release test, and this plan.
