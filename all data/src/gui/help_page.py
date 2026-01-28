import os
import customtkinter as ctk
from src.gui.styles import UIStyle
from src.gui.components import CardFrame

def load_help_tab(parent, help_path, version_text, discord_callback):
    """Load and render the help tab"""
    for widget in parent.winfo_children():
        widget.destroy()
        
    scroll_frame = ctk.CTkScrollableFrame(parent, corner_radius=0, fg_color="transparent")
    scroll_frame.pack(fill="both", expand=True)
    
    try:
        if not os.path.exists(help_path):
            ctk.CTkLabel(scroll_frame, text="Help file not found.", font=UIStyle.BODY_FONT).pack(pady=20)
        else:
            with open(help_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                
            blocks = content.split('\n\n')

            intro_card = CardFrame(scroll_frame)
            intro_card.pack(fill="x", padx=10, pady=10)
            ctk.CTkLabel(intro_card, text="General Info", font=UIStyle.SUBHEADER_FONT).pack(anchor="w", padx=20, pady=(15, 10))
            
            current_card = intro_card
            text_labels = []
            
            for block in blocks:
                lines = block.strip().split('\n')
                if not lines: continue
                
                if lines[0].strip().endswith(':'):
                    header = lines[0].strip()[:-1].title()
                    body = '\n'.join(lines[1:])
                    
                    current_card = CardFrame(scroll_frame)
                    current_card.pack(fill="x", padx=10, pady=10)
                    
                    ctk.CTkLabel(current_card, text=header, font=UIStyle.SUBHEADER_FONT).pack(anchor="w", padx=20, pady=(15, 10))
                    if body.strip():
                        label = ctk.CTkLabel(current_card, text=body, font=UIStyle.BODY_FONT, justify="left", text_color=UIStyle.TEXT_SECONDARY_COLOR)
                        label.pack(anchor="w", padx=20, pady=(0, 15))
                        text_labels.append(label)
                else:
                    body = '\n'.join(lines)
                    label = ctk.CTkLabel(current_card, text=body, font=UIStyle.BODY_FONT, justify="left", text_color=UIStyle.TEXT_SECONDARY_COLOR)
                    label.pack(anchor="w", padx=20, pady=(0, 15))
                    text_labels.append(label)

            about_card = CardFrame(scroll_frame)
            about_card.pack(fill="x", padx=10, pady=10)
            ctk.CTkLabel(about_card, text="About", font=UIStyle.SUBHEADER_FONT).pack(anchor="w", padx=20, pady=(15, 10))
            
            about_text = f"WorkerBee {version_text}\nDeveloped by Bonk\n\nAn automated assistant for Limbus Company. Forked from Kryxzort's release added with Harry's fixes.\nUse responsibly."
            ctk.CTkLabel(about_card, text=about_text, font=UIStyle.BODY_FONT, justify="left", text_color=UIStyle.TEXT_SECONDARY_COLOR).pack(anchor="w", padx=20, pady=(0, 15))

    except Exception as e:
        ctk.CTkLabel(scroll_frame, text=f"Error loading help: {e}", font=UIStyle.BODY_FONT).pack(pady=20)

    discord_button = ctk.CTkButton(scroll_frame, text="Join Discord", command=discord_callback, height=UIStyle.BUTTON_HEIGHT, font=UIStyle.BODY_FONT)
    discord_button.pack(pady=20)