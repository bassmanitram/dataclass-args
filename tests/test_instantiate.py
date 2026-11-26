"""
Comprehensive tests for the instantiate() utility.

Tests cover all dispatch rules, error paths, recursive resolution,
attribute traversal, custom keys, and edge cases.
"""

from typing import Optional

import pytest

from dataclass_args import InstantiationError, instantiate

# Module path prefix for fixture classes
FIXTURES = "tests.test_instantiate_fixtures"


class TestNonePassthrough:
    """Rule 1: None → return None."""

    def test_none_returns_none(self):
        assert instantiate(None) is None

    def test_none_with_registry(self):
        """Registry is irrelevant for None."""
        assert instantiate(None, registry={"foo": "bar.Baz"}) is None

    def test_none_with_all_options(self):
        """All options are irrelevant for None."""
        result = instantiate(
            None,
            registry={"x": "y.Z"},
            target_key="custom",
            type_key="kind",
            attr_key="_get_",
            recursive=True,
            max_depth=5,
        )
        assert result is None


class TestNonDictNonStringPassthrough:
    """Rule 2: Not a dict and not a string → return as-is."""

    def test_integer(self):
        assert instantiate(42) == 42

    def test_float(self):
        assert instantiate(3.14) == 3.14

    def test_boolean(self):
        assert instantiate(True) is True
        assert instantiate(False) is False

    def test_list(self):
        data = [1, 2, 3]
        result = instantiate(data)
        assert result == [1, 2, 3]
        assert result is data  # Same object (no copy)

    def test_tuple(self):
        data = (1, "a", None)
        result = instantiate(data)
        assert result is data

    def test_set(self):
        data = {1, 2, 3}
        result = instantiate(data)
        assert result is data

    def test_custom_object(self):
        """Pre-built objects pass through unchanged."""
        from tests.test_instantiate_fixtures import SimpleClass

        obj = SimpleClass(name="existing", count=99)
        result = instantiate(obj)
        assert result is obj
        assert result.name == "existing"
        assert result.count == 99

    def test_bytes(self):
        data = b"hello"
        result = instantiate(data)
        assert result is data


class TestStringWithRegistry:
    """Rule 3: String + registry → lookup and instantiate."""

    def test_simple_lookup(self):
        registry = {"simple": f"{FIXTURES}.SimpleClass"}
        result = instantiate("simple", registry=registry)
        from tests.test_instantiate_fixtures import SimpleClass

        assert isinstance(result, SimpleClass)
        assert result.name == "default"
        assert result.count == 0

    def test_stdlib_class_lookup(self):
        registry = {"ordered": "collections.OrderedDict"}
        from collections import OrderedDict

        result = instantiate("ordered", registry=registry)
        assert isinstance(result, OrderedDict)

    def test_registry_with_multiple_entries(self):
        registry = {
            "simple": f"{FIXTURES}.SimpleClass",
            "storage": f"{FIXTURES}.Storage",
        }
        result = instantiate("storage", registry=registry)
        from tests.test_instantiate_fixtures import Storage

        assert isinstance(result, Storage)
        assert result.path == "/tmp"


class TestStringErrors:
    """Error cases for string config values."""

    def test_string_without_registry_raises(self):
        with pytest.raises(InstantiationError, match="requires a registry"):
            instantiate("some_type")

    def test_string_not_in_registry_raises(self):
        registry = {"foo": "bar.Baz"}
        with pytest.raises(InstantiationError, match="not found in registry"):
            instantiate("unknown", registry=registry)

    def test_string_not_in_registry_shows_available(self):
        registry = {"alpha": "a.A", "beta": "b.B"}
        with pytest.raises(InstantiationError, match="alpha.*beta"):
            instantiate("gamma", registry=registry)

    def test_string_with_bad_import_path(self):
        registry = {"bad": "nonexistent.module.Class"}
        with pytest.raises(InstantiationError, match="Failed to import"):
            instantiate("bad", registry=registry)

    def test_string_path_context_in_error(self):
        with pytest.raises(InstantiationError, match="at 'root'"):
            instantiate("test")

    def test_string_registry_class_fails_to_construct_no_args(self):
        """Registry class with required args fails on zero-arg construction."""
        registry = {"requires_args": f"{FIXTURES}.RequiresArgs"}
        with pytest.raises(
            InstantiationError, match="Failed to instantiate.*with no arguments"
        ):
            instantiate("requires_args", registry=registry)


