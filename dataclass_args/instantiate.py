"""
Generic object instantiation from configuration values.

Provides a convention-based dispatch mechanism for constructing Python objects
from configuration dicts, strings (via registry lookup), or pass-through values.

Dispatch rules (priority order):
    1. None → return None
    2. Not a dict and not a string → return as-is (pass-through)
    3. String + registry → lookup class path in registry → cls()
    4. Dict with _target_ key → import class → cls(**remaining_kwargs)
    5. Dict with type key + registry → lookup → cls(**remaining_kwargs)
    6. Dict with neither key → return as-is (plain dict)

Features:
    - _attr_ traversal: post-construction dotted attribute path resolution
    - Recursive resolution: nested dicts (and list elements) that carry a
      dispatch key are instantiated before the outer object; a string kwarg
      whose __init__ annotation is a class is looked up in the registry
    - Max depth: configurable limit to prevent infinite recursion
    - Path context: error messages include full resolution path for debugging
"""

import importlib
from types import UnionType
from typing import Any, Dict, FrozenSet, Optional, Type, Union, get_args, get_origin

from .exceptions import InstantiationError

# Builtin types that should not be recursively instantiated
_BUILTINS: FrozenSet[Type] = frozenset(
    (str, int, float, bool, bytes, dict, list, tuple, set, frozenset, type(None))
)


def instantiate(
    config: Any,
    *,
    registry: Optional[Dict[str, str]] = None,
    target_key: str = "_target_",
    type_key: str = "type",
    attr_key: Optional[str] = "_attr_",
    recursive: bool = True,
    max_depth: int = 10,
) -> Any:
    """
    Construct a Python object from a configuration value.

    Uses convention-based dispatch to determine how to interpret the config:
    - None passes through as None
    - Non-dict/non-string values pass through unchanged
    - Strings are looked up in the registry to find a class path
    - Dicts with a target key (_target_) use direct class import
    - Dicts with a type key and registry use registry lookup
    - Plain dicts (no special keys) pass through unchanged

    Args:
        config: The configuration value to instantiate from. Can be None,
            a string (registry lookup), a dict (with _target_ or type key),
            or any other value (pass-through).
        registry: Optional mapping of type names to importable class paths.
            Required when config is a string or a dict with a type key.
            Example: {"docker": "myapp.sandboxes.DockerSandbox"}
        target_key: Dict key indicating a direct import path.
            Default: "_target_"
        type_key: Dict key indicating a registry lookup name.
            Default: "type"
        attr_key: Dict key indicating post-construction attribute traversal.
            Set to None to disable _attr_ processing. Default: "_attr_"
        recursive: Whether to resolve nested values in kwargs: dicts and list
            elements carrying a dispatch key, and string kwargs annotated with
            a class (registry lookup). Default: True
        max_depth: Maximum recursion depth to prevent infinite loops.
            Default: 10

    Returns:
        The instantiated object, or the original value for pass-through cases.

    Raises:
        InstantiationError: When instantiation fails due to import errors,
            construction errors, missing registry entries, or max depth exceeded.
            Error messages include the resolution path for debugging.

    Examples:
        # Direct target import
        >>> instantiate({"_target_": "datetime.timedelta", "hours": 2})
        datetime.timedelta(seconds=7200)

        # Registry lookup
        >>> registry = {"docker": "myapp.DockerSandbox"}
        >>> instantiate("docker", registry=registry)

        # Dict with type + registry
        >>> instantiate({"type": "docker", "image": "python:3.11"},
        ...             registry=registry)

        # Pass-through
        >>> instantiate(42)
        42
        >>> instantiate(None)
        None
    """
    return _instantiate_impl(
        config=config,
        registry=registry,
        target_key=target_key,
        type_key=type_key,
        attr_key=attr_key,
        recursive=recursive,
        max_depth=max_depth,
        path="root",
    )


