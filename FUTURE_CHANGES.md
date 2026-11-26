# Future changes

Changes that have been **accepted but deliberately deferred** to a later release, usually because they would change behaviour users can see in a bug-fix release. Each entry says what will change, why, and who is affected. When a change ships, move its entry into `CHANGELOG.md` and delete it here.

---

## Hyphenate underscores in nested prefixes

**Planned for:** next minor release

**Today:** a `cli_nested` prefix keeps its underscores in the positive option, but the negative boolean flag hyphenates them:

```python
@dataclass
class Database:
    host: str = "localhost"
    ssl: bool = False

@dataclass
class App:
    primary_db: Database = cli_nested(default_factory=Database)   # auto prefix "primary_db"
```
```
--primary_db-host HOST
--primary_db-ssl / --no-primary-db-ssl
```

**Change:** normalise the prefix the same way field names are normalised, so every option is hyphenated (`--primary-db-host`, `--primary-db-ssl` / `--no-primary-db-ssl`). The negative flag is derived from the positive one, so the two can never disagree.

**Who is affected:** CLIs whose nested prefix contains `_`, either an explicit `prefix="my_db"` or an auto prefix from a multi-word field name. Their positive option names change. Negative flags don't change.

---

## Convert `Path` and `Enum` values consistently

**Planned for:** next minor release

**Today:** `Path`, `Optional[Path]`, `List[Path]` and `Enum`-typed fields receive the **string** as typed on the command line. Values from config files are passed through as loaded.

**Change:** convert values for these types, whatever their source (command line, `base_configs`, `--config` and `build_config_from_dict`), so a field always holds the declared type. An `Enum` value that isn't valid becomes a clear error.

**Who is affected:** code that treats such a field as a string, e.g. `config.output + ".bak"` or `json.dumps(config.output)`.

---

## Disable argparse prefix matching (`allow_abbrev`)

**Planned for:** under consideration

**Today:** argparse accepts any unambiguous prefix of a long option (`--na` for `--name`). With short auto-generated dict override options (`--d`, `--mc`), a mistyped option can silently match a different one.

**Change:** build the parser with `allow_abbrev=False`, so only exact option names are accepted.

**Who is affected:** users who type abbreviated long options.

---

## Annotation-guided construction in `instantiate()`

**Planned for:** under consideration (feature)

**Today:** nested dicts are instantiated only when they carry a dispatch key (`_target_`, or `type` with a registry). Constructor type annotations are used only to look up string kwargs in the registry.

**Change (if wanted):** construct a nested dict as `annotation(**resolved_dict)` when the target's `__init__` annotates that parameter with a class.

**Who is affected:** no one by default. It would be opt-in.
