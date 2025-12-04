"""Custom argparse action for range-validated append arguments."""

import argparse
from typing import Any, Optional, Sequence, Union


class RangeAppendAction(argparse._AppendAction):  # type: ignore[misc]
    """
    Append action for fields with min/max argument validation.

    Works with RangeAppendHelpFormatter to display metavar cleanly without repetition.

    Standard: -f X Y [X Y ...]
    With this: -f X Y
    """

    def __init__(
        self,
        option_strings: Sequence[str],
        dest: str,
        nargs: Optional[Union[int, str]] = None,
        const: Any = None,
        default: Any = None,
        type: Any = None,
        choices: Optional[Sequence[Any]] = None,
        required: bool = False,
        help: Optional[str] = None,
        metavar: Optional[str] = None,
        **kwargs: Any,
    ):
        """Initialize with custom metavar storage."""
        # Store metavar for custom formatter to use
        self._custom_metavar = metavar

        # Call parent without metavar to avoid argparse's automatic handling
        super().__init__(
            option_strings=option_strings,
            dest=dest,
            nargs=nargs,
            const=const,
            default=default,
            type=type,
            choices=choices,
            required=required,
            help=help,
            metavar=None,  # Don't pass to parent
            **kwargs,
        )
