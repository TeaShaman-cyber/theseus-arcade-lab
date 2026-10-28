# theseus-zenodo-arcade

Minimal Arcade Hosted MCP adapter for authenticated Zenodo deposit access.

## Initial authority boundary

The first slice exposes exactly two tools:

- `TheseusZenodo.ListDeposits`
- `TheseusZenodo.GetDeposit`

Both require the Arcade custom OAuth provider `theseus-zenodo` with only the Zenodo scope `deposit:write`.

There is deliberately no publish tool and no `deposit:actions` scope in this package.

## Local verification

```bash
python3 -m unittest discover -s tests -v
```

Repository-wide verification remains:

```bash
tools/dev/check
```

## Hosted deployment

The server entrypoint is:

```text
src/theseus_zenodo_arcade/server.py
```

A deployment may use Arcade Hosted once deployment credentials are available. Provider OAuth configuration is separate from server deployment; capability does not imply authorization.