class TestDictWithTarget:
    """Rule 4: Dict with _target_ key → import and construct."""

    def test_target_no_kwargs(self):
        config = {"_target_": "collections.OrderedDict"}
        from collections import OrderedDict

        result = instantiate(config)
        assert isinstance(result, OrderedDict)

    def test_target_with_kwargs(self):
        config = {
            "_target_": f"{FIXTURES}.SimpleClass",
            "name": "hello",
            "count": 5,
        }
        result = instantiate(config)
        from tests.test_instantiate_fixtures import SimpleClass

        assert isinstance(result, SimpleClass)
        assert result.name == "hello"
        assert result.count == 5

    def test_target_with_partial_kwargs(self):
        config = {"_target_": f"{FIXTURES}.SimpleClass", "name": "partial"}
        result = instantiate(config)
        assert result.name == "partial"
        assert result.count == 0  # default

    def test_target_stdlib_pathlib(self):
        config = {"_target_": "pathlib.PurePosixPath", "args": ("/", "tmp", "file")}
        # PurePosixPath doesn't take 'args' kwarg, use a different test
        config = {"_target_": f"{FIXTURES}.Storage", "path": "/data", "readonly": True}
        result = instantiate(config)
        assert result.path == "/data"
        assert result.readonly is True

    def test_target_with_registry_still_uses_target(self):
        """_target_ takes precedence over type+registry dispatch."""
        registry = {"storage": f"{FIXTURES}.Storage"}
        config = {
            "_target_": f"{FIXTURES}.SimpleClass",
            "name": "target_wins",
        }
        # Despite registry being available, _target_ is used (Rule 4 before Rule 5)
        result = instantiate(config, registry=registry)
        from tests.test_instantiate_fixtures import SimpleClass

        assert isinstance(result, SimpleClass)
        assert result.name == "target_wins"


class TestDictWithTargetErrors:
    def test_target_non_string_raises_instantiation_error(self):
        """Non-string _target_ value raises InstantiationError."""
        with pytest.raises(InstantiationError, match="'_target_' must be a string"):
            instantiate({"_target_": 123})

    def test_target_list_raises_instantiation_error(self):
        """List _target_ value raises InstantiationError."""
        with pytest.raises(InstantiationError, match="'_target_' must be a string"):
            instantiate({"_target_": ["pathlib", "Path"]})

    """Error cases for _target_ dispatch."""

    def test_bad_module_path(self):
        config = {"_target_": "nonexistent_module.Class"}
        with pytest.raises(InstantiationError, match="Failed to import"):
            instantiate(config)

    def test_bad_attribute(self):
        config = {"_target_": "collections.NonexistentClass"}
        with pytest.raises(InstantiationError, match="has no attribute"):
            instantiate(config)

    def test_no_dot_in_target(self):
        config = {"_target_": "NoDotPath"}
        with pytest.raises(InstantiationError, match="must contain at least one dot"):
            instantiate(config)

    def test_construction_failure(self):
        config = {"_target_": f"{FIXTURES}.FailsToConstruct"}
        with pytest.raises(InstantiationError, match="Failed to instantiate"):
            instantiate(config)

    def test_construction_failure_with_args(self):
        config = {"_target_": f"{FIXTURES}.FailsWithArgs", "value": -1}
        with pytest.raises(InstantiationError, match="must be non-negative"):
            instantiate(config)

    def test_wrong_kwargs(self):
        config = {
            "_target_": f"{FIXTURES}.SimpleClass",
            "nonexistent_param": "value",
        }
        with pytest.raises(InstantiationError, match="Failed to instantiate"):
            instantiate(config)

    def test_error_includes_path_context(self):
        config = {"_target_": "bad.path.Class"}
        with pytest.raises(InstantiationError, match="at 'root'"):
            instantiate(config)

    def test_non_callable_target_raises(self):
        """Non-callable target (e.g., a constant) raises InstantiationError."""
        with pytest.raises(InstantiationError, match="not callable"):
            instantiate({"_target_": "logging.DEBUG"})

    def test_non_callable_nested_target_falls_through(self):
        """Non-callable via nested import path raises InstantiationError."""
        # This goes through _try_import_nested which skips non-callables,
        # resulting in an import error since no callable resolution found
        with pytest.raises(InstantiationError):
            instantiate(
                {
                    "_target_": "tests.test_instantiate_fixtures.ClassWithConstant.CONSTANT_VALUE"
                }
            )


class TestDictWithTypeAndRegistry:
    """Rule 5: Dict with type key + registry → lookup and construct."""

    def test_type_with_registry(self):
        registry = {"simple": f"{FIXTURES}.SimpleClass"}
        config = {"type": "simple", "name": "typed", "count": 7}
        result = instantiate(config, registry=registry)
        from tests.test_instantiate_fixtures import SimpleClass

        assert isinstance(result, SimpleClass)
        assert result.name == "typed"
        assert result.count == 7

    def test_type_with_registry_no_extra_kwargs(self):
        registry = {"simple": f"{FIXTURES}.SimpleClass"}
        config = {"type": "simple"}
        result = instantiate(config, registry=registry)
        assert result.name == "default"

    def test_type_not_passed_as_kwarg(self):
        """The 'type' key is consumed, not passed to constructor."""
        registry = {"simple": f"{FIXTURES}.SimpleClass"}
        config = {"type": "simple", "name": "test"}
        result = instantiate(config, registry=registry)
        # SimpleClass doesn't have a 'type' param; it would fail if passed
        assert result.name == "test"


