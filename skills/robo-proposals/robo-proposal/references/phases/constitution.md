# Constitution

Create or repair the target project's Constitution.

Ask one gating question at a time unless the prompt explicitly seeds the answer:

- architecture style: `MONOLITH` or `MICROSERVICES`
- technology stack
- repository strategy: `MONOREPO` or `REPO_PER_SERVICE`
- if repo-per-service, repo mode: `SPLIT_GIT` or `REUSE_EXISTING`

When all decisions are available, output:

```json
{ "action": "done", "raw": "...", "fields": { "designPrinciples": "...", "techStack": "...", "architectureStyle": "MONOLITH", "repoStrategy": "MONOREPO", "repoMode": null }, "seededFrom": [], "recommendations": [] }
```
