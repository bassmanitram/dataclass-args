"""
Option-string collision detection.

Before anything is registered with argparse, the complete set of option
strings the parser will contain is planned and checked for duplicates, so a
clash surfaces as a clear ConfigBuilderError that names the claimants and
suggests a fix, instead of a raw argparse.ArgumentError from deep inside
argparse.

Namespace attributes (argparse ``dest``) are checked too: two arguments with
different option strings, or a positional and an option, that store into the
same attribute would silently overwrite each other.

The plan uses the registry's own helpers to decide which options each field
registers, so it can't drift from the real registration.
"""

from typing import Any, Dict, Iterator, List, Tuple

from .annotations import get_cli_short, is_cli_append, is_cli_positional
from .exceptions import ConfigBuilderError
from .nested_processor import mapping_source
from .utils import cli_name_to_dest, flattened_field_name, negative_flag_name

KIND_HELP = "help"
KIND_CONFIG = "config"
KIND_FIELD = "field"
KIND_SHORT = "short"
KIND_NEGATIVE = "negative"
KIND_OVERRIDE = "override"

# (option string, kind, human description of the claimant)
PlannedOption = Tuple[str, str, str]


def _bool_options(
    owner: str, info: Dict[str, Any], cli_name: Any, prefix: str, field_name: str
) -> Iterator[PlannedOption]:
    """Options registered for a boolean field: --x, optional -s, and --no-x."""
    long_name = cli_name or info["cli_name"]
    if cli_name:
        field_name = flattened_field_name(cli_name)
    short = get_cli_short(info) if prefix == "" else None
    yield long_name, KIND_FIELD, f"field '{owner}' ({long_name})"
    if short:
        yield f"-{short}", KIND_SHORT, f"field '{owner}' (-{short})"
    negative = negative_flag_name(field_name)
    yield negative, KIND_NEGATIVE, f"negative flag of '{owner}' ({negative})"


def _non_bool_options(
    registry: Any, owner: str, info: Dict[str, Any], cli_name: Any, prefix: str
) -> Iterator[PlannedOption]:
    """Options registered for a non-boolean field: --x, optional -s, dict override."""
    resolved_name, short = registry._resolve_cli_name_and_short(cli_name, info, prefix)
    yield resolved_name, KIND_FIELD, f"field '{owner}' ({resolved_name})"
    if short:
        yield f"-{short}", KIND_SHORT, f"field '{owner}' (-{short})"
    if is_cli_append(info) or info["is_list"] or not info["is_dict"]:
        return
    override = registry._compute_dict_override_name(info, resolved_name, prefix)
    if override:
        yield override, KIND_OVERRIDE, f"dict override of '{owner}' ({override})"


def _mapping_options(
    registry: Any, cli_name: str, mapping: Dict[str, Any]
) -> Iterator[PlannedOption]:
    """Options registered for one flattened field (none for positionals/containers)."""
    if mapping.get("parent_field"):
        info = mapping["nested_info"]
        name_arg, prefix = cli_name, mapping["prefix"]
    else:
        info = mapping["field_info"]
        if info.get("is_nested_dataclass", False):
            return
        name_arg, prefix = None, ""
    if is_cli_positional(info):
        return
    owner = mapping_source(mapping)
    if info["type"] == bool:
        yield from _bool_options(
            owner, info, name_arg, prefix, mapping.get("field_name", "")
        )
    else:
        yield from _non_bool_options(registry, owner, info, name_arg, prefix)


def plan_option_strings(
    registry: Any,
    flat_fields: Dict[str, Any],
    base_config_name: str,
    add_help: bool,
) -> List[PlannedOption]:
    """
    List every option string the parser will contain, with who claims it.

    Args:
        registry: The ArgumentRegistry (its helpers decide what each field registers)
        flat_fields: Flattened field mappings
        base_config_name: Name of the config-file option
        add_help: Whether the parser has argparse's -h/--help

    Returns:
        (option string, kind, description) triples in registration order
    """
    planned: List[PlannedOption] = []
    if add_help:
        planned.append(("-h", KIND_HELP, "argparse help (-h/--help)"))
        planned.append(("--help", KIND_HELP, "argparse help (-h/--help)"))
    config_option = f"--{base_config_name}"
    planned.append(
        (config_option, KIND_CONFIG, f"config-file option ({config_option})")
    )
    for cli_name, mapping in flat_fields.items():
        planned.extend(_mapping_options(registry, cli_name, mapping))
    return planned