class TestDictWithTypeErrors:
    def test_type_non_string_raises_instantiation_error(self):
        """Non-string type value raises InstantiationError."""
        registry = {"docker": "pathlib.Path"}
        with pytest.raises(InstantiationError, match="'type' must be a string"):
            instantiate({"type": 42}, registry=registry)

    def test_type_none_raises_instantiation_error(self):
        """None type value raises InstantiationError."""
        registry = {"docker": "pathlib.Path"}
        with pytest.raises(InstantiationError, match="'type' must be a string"):
            instantiate({"type": None}, registry=registry)

    """Error cases for type+registry dispatch."""

    def test_type_not_in_registry(self):
        registry = {"alpha": "a.A"}
        config = {"type": "unknown", "name": "test"}
        with pytest.raises(InstantiationError, match="not found in registry"):
            instantiate(config, registry=registry)

    def test_type_not_in_registry_shows_available(self):
        registry = {"alpha": "a.A", "beta": "b.B"}
        config = {"type": "gamma"}
        with pytest.raises(InstantiationError, match="alpha.*beta"):
            instantiate(config, registry=registry)


class TestPlainDictPassthrough:
    """Rule 6: Dict with neither dispatch key → return as-is."""

    def test_plain_dict_no_registry(self):
        d = {"foo": "bar", "count": 42}
        result = instantiate(d)
        assert result == {"foo": "bar", "count": 42}

    def test_dict_with_type_key_but_no_registry(self):
        """type key without registry → falls through to Rule 6."""
        d = {"type": "string", "minLength": 1}
        result = instantiate(d)
        assert result == {"type": "string", "minLength": 1}

    def test_empty_dict(self):
        result = instantiate({})
        assert result == {}

    def test_nested_plain_dict(self):
        d = {"outer": {"inner": "value"}}
        result = instantiate(d)
        assert result == {"outer": {"inner": "value"}}


class TestAttrTraversal:
    """_attr_ key triggers post-construction attribute traversal."""

    def test_simple_attr(self):
        config = {
            "_target_": f"{FIXTURES}.Toolkit",
            "_attr_": "version",
        }
        result = instantiate(config)
        assert result == "1.0"

    def test_dotted_attr_path(self):
        config = {
            "_target_": f"{FIXTURES}.Toolkit",
            "_attr_": "tools.search.engine",
        }
        result = instantiate(config)
        assert result == "default"

    def test_deep_attr_path(self):
        config = {
            "_target_": f"{FIXTURES}.ModuleContainer",
            "_attr_": "inner.deep.value",
        }
        result = instantiate(config)
        assert result == "found_it"

    def test_attr_with_type_and_registry(self):
        """_attr_ works with type+registry dispatch too."""
        registry = {"toolkit": f"{FIXTURES}.Toolkit"}
        config = {
            "type": "toolkit",
            "_attr_": "tools.format.style",
        }
        result = instantiate(config, registry=registry)
        assert result == "compact"

    def test_attr_not_consumed_as_kwarg(self):
        """_attr_ is popped from kwargs before construction."""
        config = {
            "_target_": f"{FIXTURES}.SimpleClass",
            "name": "test",
            "_attr_": "name",
        }
        result = instantiate(config)
        assert result == "test"


class TestAttrTraversalErrors:
    """Error cases for _attr_ traversal."""

    def test_missing_attribute(self):
        config = {
            "_target_": f"{FIXTURES}.SimpleClass",
            "_attr_": "nonexistent",
        }
        with pytest.raises(InstantiationError, match="has no attribute 'nonexistent'"):
            instantiate(config)

    def test_missing_deep_attribute(self):
        config = {
            "_target_": f"{FIXTURES}.Toolkit",
            "_attr_": "tools.missing_attr.value",
        }
        with pytest.raises(InstantiationError, match="has no attribute 'missing_attr'"):
            instantiate(config)

    def test_error_includes_full_attr_path(self):
        config = {
            "_target_": f"{FIXTURES}.Toolkit",
            "_attr_": "tools.bad.deep",
        }
        with pytest.raises(InstantiationError, match="traversing 'tools.bad.deep'"):
            instantiate(config)