def _instantiate_impl(
    config: Any,
    *,
    registry: Optional[Dict[str, str]] = None,
    target_key: str,
    type_key: str,
    attr_key: Optional[str],
    recursive: bool,
    max_depth: int,
    path: str,
) -> Any:
    """
    Internal implementation with path tracking for error context.

    Args:
        config: Value to instantiate.
        registry: Type name → class path mapping.
        target_key: Key for direct import path in dicts.
        type_key: Key for registry lookup in dicts.
        attr_key: Key for attribute traversal (None to disable).
        recursive: Whether to recurse into nested values.
        max_depth: Remaining recursion depth.
        path: Current resolution path for error messages.

    Returns:
        Instantiated object or pass-through value.

    Raises:
        InstantiationError: On any instantiation failure.
    """
    # Rule 1: None → return None
    if config is None:
        return None

    # Rule 2: Not a dict and not a string → pass-through
    if not isinstance(config, (dict, str)):
        return config

    # Rule 3: String + registry → lookup and instantiate
    if isinstance(config, str):
        return _from_string(
            config,
            registry=registry,
            path=path,
        )

    # config is a dict from here
    return _from_dict(
        config,
        registry=registry,
        target_key=target_key,
        type_key=type_key,
        attr_key=attr_key,
        recursive=recursive,
        max_depth=max_depth,
        path=path,
    )


def _from_string(
    config: str,
    *,
    registry: Optional[Dict[str, str]],
    path: str,
) -> Any:
    """
    Resolve a string config value via registry lookup.

    Args:
        config: String value to look up in registry.
        registry: Type name → class path mapping.
        path: Current resolution path for error context.

    Returns:
        Instantiated object from the looked-up class.

    Raises:
        InstantiationError: If registry is None or key not found.
    """
    if registry is None:
        raise InstantiationError(
            f"String config value '{config}' requires a registry, "
            f"but none was provided (at '{path}')"
        )

    if config not in registry:
        raise InstantiationError(
            f"String config value '{config}' not found in registry "
            f"(available: {sorted(registry.keys())}) (at '{path}')"
        )

    target_path = registry[config]
    cls = _import_target(target_path, path=path)

    try:
        return cls()
    except Exception as exc:
        raise InstantiationError(
            f"Failed to instantiate '{target_path}' with no arguments "
            f"(at '{path}'): {exc}"
        ) from exc


def _require_string(value: Any, key: str, path: str, description: str = "") -> str:
    """Return `value` if it is a string, otherwise raise InstantiationError."""
    if not isinstance(value, str):
        raise InstantiationError(
            f"'{key}' must be a string{description}, "
            f"got {type(value).__name__} (at '{path}')"
        )
    return value


def _pop_attr_path(
    kwargs: Dict[str, Any], attr_key: Optional[str], path: str
) -> Optional[str]:
    """Remove and return the attribute path (a string), or None if absent/disabled."""
    if not attr_key or attr_key not in kwargs:
        return None
    return _require_string(kwargs.pop(attr_key), attr_key, path, " (attribute path)")


def _lookup_registry(registry: Dict[str, str], type_name: str, path: str) -> str:
    """Return the class path registered for `type_name`, or raise InstantiationError."""
    if type_name not in registry:
        raise InstantiationError(
            f"Type '{type_name}' not found in registry "
            f"(available: {sorted(registry.keys())}) (at '{path}')"
        )
    return registry[type_name]


def _construct_from_target(
    kwargs: Dict[str, Any],
    target_path: str,
    attr_path: Optional[str],
    *,
    registry: Optional[Dict[str, str]],
    target_key: str,
    type_key: str,
    attr_key: Optional[str],
    recursive: bool,
    max_depth: int,
    path: str,
) -> Any:
    """Import the target class, resolve its kwargs, construct it and traverse attrs."""
    cls = _import_target(target_path, path=path)
    resolved_kwargs = _resolve_kwargs(
        kwargs,
        cls=cls,
        registry=registry,
        target_key=target_key,
        type_key=type_key,
        attr_key=attr_key,
        recursive=recursive,
        max_depth=max_depth,
        path=path,
    )

    obj = _construct(cls, resolved_kwargs, target_path=target_path, path=path)
    return _traverse_attr(obj, attr_path, path=path)


