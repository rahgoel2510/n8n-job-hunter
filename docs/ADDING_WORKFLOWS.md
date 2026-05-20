# Adding New Workflows

## How to Add a New Pipeline

1. **Export from n8n UI**: Go to your workflow → Menu (⋮) → Download → Save as JSON

2. **Save to workflows directory**:
   ```bash
   mv ~/Downloads/My_Workflow.json workflows/my_workflow.json
   ```

3. **Import into n8n**:
   ```bash
   ./n8n.sh import workflows/my_workflow.json
   ```

4. **Activate** in the n8n UI at http://localhost:5678

## Workflow Guidelines

- **Naming**: Use snake_case for filenames, descriptive names in n8n
- **Credentials**: Never hardcode API keys — use n8n credential store or `$env` variables
- **Idempotency**: Use deduplication (file-based or database) to prevent duplicate processing on re-runs
- **Error handling**: Add error outputs or try/catch in Code nodes
- **Rate limiting**: Add `Sleep` nodes or delays between API calls

## Environment Variables

Workflows can access `.env` variables via `$env.VARIABLE_NAME` in expressions or `process.env.VARIABLE_NAME` in Code nodes.

To add new variables:
1. Add to `.env.example` (with placeholder value)
2. Add to your local `.env` (with real value)
3. Restart n8n: `./n8n.sh restart`

## Sharing Workflows

When committing workflows to git:
- Ensure no credentials are embedded (n8n strips them on export, but verify)
- Document required credentials in a comment at the top of the JSON or in this file
- Test import on a fresh n8n instance

## Backup

All workflow data lives in the `n8n_data` Docker volume. To backup:
```bash
docker compose exec n8n n8n export:workflow --all --output=/home/node/workflows/backup/
```