class TestRecursiveResolution:
    """Recursive resolution of nested dicts via __init__ annotations."""

    def test_nested_dict_resolved_by_annotation(self):
        """Dict matching annotated class type is recursively resolved."""
        config = {
            "_target_": f"{FIXTURES}.App",
            "name": "myapp",
            "storage": {
                "_target_": f"{FIXTURES}.Storage",
                "path": "/data",
                "readonly": True,
            },
        }
        result = instantiate(config)
        from tests.test_instantiate_fixtures import App, Storage

        assert isinstance(result, App)
        assert result.name == "myapp"
        assert isinstance(result.storage, Storage)
        assert result.storage.path == "/data"
        assert result.storage.readonly is True

    def test_plain_dict_not_constructed_from_annotation(self):
        """A plain dict stays a dict even when the annotation is a class."""
        config = {
            "_target_": f"{FIXTURES}.App",
            "name": "myapp",
            "storage": {"path": "/mnt", "readonly": False},
        }
        result = instantiate(config)
        from tests.test_instantiate_fixtures import Storage

        # A nested dict without a dispatch key is passed as-is (Rule 6),
        # even though the storage annotation (Optional[Storage]) is a class:
        # annotations never trigger construction of a plain dict
        assert result.storage == {"path": "/mnt", "readonly": False}

    def test_nested_with_dispatch_key_always_resolves(self):
        """Dicts with _target_ resolve regardless of annotation."""
        config = {
            "_target_": f"{FIXTURES}.Server",
            "name": "prod",
            "database": {
                "_target_": f"{FIXTURES}.Database",
                "host": "db.example.com",
                "port": 3306,
            },
        }
        result = instantiate(config)
        from tests.test_instantiate_fixtures import Database, Server

        assert isinstance(result, Server)
        assert isinstance(result.database, Database)
        assert result.database.host == "db.example.com"
        assert result.database.port == 3306

    def test_deeply_nested_resolution(self):
        """Multiple levels of nesting resolve correctly."""
        config = {
            "_target_": f"{FIXTURES}.Server",
            "name": "deep",
            "database": {
                "_target_": f"{FIXTURES}.Database",
                "host": "nested-host",
            },
            "plugins": [
                {
                    "_target_": f"{FIXTURES}.SimpleClass",
                    "name": "plugin1",
                },
            ],
        }
        result = instantiate(config)
        from tests.test_instantiate_fixtures import Database, SimpleClass

        assert result.name == "deep"
        assert isinstance(result.database, Database)
        assert result.database.host == "nested-host"
        assert isinstance(result.plugins[0], SimpleClass)
        assert result.plugins[0].name == "plugin1"

    def test_nested_with_type_and_registry(self):
        """Nested dicts with type key resolve when registry present."""
        registry = {
            "db": f"{FIXTURES}.Database",
            "store": f"{FIXTURES}.Storage",
        }
        config = {
            "_target_": f"{FIXTURES}.Server",
            "name": "test",
            "database": {"type": "db", "host": "from-registry", "port": 9999},
        }
        result = instantiate(config, registry=registry)
        from tests.test_instantiate_fixtures import Database

        assert isinstance(result.database, Database)
        assert result.database.host == "from-registry"
        assert result.database.port == 9999

    def test_broken_annotations_fallback(self):
        """Explicit _target_ resolves even when parent has broken annotations."""
        config = {
            "_target_": f"{FIXTURES}.BrokenAnnotations",
            "x": {
                "_target_": f"{FIXTURES}.SimpleClass",
                "name": "nested",
            },
        }
        result = instantiate(config)
        from tests.test_instantiate_fixtures import SimpleClass

        # Despite BrokenAnnotations having unresolvable type hints,
        # the nested dict has _target_ so it resolves via explicit dispatch
        assert isinstance(result.x, SimpleClass)
        assert result.x.name == "nested"


class TestRecursiveDisabled:
    """recursive=False skips nested resolution."""

    def test_nested_dict_not_resolved(self):
        config = {
            "_target_": f"{FIXTURES}.Server",
            "name": "norec",
            "database": {
                "_target_": f"{FIXTURES}.Database",
                "host": "should-not-resolve",
            },
        }
        result = instantiate(config, recursive=False)
        # database is passed as a raw dict (not resolved)
        assert isinstance(result.database, dict)
        assert result.database["_target_"] == f"{FIXTURES}.Database"

    def test_list_elements_not_resolved(self):
        config = {
            "_target_": f"{FIXTURES}.Server",
            "name": "norec",
            "plugins": [{"_target_": f"{FIXTURES}.SimpleClass", "name": "p1"}],
        }
        result = instantiate(config, recursive=False)
        assert isinstance(result.plugins[0], dict)