def _from_dict(
    config: Dict[str, Any],
    *,
    registry: Optional[Dict[str, str]],
    target_key: str,
    type_key: str,
    attr_key: Optional[str],
    recursive: bool,
    max_depth: int,
    path: str,
) -> Any:
    """
    Resolve a dict config value via target key or type+registry dispatch.

    Args:
        config: Dict configuration to resolve.
        registry: Type name → class path mapping.
        target_key: Key for direct import path.
        type_key: Key for registry lookup.
        attr_key: Key for attribute traversal (None to disable).
        recursive: Whether to recurse into nested values.
        max_depth: Remaining recursion depth.
        path: Current resolution path for error context.

    Returns:
        Instantiated object, or the original dict if no dispatch key found.

    Raises:
        InstantiationError: On import/construction/depth errors.
    """
    # Rule 4: Dict with _target_ key → direct import
    if target_key in config:
        kwargs = dict(config)  # Copy before mutating
        target_path = _require_string(
            kwargs.pop(target_key), target_key, path, " (class path)"
        )
        attr_path = _pop_attr_path(kwargs, attr_key, path)

        return _construct_from_target(
            kwargs,
            target_path,
            attr_path,
            registry=registry,
            target_key=target_key,
            type_key=type_key,
            attr_key=attr_key,
            recursive=recursive,
            max_depth=max_depth,
            path=path,
        )

    # Rule 5: Dict with type key + registry → registry lookup
    if type_key in config and registry is not None:
        kwargs = dict(config)  # Copy before mutating
        type_name = _require_string(kwargs.pop(type_key), type_key, path)
        attr_path = _pop_attr_path(kwargs, attr_key, path)
        target_path = _lookup_registry(registry, type_name, path)

        return _construct_from_target(
            kwargs,
            target_path,
            attr_path,
            registry=registry,
            target_key=target_key,
            type_key=type_key,
            attr_key=attr_key,
            recursive=recursive,
            max_depth=max_depth,
            path=path,
        )

    # Rule 6: Dict with neither key → return as-is
    return config


def _resolve_kwargs(
    kwargs: Dict[str, Any],
    *,
    cls: Type,
    registry: Optional[Dict[str, str]],
    target_key: str,
    type_key: str,
    attr_key: Optional[str],
    recursive: bool,
    max_depth: int,
    path: str,
) -> Dict[str, Any]:
    """
    Recursively resolve kwargs before the target class is constructed.

    - A dict value carrying target_key (or type_key with a registry) is
      instantiated; any other dict is passed as-is.
    - List elements are scanned for such dicts.
    - A string value is looked up in the registry when the matching
      __init__ annotation is a non-builtin class and the string is a key.

    Args:
        kwargs: Keyword arguments to potentially resolve.
        cls: Target class whose __init__ annotations guide resolution.
        registry: Type name → class path mapping.
        target_key: Key for direct import path.
        type_key: Key for registry lookup.
        attr_key: Key for attribute traversal.
        recursive: Whether recursion is enabled.
        max_depth: Remaining depth.
        path: Current resolution path.

    Returns:
        Dict with recursively resolved values.
    """
    if not recursive:
        return kwargs

    if max_depth <= 0:
        raise InstantiationError(
            f"Maximum instantiation depth exceeded (at '{path}'). "
            f"This may indicate circular configuration."
        )

    annotations = _get_init_annotations(cls)
    resolved = {}

    for key, value in kwargs.items():
        child_path = f"{path}.{key}"
        annotation = annotations.get(key)

        if isinstance(value, dict):
            resolved[key] = _resolve_dict_value(
                value,
                registry=registry,
                target_key=target_key,
                type_key=type_key,
                attr_key=attr_key,
                recursive=recursive,
                max_depth=max_depth - 1,
                path=child_path,
            )
        elif isinstance(value, list):
            resolved[key] = _resolve_list_value(
                value,
                registry=registry,
                target_key=target_key,
                type_key=type_key,
                attr_key=attr_key,
                recursive=recursive,
                max_depth=max_depth - 1,
                path=child_path,
            )
        elif (
            isinstance(value, str)
            and registry is not None
            and annotation is not None
            and _is_instantiable_type(annotation)
            and value in registry
        ):
            resolved[key] = _instantiate_impl(
                config=value,
                registry=registry,
                target_key=target_key,
                type_key=type_key,
                attr_key=attr_key,
                recursive=recursive,
                max_depth=max_depth,
                path=child_path,
            )
        else:
            resolved[key] = value

    return resolved


