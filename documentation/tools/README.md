# Tools

One page per tool in the app. Each page covers, in order: purpose, where to find it, prerequisites, inputs, what happens on submit, output, troubleshooting, and a developer reference.

| Tool | Route(s) | Kind |
|---|---|---|
| [Authentication](authentication.md) | `/login`, `/register` | admin |
| [Projects](projects.md) | `/`, `/project/:projectId` | admin |
| [Import Data](import-data.md) | `/import` | pipeline |
| [Data Browser](data-browser.md) | `/data`, `/filtered-data` | viewer |
| [Filter Data](filter-data.md) | `/filter` | pipeline (AI) |
| [Generate Codebook](generate-codebook.md) | `/codebook-generate` | pipeline (AI) |
| [View Codebook](view-codebook.md) | `/codebook-view` | viewer/editor |
| [Apply Codebook](apply-codebook.md) | `/codebook-apply` | pipeline (AI) |
| [View Coding](view-coding.md) | `/coding-view` | viewer/editor |
| [Compare Codebooks](compare-codebooks.md) | `/compare-codebook` | pipeline (AI) |
| [Compare Codings](compare-codings.md) | `/compare-coding` | pipeline (AI) |
| [Summarize Coding](summarize-coding.md) | `/summarize-coding` | pipeline (AI) |
| [View Summary](view-summary.md) | `/summaryview` | viewer |
| [Prompt Manager](prompt-manager.md) | modal (no route) | admin |

See [../README.md](../README.md) for the full documentation index, and [../workflow.md](../workflow.md) for how these tools chain together into the end-to-end pipeline.