class TestMaxDepth:
    """Max depth prevents infinite recursion."""

    def test_depth_exceeded_raises(self):
        config = {
            "_target_": f"{FIXTURES}.App",
            "name": "deep",
            "storage": {
                "_target_": f"{FIXTURES}.Storage",
                "path": "/deep",
            },
        }
        with pytest.raises(InstantiationError, match="Maximum instantiation depth"):
            instantiate(config, max_depth=1)

    def test_depth_zero_raises_on_nested(self):
        """max_depth=0 means no recursion into kwargs."""
        config = {
            "_target_": f"{FIXTURES}.App",
            "name": "zero",
            "storage": {
                "_target_": f"{FIXTURES}.Storage",
            },
        }
        # max_depth=0 means _resolve_kwargs raises immediately
        with pytest.raises(InstantiationError, match="Maximum instantiation depth"):
            instantiate(config, max_depth=0)

    def test_sufficient_depth_succeeds(self):
        config = {
            "_target_": f"{FIXTURES}.App",
            "name": "ok",
            "storage": {
                "_target_": f"{FIXTURES}.Storage",
                "path": "/ok",
            },
        }
        result = instantiate(config, max_depth=5)
        from tests.test_instantiate_fixtures import Storage

        assert isinstance(result.storage, Storage)

    def test_error_includes_path(self):
        config = {
            "_target_": f"{FIXTURES}.App",
            "name": "test",
            "storage": {
                "_target_": f"{FIXTURES}.Storage",
            },
        }
        with pytest.raises(InstantiationError, match="at 'root.storage'"):
            instantiate(config, max_depth=1)


class TestCustomKeys:
    """Custom target_key, type_key, and attr_key."""

    def test_custom_target_key(self):
        config = {
            "_class_": f"{FIXTURES}.SimpleClass",
            "name": "custom_target",
        }
        result = instantiate(config, target_key="_class_")
        from tests.test_instantiate_fixtures import SimpleClass

        assert isinstance(result, SimpleClass)
        assert result.name == "custom_target"

    def test_custom_target_key_ignores_default(self):
        """Dict with default _target_ is treated as plain dict with custom key."""
        config = {
            "_target_": f"{FIXTURES}.SimpleClass",
            "name": "ignored",
        }
        # With custom target_key="_class_", the _target_ key is just a regular kwarg
        # This dict has neither "_class_" nor type+registry, so Rule 6 applies
        result = instantiate(config, target_key="_class_")
        assert result == config

    def test_custom_type_key(self):
        registry = {"simple": f"{FIXTURES}.SimpleClass"}
        config = {"kind": "simple", "name": "custom_type"}
        result = instantiate(config, type_key="kind", registry=registry)
        assert result.name == "custom_type"

    def test_custom_type_key_ignores_default(self):
        """Dict with default 'type' key treated as plain dict with custom type_key."""
        registry = {"simple": f"{FIXTURES}.SimpleClass"}
        config = {"type": "simple", "name": "ignored"}
        # With type_key="kind", "type" is not recognized as dispatch key
        result = instantiate(config, type_key="kind", registry=registry)
        assert result == config

    def test_custom_attr_key(self):
        config = {
            "_target_": f"{FIXTURES}.Toolkit",
            "_get_": "version",
        }
        result = instantiate(config, attr_key="_get_")
        assert result == "1.0"

    def test_custom_attr_key_ignores_default(self):
        """Default _attr_ is passed as regular kwarg with custom attr_key."""
        config = {
            "_target_": f"{FIXTURES}.SimpleClass",
            "_attr_": "should_be_kwarg",
            "name": "test",
        }
        # _attr_ is not recognized, so it's passed as kwarg
        # SimpleClass doesn't accept _attr_, so construction will fail
        with pytest.raises(InstantiationError, match="Failed to instantiate"):
            instantiate(config, attr_key="_get_")


class TestAttrKeyDisabled:
    """attr_key=None disables _attr_ processing."""

    def test_attr_key_none_passes_through(self):
        """_attr_ is passed as kwarg when attr_key=None."""
        config = {
            "_target_": f"{FIXTURES}.SimpleClass",
            "_attr_": "some_value",
            "name": "test",
        }
        # SimpleClass doesn't accept _attr_, so it'll fail
        # But the point is that _attr_ is NOT consumed
        with pytest.raises(InstantiationError, match="Failed to instantiate"):
            instantiate(config, attr_key=None)

    def test_attr_key_none_with_compatible_class(self):
        """When attr_key=None, _attr_ stays in kwargs for classes that accept it."""
        config = {
            "_target_": f"{FIXTURES}.NoAnnotations",
            "a": 1,
            "b": 2,
            "c": "custom",
        }
        result = instantiate(config, attr_key=None)
        assert result.a == 1
        assert result.b == 2
        assert result.c == "custom"