def _resolve_dict_value(
    value: Dict[str, Any],
    *,
    registry: Optional[Dict[str, str]],
    target_key: str,
    type_key: str,
    attr_key: Optional[str],
    recursive: bool,
    max_depth: int,
    path: str,
) -> Any:
    """
    Resolve a single dict kwarg value if it carries a dispatch key.

    A dict without a dispatch key is returned unchanged, whatever the
    parameter's annotation: the target class receives the plain dict.

    Args:
        value: Dict value to potentially resolve.
        registry: Type name → class path mapping.
        target_key: Key for direct import path.
        type_key: Key for registry lookup.
        attr_key: Key for attribute traversal.
        recursive: Whether recursion is enabled.
        max_depth: Remaining depth.
        path: Current resolution path.

    Returns:
        Resolved object or original dict.
    """
    has_target = target_key in value
    has_type_with_registry = type_key in value and registry is not None

    if has_target or has_type_with_registry:
        return _instantiate_impl(
            config=value,
            registry=registry,
            target_key=target_key,
            type_key=type_key,
            attr_key=attr_key,
            recursive=recursive,
            max_depth=max_depth,
            path=path,
        )

    return value


def _resolve_list_value(
    value: list,
    *,
    registry: Optional[Dict[str, str]],
    target_key: str,
    type_key: str,
    attr_key: Optional[str],
    recursive: bool,
    max_depth: int,
    path: str,
) -> list:
    """
    Scan list elements for resolvable dicts.

    Only resolves list elements that are dicts with explicit dispatch keys
    (target_key or type_key with registry).

    Args:
        value: List to scan.
        registry: Type name → class path mapping.
        target_key: Key for direct import path.
        type_key: Key for registry lookup.
        attr_key: Key for attribute traversal.
        recursive: Whether recursion is enabled.
        max_depth: Remaining depth.
        path: Current resolution path.

    Returns:
        List with resolvable elements resolved.
    """
    resolved = []
    for i, item in enumerate(value):
        item_path = f"{path}[{i}]"
        if isinstance(item, dict):
            has_target = target_key in item
            has_type_with_registry = type_key in item and registry is not None
            if has_target or has_type_with_registry:
                resolved.append(
                    _instantiate_impl(
                        config=item,
                        registry=registry,
                        target_key=target_key,
                        type_key=type_key,
                        attr_key=attr_key,
                        recursive=recursive,
                        max_depth=max_depth,
                        path=item_path,
                    )
                )
            else:
                resolved.append(item)
        else:
            resolved.append(item)
    return resolved


def _import_target(target_path: str, *, path: str) -> Type:
    """
    Import a class from a dotted path string.

    Splits the path on the last dot to separate module from attribute.
    Handles nested attributes (e.g., "package.module.Class.InnerClass").

    Args:
        target_path: Dotted import path (e.g., "pathlib.Path").
        path: Current resolution path for error context.

    Returns:
        The imported class or callable.

    Raises:
        InstantiationError: If import or attribute access fails.
    """
    if "." not in target_path:
        raise InstantiationError(
            f"Invalid target path '{target_path}': must contain at least one dot "
            f"separating module from attribute (at '{path}')"
        )

    # Try progressively shorter module paths to handle nested attributes
    parts = target_path.rsplit(".", 1)
    module_path = parts[0]
    attr_path = parts[1]

    try:
        module = importlib.import_module(module_path)
    except ImportError as exc:
        # Try splitting further — the module might be shorter
        # e.g., "package.module.Class.method" → module="package.module",
        # attrs="Class.method"
        resolved = _try_import_nested(target_path, path=path)
        if resolved is not None:
            return resolved
        raise InstantiationError(
            f"Failed to import module '{module_path}' "
            f"from target '{target_path}' (at '{path}'): {exc}"
        ) from exc
    except Exception as exc:  # the module exists but raised while importing
        raise InstantiationError(
            f"Error while importing module '{module_path}' "
            f"from target '{target_path}' (at '{path}'): "
            f"{type(exc).__name__}: {exc}"
        ) from exc

    try:
        obj = getattr(module, attr_path)
    except AttributeError as exc:
        raise InstantiationError(
            f"Module '{module_path}' has no attribute '{attr_path}' "
            f"(target: '{target_path}', at '{path}'): {exc}"
        ) from exc

    if not callable(obj):
        raise InstantiationError(
            f"'{target_path}' resolved to {type(obj).__name__}, "
            f"which is not callable (at '{path}')"
        )

    return obj


