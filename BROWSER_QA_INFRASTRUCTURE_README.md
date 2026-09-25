# Browser QA infrastructure

## Purpose and architecture

This repository provides a reusable GitHub Actions service for project-owned Playwright tests and a manual infrastructure self-test. Both modes run on `windows-latest`, use Node.js LTS, and require the installed branded Google Chrome Stable and Microsoft Edge Stable executables. The workflow has read-only repository access (`contents: read`) and accepts no secrets.

The infrastructure currently pins Playwright **1.63.0** (and `pdf-lib` 1.17.1). Caller repositories own their application, dependencies, Playwright configuration, and acceptance tests; this repository does not copy a test implementation into callers.

## Browser contract

Every configuration must define these exact Playwright projects:

```js
projects: [
  { name: 'chrome-stable', use: { browserName: 'chromium', channel: 'chrome' } },
  { name: 'edge-stable', use: { browserName: 'chromium', channel: 'msedge' } },
]
```

The reusable workflow asks Playwright to load the caller's configuration and fails clearly if either project is missing or its effective `browserName` or `channel` differs. Generic Chromium is never a fallback.

## Infrastructure self-test

In GitHub, choose **Actions → Browser QA infrastructure validation → Run workflow**. The `workflow_dispatch` path installs the locked dependencies and runs the complete self-test in both branded projects. It exercises the local HTTP server, IndexedDB persistence, A4 PDF creation and page-count validation, 1366×768, 1440×900, and 1920×1080 viewports, runtime console/page-error/request-failure monitoring, screenshots, traces, and the HTML report.

A green workflow is a PASS only when the tests and all infrastructure-specific artifact gates pass. A red workflow is a FAIL; inspect the failed step, HTML report, trace, and retained evidence. Exact self-test screenshots, browser identity JSON, IndexedDB JSON, runtime JSON, print PDFs/JSON, and trace archives are required only in this manual mode.

Artifacts include `browser-self-test`, `playwright-report`, and `playwright-test-results`. Open `playwright-report/index.html` from the downloaded report. Traces are ZIP files below `test-results/` and can be opened with Playwright Trace Viewer. Screenshots, generated PDFs, IndexedDB evidence, and runtime evidence are under `artifacts/self-test/`.

## Calling from another repository

The called workflow checks out the **caller repository**, sets up Node LTS, runs `npm ci`, prints Windows/Node/npm/Playwright versions, verifies both branded executables and projects, runs the requested command, and uploads diagnostics.

```yaml
name: Browser QA
on: [workflow_dispatch, pull_request]

permissions:
  contents: read

jobs:
  browser-qa:
    uses: 669hysk8vt-hash/browser-qa-infrastructure/.github/workflows/browser-qa-reusable.yml@main
```

The complete non-executing example is [`examples/browser-qa-caller.yml`](examples/browser-qa-caller.yml). No secrets are passed. For production, pinning `uses` to a release tag or commit SHA is safer than a moving branch.

### Inputs

| Input | Type | Default | Meaning |
| --- | --- | --- | --- |
| `test_command` | string | `npx playwright test` | Command executed after validation |
| `working_directory` | string | `.` | Caller directory containing `package-lock.json`, package, configuration, and tests |

Callers need only their project code, `package.json`/`package-lock.json`, Playwright configuration, project-specific tests, and the small caller workflow. Infrastructure self-test artifact assertions never run for callers. Caller project behavior remains the caller's responsibility.

Caller uploads use `actions/upload-artifact@v7` with `if: always()` for `playwright-report/`, `test-results/`, and optional `artifacts/`. Missing paths warn rather than replace the original setup or test failure, so early failures retain available diagnostics without producing a false PASS.

## Limitations

These are **not** currently automated acceptance gates:

- the native Windows print-dialog GUI;
- browser zoom at 125%;
- Safari/WebKit.

Browser zoom must not be simulated with CSS `zoom`, transforms, viewport resizing, or `deviceScaleFactor`. The service also does not test Firefox, drive native GUI automation, use self-hosted runners, or define project-specific acceptance criteria. Cross-repository runtime operation must still be proven with a real pilot repository.