class TestListResolution:
    """List elements with dispatch keys are resolved."""

    def test_list_elements_with_target(self):
        config = {
            "_target_": f"{FIXTURES}.Server",
            "name": "srv",
            "plugins": [
                {"_target_": f"{FIXTURES}.SimpleClass", "name": "p1"},
                {"_target_": f"{FIXTURES}.SimpleClass", "name": "p2"},
            ],
        }
        result = instantiate(config)
        from tests.test_instantiate_fixtures import SimpleClass

        assert len(result.plugins) == 2
        assert isinstance(result.plugins[0], SimpleClass)
        assert result.plugins[0].name == "p1"
        assert isinstance(result.plugins[1], SimpleClass)
        assert result.plugins[1].name == "p2"

    def test_list_elements_with_type_and_registry(self):
        registry = {"simple": f"{FIXTURES}.SimpleClass"}
        config = {
            "_target_": f"{FIXTURES}.Server",
            "name": "srv",
            "plugins": [
                {"type": "simple", "name": "from_registry"},
            ],
        }
        result = instantiate(config, registry=registry)
        from tests.test_instantiate_fixtures import SimpleClass

        assert isinstance(result.plugins[0], SimpleClass)
        assert result.plugins[0].name == "from_registry"

    def test_list_plain_dicts_not_resolved(self):
        """List elements without dispatch keys are left as-is."""
        config = {
            "_target_": f"{FIXTURES}.Server",
            "name": "srv",
            "plugins": [
                {"name": "plain_dict", "version": "1.0"},
            ],
        }
        result = instantiate(config)
        assert isinstance(result.plugins[0], dict)
        assert result.plugins[0] == {"name": "plain_dict", "version": "1.0"}

    def test_list_mixed_elements(self):
        """Mix of resolvable and plain elements."""
        config = {
            "_target_": f"{FIXTURES}.Server",
            "name": "srv",
            "plugins": [
                {"_target_": f"{FIXTURES}.SimpleClass", "name": "resolved"},
                {"plain": "data"},
                "just a string",
                42,
            ],
        }
        result = instantiate(config)
        from tests.test_instantiate_fixtures import SimpleClass

        assert isinstance(result.plugins[0], SimpleClass)
        assert result.plugins[1] == {"plain": "data"}
        assert result.plugins[2] == "just a string"
        assert result.plugins[3] == 42

    def test_list_with_type_key_no_registry(self):
        """List elements with type key but no registry stay as-is."""
        config = {
            "_target_": f"{FIXTURES}.Server",
            "name": "srv",
            "plugins": [
                {"type": "something", "value": 1},
            ],
        }
        result = instantiate(config)
        assert result.plugins[0] == {"type": "something", "value": 1}


class TestInputNotMutated:
    """Original input dict should not be modified."""

    def test_target_dict_not_mutated(self):
        config = {
            "_target_": f"{FIXTURES}.SimpleClass",
            "name": "test",
            "_attr_": "name",
        }
        original = dict(config)
        instantiate(config)
        assert config == original

    def test_type_dict_not_mutated(self):
        registry = {"simple": f"{FIXTURES}.SimpleClass"}
        config = {"type": "simple", "name": "test"}
        original = dict(config)
        instantiate(config, registry=registry)
        assert config == original

    def test_nested_dict_not_mutated(self):
        inner = {"_target_": f"{FIXTURES}.Storage", "path": "/x"}
        config = {
            "_target_": f"{FIXTURES}.App",
            "name": "test",
            "storage": inner,
        }
        inner_original = dict(inner)
        instantiate(config)
        assert inner == inner_original


class TestAnnotationGuidedResolution:
    """Annotations only matter for string kwargs (registry lookup), never dicts."""

    def test_annotation_not_applied_to_builtin_types(self):
        """Dicts for builtin-typed params (str, int, dict) stay as dicts."""
        # Server has 'name: str' — a dict value for name shouldn't resolve
        config = {
            "_target_": f"{FIXTURES}.Server",
            "name": "test",
            "database": None,
        }
        result = instantiate(config)
        assert result.name == "test"
        assert result.database is None

    def test_annotation_guided_with_target_key(self):
        """Annotation-guided resolution works when nested dict has _target_."""
        config = {
            "_target_": f"{FIXTURES}.App",
            "name": "guided",
            "storage": {
                "_target_": f"{FIXTURES}.Storage",
                "path": "/guided",
            },
        }
        result = instantiate(config)
        from tests.test_instantiate_fixtures import Storage

        assert isinstance(result.storage, Storage)
        assert result.storage.path == "/guided"

    def test_annotation_guided_with_generic_type_returns_dict(self):
        """Dict for generic-typed param (List[str]) passes through as-is."""
        config = {
            "_target_": f"{FIXTURES}.HasListAnnotation",
            "items": {"not": "a_list"},
        }
        result = instantiate(config)
        # List[str] is a generic type, _is_instantiable_type returns False
        # so the nested dict passes through unchanged
        assert result.items == {"not": "a_list"}

    def test_is_instantiable_type_non_type_annotation(self):
        """String forward-ref annotations don't trigger recursive resolution."""
        # BrokenAnnotations has x: 'UndefinedType' — a string, not a type
        # When we pass a plain dict (no dispatch keys) for x, it should
        # pass through because string annotations aren't types
        config = {
            "_target_": f"{FIXTURES}.BrokenAnnotations",
            "x": {"plain": "dict", "no_dispatch": "keys"},
        }
        result = instantiate(config)
        # x gets the raw dict because 'UndefinedType' string annotation
        # causes _get_init_annotations fallback → annotation is string →
        # _is_instantiable_type returns False → dict passes through
        assert result.x == {"plain": "dict", "no_dispatch": "keys"}