def _try_import_nested(target_path: str, *, path: str) -> Optional[Any]:
    """
    Try importing with progressively shorter module paths.

    Handles cases like "package.module.Class.InnerClass" where we need to
    import "package.module" and then traverse "Class.InnerClass".

    Args:
        target_path: Full dotted path to resolve.
        path: Current resolution path for error context.

    Returns:
        The resolved object, or None if no valid split found.
    """
    parts = target_path.split(".")

    # Try each possible split point (at least one part for module)
    for i in range(len(parts) - 1, 0, -1):
        module_path = ".".join(parts[:i])
        attr_parts = parts[i:]

        try:
            module = importlib.import_module(module_path)
        except ImportError:
            continue

        # Traverse attributes
        obj = module
        try:
            for attr in attr_parts:
                obj = getattr(obj, attr)
            if not callable(obj):
                continue  # Skip non-callable results
            return obj
        except AttributeError:
            continue

    return None


def _construct(
    cls: Type,
    kwargs: Dict[str, Any],
    *,
    target_path: str,
    path: str,
) -> Any:
    """
    Construct an object from a class and keyword arguments.

    Args:
        cls: Class to instantiate.
        kwargs: Keyword arguments to pass.
        target_path: Original import path (for error messages).
        path: Current resolution path.

    Returns:
        Constructed object.

    Raises:
        InstantiationError: If construction fails.
    """
    try:
        return cls(**kwargs)
    except Exception as exc:
        raise InstantiationError(
            f"Failed to instantiate '{target_path}' with kwargs "
            f"{set(kwargs.keys())} (at '{path}'): {exc}"
        ) from exc


def _traverse_attr(obj: Any, attr_path: Optional[str], *, path: str) -> Any:
    """
    Traverse a dotted attribute path on an object.

    Args:
        obj: Object to traverse.
        attr_path: Dotted attribute path (e.g., "foo.bar.baz"), or None.
        path: Current resolution path for error context.

    Returns:
        The attribute value at the end of the path, or obj if attr_path is None.

    Raises:
        InstantiationError: If attribute traversal fails.
    """
    if attr_path is None:
        return obj

    current = obj
    for attr in attr_path.split("."):
        try:
            current = getattr(current, attr)
        except AttributeError as exc:
            raise InstantiationError(
                f"Attribute traversal failed: object of type "
                f"'{type(current).__name__}' has no attribute '{attr}' "
                f"(traversing '{attr_path}' at '{path}'): {exc}"
            ) from exc

    return current


def _get_init_annotations(cls: Type) -> Dict[str, Type]:
    """
    Safely retrieve __init__ type annotations for a class.

    Uses typing.get_type_hints when possible, falling back to
    __init__.__annotations__ or empty dict.

    Args:
        cls: Class to inspect.

    Returns:
        Dict of parameter name → type annotation.
    """
    try:
        import typing

        hints = typing.get_type_hints(cls.__init__)
        # Remove 'return' annotation if present
        hints.pop("return", None)
        return hints
    except Exception:
        # Fallback: try direct __annotations__ access
        try:
            init_method = cls.__init__
            annotations = getattr(init_method, "__annotations__", {})
            result = dict(annotations)
            result.pop("return", None)
            return result
        except Exception:  # pragma: no cover
            return {}  # pragma: no cover


def _is_instantiable_type(annotation: Type) -> bool:
    """
    Check if a type annotation represents an instantiable (non-builtin) class.

    Handles Optional[T] by unwrapping to T before checking.
    Handles PEP 604 union types (T | None) on Python 3.10+.

    Args:
        annotation: Type annotation to check.

    Returns:
        True if the annotation is a non-builtin class suitable for
        recursive instantiation.
    """
    # Unwrap Optional[T] → T
    unwrapped = _unwrap_optional(annotation)

    # Skip builtins
    if unwrapped in _BUILTINS:
        return False

    # Skip generic types (List[X], Dict[X, Y], etc.)
    if get_origin(unwrapped) is not None:
        return False

    # Must be a class (not a string forward reference, not a special form)
    if not isinstance(unwrapped, type):
        return False

    return True


def _unwrap_optional(annotation: Type) -> Type:
    """
    Unwrap Optional[T] or T | None to get T.

    Handles both typing.Optional[T] / typing.Union[T, None] and
    PEP 604 syntax (T | None) on Python 3.10+.

    Args:
        annotation: Type that may be Optional.

    Returns:
        Inner type if Optional, otherwise original type.
    """
    origin = get_origin(annotation)

    # typing.Union (includes Optional) and PEP 604 unions (X | None)
    if origin is Union or origin is UnionType:
        args = get_args(annotation)
        non_none = [a for a in args if a is not type(None)]
        if len(non_none) == 1:
            return non_none[0]

    return annotation
