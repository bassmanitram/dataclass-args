"""
Type inspection utilities for analyzing dataclass field types.

Consolidates type origin/args extraction and type checking logic.
"""

from typing import Any, Optional, Tuple, Type

# Import typing utilities with Python 3.8+ compatibility
try:
    from typing import get_args, get_origin  # type: ignore[attr-defined]
except ImportError:
    from typing_extensions import get_args, get_origin  # type: ignore[assignment]


class TypeInspector:
    """
    Unified type inspection for dataclass fields.

    Consolidates repeated type analysis patterns across the codebase.
    """

    @staticmethod
    def get_origin_and_args(
        field_type: Type,
    ) -> Tuple[Optional[Type], Tuple[Type, ...]]:
        """
        Extract origin and args from a typing hint.

        Args:
            field_type: Type hint to analyze

        Returns:
            Tuple of (origin, args)
            - origin: Base type (e.g., list, dict, Union)
            - args: Type parameters (e.g., (str,) for List[str])

        Examples:
            List[str] → (list, (str,))
            Optional[int] → (Union, (int, NoneType))
            Dict[str, Any] → (dict, (str, Any))
            str → (None, ())
        """
        origin = get_origin(field_type)
        args = get_args(field_type) if origin else ()
        return origin, args

    @staticmethod
    def is_optional(field_type: Type) -> bool:
        """
        Check if type is Optional (Union with None).

        Args:
            field_type: Type to check

        Returns:
            True if type is Optional[T] or Union[T, None]
        """
        origin, args = TypeInspector.get_origin_and_args(field_type)

        # Check for Union[T, None] pattern
        if origin is not None:
            # Handle Union types (includes Optional)
            try:
                from typing import Union

                if origin is Union:
                    return type(None) in args
            except ImportError:
                pass

        return False

    @staticmethod
    def unwrap_optional(field_type: Type) -> Type:
        """
        Unwrap Optional[T] to get T.

        Args:
            field_type: Type that may be Optional

        Returns:
            Inner type if Optional, otherwise original type

        Examples:
            Optional[str] → str
            Union[int, None] → int
            str → str
        """
        if TypeInspector.is_optional(field_type):
            origin, args = TypeInspector.get_origin_and_args(field_type)
            # Return first non-None type
            for arg in args:
                if arg is not type(None):
                    return arg
        return field_type

    @staticmethod
    def is_list_type(field_type: Type) -> bool:
        """
        Check if type is a List.

        Args:
            field_type: Type to check

        Returns:
            True if type is List[T]
        """
        origin, _ = TypeInspector.get_origin_and_args(field_type)
        return origin is list

    @staticmethod
    def is_dict_type(field_type: Type) -> bool:
        """
        Check if type is a Dict.

        Args:
            field_type: Type to check

        Returns:
            True if type is Dict[K, V]
        """
        origin, _ = TypeInspector.get_origin_and_args(field_type)
        return origin is dict

    @staticmethod
    def get_list_element_type(field_type: Type) -> Optional[Type]:
        """
        Get element type from List[T].

        Args:
            field_type: List type to analyze

        Returns:
            Element type T, or None if not a list or no type param
        """
        origin, args = TypeInspector.get_origin_and_args(field_type)
        if origin is list and args:
            return args[0]
        return None

    @staticmethod
    def get_dict_types(field_type: Type) -> Tuple[Optional[Type], Optional[Type]]:
        """
        Get key and value types from Dict[K, V].

        Args:
            field_type: Dict type to analyze

        Returns:
            Tuple of (key_type, value_type), or (None, None) if not a dict
        """
        origin, args = TypeInspector.get_origin_and_args(field_type)
        if origin is dict:
            if len(args) >= 2:
                return args[0], args[1]
            elif len(args) == 1:
                return args[0], Any
        return None, None

    @staticmethod
    def is_nested_list(field_type: Type) -> bool:
        """
        Check if type is List[List[T]].

        Args:
            field_type: Type to check

        Returns:
            True if type is nested list
        """
        if TypeInspector.is_list_type(field_type):
            element_type = TypeInspector.get_list_element_type(field_type)
            if element_type:
                return TypeInspector.is_list_type(element_type)
        return False

    @staticmethod
    def get_nested_list_element_type(field_type: Type) -> Optional[Type]:
        """
        Get inner element type from List[List[T]].

        Args:
            field_type: Nested list type

        Returns:
            Inner element type T, or None if not nested list
        """
        if TypeInspector.is_nested_list(field_type):
            outer_element = TypeInspector.get_list_element_type(field_type)
            if outer_element:
                return TypeInspector.get_list_element_type(outer_element)
        return None