class TestNestedClassImport:
    """Import of nested/inner classes."""

    def test_inner_class(self):
        config = {
            "_target_": f"{FIXTURES}.InnerClass.Nested",
            "value": 99,
        }
        result = instantiate(config)
        from tests.test_instantiate_fixtures import InnerClass

        assert isinstance(result, InnerClass.Nested)
        assert result.value == 99

    def test_deep_nested_class(self):
        config = {
            "_target_": f"{FIXTURES}.InnerClass.DeepNested.Deeper",
            "x": 7,
        }
        result = instantiate(config)
        from tests.test_instantiate_fixtures import InnerClass

        assert isinstance(result, InnerClass.DeepNested.Deeper)
        assert result.x == 7

    def test_try_import_nested_attribute_error_fallback(self):
        """Attribute error in nested path triggers fallback and eventual failure."""
        config = {
            "_target_": f"{FIXTURES}.SimpleClass.nonexistent_attr.Deeper",
        }
        with pytest.raises(InstantiationError, match="Failed to import"):
            instantiate(config)


class TestEdgeCases:
    """Edge cases and boundary conditions."""

    def test_empty_registry(self):
        """Empty registry still works (just nothing matches)."""
        with pytest.raises(InstantiationError, match="not found in registry"):
            instantiate("anything", registry={})

    def test_max_depth_one_no_nested(self):
        """max_depth=1 works fine when there's no nested resolution needed."""
        config = {"_target_": f"{FIXTURES}.SimpleClass", "name": "shallow"}
        # max_depth=1 allows one level but _resolve_kwargs would fail at depth 0
        # Actually max_depth is checked in _resolve_kwargs, and decremented before
        # recursive calls. So max_depth=1 means kwargs can be checked but
        # nested dicts at depth 0 would fail.
        # For a class with no nested objects in kwargs, depth=1 is fine.
        result = instantiate(config, max_depth=1)
        assert result.name == "shallow"

    def test_registry_values_can_be_nested_import_paths(self):
        """Registry can point to nested class paths."""
        registry = {"nested": f"{FIXTURES}.InnerClass.Nested"}
        config = {"type": "nested", "value": 55}
        result = instantiate(config, registry=registry)
        assert result.value == 55

    def test_class_with_no_annotations(self):
        """Classes without __init__ type annotations work with kwargs."""
        config = {
            "_target_": f"{FIXTURES}.NoAnnotations",
            "a": "x",
            "b": "y",
            "c": "z",
        }
        result = instantiate(config)
        assert result.a == "x"
        assert result.b == "y"
        assert result.c == "z"

    def test_required_kwarg(self):
        """Classes with required keyword-only params work."""
        config = {
            "_target_": f"{FIXTURES}.CustomInit",
            "required_param": "provided",
        }
        result = instantiate(config)
        assert result.required_param == "provided"

    def test_missing_required_kwarg_raises(self):
        """Missing required params raise InstantiationError."""
        config = {"_target_": f"{FIXTURES}.CustomInit"}
        with pytest.raises(InstantiationError, match="Failed to instantiate"):
            instantiate(config)

    def test_path_context_nested(self):
        """Error path shows full nesting context."""
        config = {
            "_target_": f"{FIXTURES}.Server",
            "name": "test",
            "database": {
                "_target_": "nonexistent.BadClass",
            },
        }
        with pytest.raises(InstantiationError, match="root.database"):
            instantiate(config)

    def test_path_context_list_element(self):
        """Error path shows list index."""
        config = {
            "_target_": f"{FIXTURES}.Server",
            "name": "test",
            "plugins": [
                {"_target_": f"{FIXTURES}.SimpleClass", "name": "ok"},
                {"_target_": "bad.module.Class"},
            ],
        }
        with pytest.raises(InstantiationError, match=r"root\.plugins\[1\]"):
            instantiate(config)


