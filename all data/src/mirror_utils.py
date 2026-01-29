import shared_vars
import common
import os

def squad_choice(status):
    """Get squad image path for status"""
    return f"pictures/CustomAdded1080p/general/squads/{status}.png"

def gift_choice(status):
    """Get starting gift image path for status"""
    return f"pictures/mirror/gifts/{status}.png"

def pack_choice(status):
    """Get pack image path for status"""
    return f"pictures/mirror/packs/status/{status}_pack.png"

def reward_choice(status):
    """Get reward image path for status"""
    return f"pictures/mirror/rewards/{status}_reward.png"

def market_choice(status):
    """Get market image path for status"""
    return f"pictures/mirror/restshop/market/{status}_market.png"

def enhance_shift(status):
    """Return x, y shift for enhancement based on status"""
    return (12, -41)

def get_status_gift_template(status):
    return f"pictures/mirror/restshop/enhance/{status}_enhance.png"

def get_fusion_target_button(status):
    return f"pictures/mirror/restshop/fusion/{status}.png"