def _suggestions(option: str, kinds: List[str]) -> List[str]:
    """Targeted fixes for one colliding option string."""
    fixes = []
    if KIND_OVERRIDE in kinds:
        fixes.append(
            'give the dict field a different override: cli_override_name("...")'
        )
    if KIND_SHORT in kinds:
        if KIND_HELP in kinds:
            fixes.append(
                f"{option} is reserved for --help; use a different cli_short letter"
            )
        else:
            fixes.append("use a different cli_short letter for one of the fields")
    if KIND_CONFIG in kinds:
        fixes.append("rename the field, or pass a different base_config_name")
    if KIND_HELP in kinds and KIND_SHORT not in kinds:
        fixes.append("rename the field (--help is reserved for argparse's help)")
    if KIND_NEGATIVE in kinds:
        fixes.append("rename one of the fields (a bool field claims its --no- form)")
    if not fixes:
        fixes.append("rename one of the fields")
    return fixes


def check_option_collisions(planned: List[PlannedOption]) -> None:
    """
    Raise ConfigBuilderError if any option string is claimed more than once.

    Args:
        planned: Output of plan_option_strings

    Raises:
        ConfigBuilderError: Naming each option string, every claimant and a fix
    """
    claims: Dict[str, List[Tuple[str, str]]] = {}
    for option, kind, description in planned:
        claims.setdefault(option, []).append((kind, description))

    lines: List[str] = []
    for option, claimants in claims.items():
        if len(claimants) < 2:
            continue
        lines.append(f"Option string '{option}' is claimed more than once:")
        lines.extend(f"  - {description}" for _, description in claimants)
        for fix in _suggestions(option, [kind for kind, _ in claimants]):
            lines.append(f"  Fix: {fix}")
        lines.append("")

    if lines:
        raise ConfigBuilderError(
            "\n".join(["Option collision detected:", ""] + lines).rstrip()
        )


def _mapping_dests(
    registry: Any, cli_name: str, mapping: Dict[str, Any]
) -> Iterator[Tuple[str, str]]:
    """Namespace attributes one flattened field stores into, with a description."""
    nested = bool(mapping.get("parent_field"))
    info = mapping["nested_info"] if nested else mapping["field_info"]
    owner = mapping_source(mapping)
    if is_cli_positional(info):
        # Positionals in nested dataclasses are rejected when registering
        if not nested:
            yield mapping["field_name"], f"positional '{owner}'"
        return
    if info.get("is_nested_dataclass", False):
        return
    yield cli_name_to_dest(cli_name), f"field '{owner}' ({cli_name})"
    yield from _override_dest(registry, owner, info, cli_name, mapping)


def _override_dest(
    registry: Any,
    owner: str,
    info: Dict[str, Any],
    cli_name: str,
    mapping: Dict[str, Any],
) -> Iterator[Tuple[str, str]]:
    """The dest of a dict field's property-override option, if it has one."""
    if info["type"] == bool or is_cli_append(info) or not info["is_dict"]:
        return
    if info["is_list"]:
        return
    prefix = mapping.get("prefix", "") if mapping.get("parent_field") else ""
    override = registry._compute_dict_override_name(info, cli_name, prefix)
    if override:
        description = f"dict override of '{owner}' ({override})"
        yield cli_name_to_dest(override), description


def check_dest_collisions(
    registry: Any, flat_fields: Dict[str, Any], base_config_name: str
) -> None:
    """
    Raise ConfigBuilderError if two arguments would store into the same attribute.

    Option strings are already unique at this point (check_option_collisions),
    but different strings can still share a ``dest``: a positional field named
    like the config-file option (``config``), or ``cli_override_name("a_b")``
    next to a field ``a_b`` (``--a_b`` and ``--a-b``).

    Args:
        registry: The ArgumentRegistry (its helpers decide what each field registers)
        flat_fields: Flattened field mappings
        base_config_name: Name of the config-file option

    Raises:
        ConfigBuilderError: Naming each shared attribute and its claimants
    """
    claims: Dict[str, List[str]] = {}
    config_dest = base_config_name.replace("-", "_")
    claims[config_dest] = [f"config-file option (--{base_config_name})"]
    for cli_name, mapping in flat_fields.items():
        for dest, description in _mapping_dests(registry, cli_name, mapping):
            claims.setdefault(dest, []).append(description)

    lines: List[str] = []
    for dest, claimants in claims.items():
        if len(claimants) < 2:
            continue
        lines.append(f"Argument destination '{dest}' is claimed more than once:")
        lines.extend(f"  - {description}" for description in claimants)
        lines.append(
            "  Fix: rename one of the fields, use cli_override_name(), "
            "or pass a different base_config_name"
        )
        lines.append("")

    if lines:
        raise ConfigBuilderError(
            "\n".join(["Argument destination collision detected:", ""] + lines).rstrip()
        )
