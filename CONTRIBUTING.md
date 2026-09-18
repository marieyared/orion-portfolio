# Contributing to Orion

Keep `main` in a working state. Develop each meaningful change on a short-lived branch and merge it through a pull request.

## Workflow

1. Update `main`: `git switch main && git pull --ff-only`.
2. Create a focused branch, such as `feature/expense-dashboard` or `fix/projection-calculation`.
3. Make small commits that each describe one logical change.
4. Run `npm test` before pushing.
5. Open a pull request, complete its checklist, and wait for the automated check.
6. Squash-merge the pull request and delete the branch.

## Useful commands

- `npm test` runs both JavaScript test suites and checks the Python source for syntax errors.
- `npm run serve` serves the repository at `http://127.0.0.1:8080` for local browser testing.

Never commit API keys, unlock codes, account data, or personal financial information. Use `.env` or `.dev.vars` for local secrets.
