from multiprocessing import Value

class SharedVars:
    """Shared variables for multiprocessing communication"""
    def __init__(self):
        self.x_offset = Value('i', 0)
        self.y_offset = Value('i', 0)
        self.game_monitor = Value('i', 1)
        self.skip_restshop = Value('b', False)
        self.skip_ego_check = Value('b', False)
        self.skip_ego_fusion = Value('b', False)
        self.skip_sinner_healing = Value('b', False)
        self.skip_ego_enhancing = Value('b', False)
        self.skip_ego_buying = Value('b', False)
        self.prioritize_list_over_status = Value('b', False)
        self.debug_image_matches = Value('b', False)
        self.hard_mode = Value('b', False)
        self.convert_images_to_grayscale = Value('b', True)
        self.reconnection_delay = Value('i', 6)
        self.reconnect_when_internet_reachable = Value('b', False)
        self.good_pc_mode = Value('b', True)
        self.click_delay = Value('f', 0.5)
        self.retry_count = Value('i', 0)
        self.claim_on_defeat = Value('b', False)
        self.pack_refreshes = Value('i', 7)