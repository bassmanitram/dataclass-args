"""Custom argument help formatter for better append action display."""

import argparse
from typing import Any


class RangeAppendHelpFormatter(argparse.HelpFormatter):
    """
    Custom help formatter that improves display of append actions with min/max args.

    Standard argparse with action='append' and nargs='+' shows:
        -f METAVAR [METAVAR ...]

    This formatter detects our RangeAppendAction and shows:
        -f METAVAR

    The help text explains the repetition and argument count separately.
    """

    def _format_args(self, action: argparse.Action, default_metavar: str) -> str:
        """
        Format argument names for usage display.

        Args:
            action: The argparse action being formatted
            default_metavar: Default metavar if none specified

        Returns:
            Formatted argument string for usage line
        """
        # Check if this is our custom append action with range validation
        if (
            hasattr(action, "__class__")
            and action.__class__.__name__ == "RangeAppendAction"
        ):
            # Get the custom metavar
            if hasattr(action, "_custom_metavar") and action._custom_metavar:
                # Show metavar once without repetition
                return action._custom_metavar
            else:
                # Fallback to dest name
                return default_metavar

        # For all other actions, use parent behavior
        return super()._format_args(action, default_metavar)
