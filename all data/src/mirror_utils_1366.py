import shared_vars
import common
import os

def squad_choice(status):
    return f"pictures/1366/CustomAdded1080p/general/squads/{status}.png"

def gift_choice(status):
    return f"pictures/1366/mirror/gifts/{status}.png"

def reward_choice(status):
    return f"pictures/1366/mirror/rewards/{status}_reward.png"

def market_choice(status):
    return f"pictures/1366/mirror/restshop/market/{status}_market.png"

def enhance_shift(status):
    return (12, -41)

def get_status_gift_template(status):
    return f"pictures/1366/mirror/restshop/enhance/{status}_enhance.png"

def get_fusion_target_button(status):
    return f"pictures/1366/mirror/restshop/fusion/{status}.png"
