# UI Styles and Colors
import platform

class UIStyle:
    FONT_FAMILY = "Segoe UI" if platform.system() == "Windows" else "Roboto"
    
    HEADER_FONT = (FONT_FAMILY, 24, "bold")
    SUBHEADER_FONT = (FONT_FAMILY, 18, "bold")
    SECTION_FONT = (FONT_FAMILY, 16, "bold")
    BODY_FONT = (FONT_FAMILY, 14)
    SMALL_FONT = (FONT_FAMILY, 12)
    
    # Layout
    PADDING_X = 20
    PADDING_Y = 10
    INNER_PADDING = 10
    SIDEBAR_WIDTH = 220
    
    # Colors
    SIDEBAR_COLOR = "#212121"
    MAIN_BG_COLOR = "#1a1a1a"
    CARD_COLOR = "#2b2b2b"
    ACCENT_COLOR = "#3a7ebf"
    HOVER_COLOR = "#326599"
    TEXT_COLOR = "#ffffff"
    TEXT_SECONDARY_COLOR = "#a0a0a0"
    
    # Dimensions
    BUTTON_HEIGHT = 36
    ENTRY_HEIGHT = 32
    CORNER_RADIUS = 8