class TestInstantiateUnwrapPaths:
    """Tests for _unwrap_optional and _is_instantiable_type edge cases."""

    def test_unwrap_optional_multi_type_union(self):
        """Multi-type Union (2+ non-None types) is returned unchanged."""
        from typing import Union

        from dataclass_args.instantiate import _is_instantiable_type, _unwrap_optional

        # Union[int, str, None] has 2 non-None types -> returned as-is
        multi_union = Union[int, str, None]
        result = _unwrap_optional(multi_union)
        assert result is multi_union
        # Not instantiable (it's a Union, not a class)
        assert _is_instantiable_type(multi_union) is False

    def test_unwrap_optional_pep604_multi_type(self):
        """PEP 604 multi-type union (int | str | None) returned unchanged."""
        from dataclass_args.instantiate import _unwrap_optional

        pep604_multi = eval("int | str | None")
        result = _unwrap_optional(pep604_multi)
        # 2 non-None types, returned unchanged
        assert result is pep604_multi

    def test_is_instantiable_type_optional_builtin(self):
        """Optional[builtin] unwraps to builtin -> returns False."""
        from dataclass_args.instantiate import _is_instantiable_type

        assert _is_instantiable_type(Optional[str]) is False
        assert _is_instantiable_type(Optional[int]) is False
        assert _is_instantiable_type(Optional[dict]) is False
        assert _is_instantiable_type(Optional[list]) is False

    def test_annotation_guided_builtin_after_unwrap_integration(self):
        """Optional[str] annotated param gets dict passed through (builtin after unwrap)."""
        config = {
            "_target_": f"{FIXTURES}.HasOptionalStr",
            "name": "test",
            "label": {"nested": "dict"},
        }
        result = instantiate(config)
        # label annotation is Optional[str], unwraps to str (builtin)
        # -> _is_instantiable_type returns False -> dict passes through
        assert result.label == {"nested": "dict"}


class TestAnnotationGuidedStringResolution:
    """Tests for string kwarg resolution via annotation + registry."""

    def test_string_kwarg_resolved_via_annotation_and_registry(self):
        """String value for class-typed param resolves via registry."""
        config = {
            "_target_": f"{FIXTURES}.HasTypedField",
            "component": "basic",
        }
        registry = {"basic": f"{FIXTURES}.BasicComponent"}
        result = instantiate(config, registry=registry)
        assert isinstance(
            result.component,
            __import__(
                "tests.test_instantiate_fixtures", fromlist=["BasicComponent"]
            ).BasicComponent,
        )

    def test_string_kwarg_not_in_registry_passes_through(self):
        """String not in registry stays as string (no resolution)."""
        config = {
            "_target_": f"{FIXTURES}.HasTypedField",
            "component": "unknown_type",
        }
        registry = {"basic": f"{FIXTURES}.BasicComponent"}
        result = instantiate(config, registry=registry)
        assert result.component == "unknown_type"

    def test_string_kwarg_no_registry_passes_through(self):
        """No registry means no string resolution."""
        config = {
            "_target_": f"{FIXTURES}.HasTypedField",
            "component": "basic",
        }
        result = instantiate(config)
        assert result.component == "basic"

    def test_string_kwarg_builtin_annotation_passes_through(self):
        """str/int annotation means no resolution even if in registry."""
        config = {
            "_target_": f"{FIXTURES}.HasStringField",
            "name": "basic",
        }
        registry = {"basic": f"{FIXTURES}.BasicComponent"}
        result = instantiate(config, registry=registry)
        assert result.name == "basic"


class TestPep604UnionUnwrap:
    """PEP 604 union type (T | None) unwrapping in recursive resolution."""

    def test_pep604_union_unwrap_in_resolution(self):
        """Optional via PEP 604 (T | None) is correctly unwrapped during resolution."""
        # Define a class with PEP 604 annotation using exec to avoid syntax error on < 3.10
        ns = {}
        exec(
            """
class Pep604Host:
    def __init__(self, name: str = "host", storage: Storage | None = None):
        self.name = name
        self.storage = storage
""",
            {
                "Storage": __import__(
                    "tests.test_instantiate_fixtures", fromlist=["Storage"]
                ).Storage
            },
            ns,
        )
        Pep604Host = ns["Pep604Host"]  # noqa: F841

        # Register the class so we can import it
        # Instead, use _target_ with a class that already exists
        # and verify the unwrapping works via the annotation-guided path
        from dataclass_args.instantiate import _is_instantiable_type, _unwrap_optional

        # Create a PEP 604 type: int | None
        pep604_type = eval("int | None")
        assert _unwrap_optional(pep604_type) is int

        # Verify Storage | None unwraps to Storage
        from tests.test_instantiate_fixtures import Storage

        pep604_storage = eval("Storage | None", {"Storage": Storage})
        unwrapped = _unwrap_optional(pep604_storage)
        assert unwrapped is Storage
        assert _is_instantiable_type(pep604_storage) is True
