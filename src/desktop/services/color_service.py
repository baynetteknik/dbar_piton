"""Theme & Color Token Service.

Maps semantic color tokens (danger, success, warning, info) to theme colors.
"""



class ColorService:
    """Manages semantic color tokens for conditional visual styling."""

    COLOR_TOKENS: dict[str, dict[str, str]] = {
        "danger": {
            "light": "#f8d7da",
            "main": "#dc3545",
            "dark": "#721c24",
        },
        "success": {
            "light": "#d4edda",
            "main": "#28a745",
            "dark": "#155724",
        },
        "warning": {
            "light": "#fff3cd",
            "main": "#ffc107",
            "dark": "#856404",
        },
        "info": {
            "light": "#d1ecf1",
            "main": "#17a2b8",
            "dark": "#0c5460",
        },
    }

    @classmethod
    def get_token_colors(cls, token_name: str) -> dict[str, str]:
        """Returns background, text and border colors for a token.

        Args:
            token_name: Name of token ('danger', 'success', 'warning', 'info')

        Returns:
            Dictionary with 'light', 'main', 'dark' hex color codes.
        """
        return cls.COLOR_TOKENS.get(
            token_name,
            {"light": "#ffffff", "main": "#6c757d", "dark": "#212529"},
        )
