import os
import cairosvg

# Configuration
COLOR_PRIMARY = "#4dae50"
COLOR_WHITE = "#FFFFFF"
COLOR_BLACK = "#000000"
STROKE = 8
CENTER_X, CENTER_Y = 50, 50
RADIUS = 35

ASSETS_DIR = "docs/website/docs/assets"

def ensure_assets_dir():
    if not os.path.exists(ASSETS_DIR):
        os.makedirs(ASSETS_DIR)
        print(f"Created directory: {ASSETS_DIR}")

def get_glow_def(color):
    return f'''
    <defs>
        <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="1" result="blur" />
            <feComposite in="SourceGraphic" in2="blur" operator="over" />
        </filter>
    </defs>'''

def get_svg_content(width, height, color):
    # Viewbox is always 100x100 for the logic
    path = f'M 27.5,23.4 A 35,35 0 1 0 72.5,23.4 L 50,23.4 L 50,55'
    
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 100 100" fill="none">
    {get_glow_def(color)}
    <path d="{path}" stroke="{color}" stroke-width="{STROKE}" 
          stroke-linecap="round" stroke-linejoin="round" filter="url(#glow)" opacity="0.4" />
    <path d="{path}" stroke="{color}" stroke-width="{STROKE}" 
          stroke-linecap="round" stroke-linejoin="round" />
    </svg>'''

def generate_assets():
    ensure_assets_dir()
    
    # Variants configuration
    # (base_name, color, generate_favicons)
    logo_variants = [
        ("codegreen_logo", COLOR_PRIMARY, True),
        ("codegreen_logo_white", COLOR_WHITE, False),
        ("codegreen_logo_black", COLOR_BLACK, False),
    ]

    for base_name, color, gen_favicons in logo_variants:
        # 1. Master SVG
        svg_content = get_svg_content(100, 100, color)
        scalable_svg = svg_content.replace('width="100" height="100"', '')
        
        svg_path = os.path.join(ASSETS_DIR, f"{base_name}.svg")
        with open(svg_path, "w") as f:
            f.write(scalable_svg)
        print(f"Generated: {svg_path}")

        # 2. PNGs
        if gen_favicons:
            # Full set for the primary brand logo
            png_variants = [
                ("favicon-16x16.png", 16),
                ("favicon-32x32.png", 32),
                ("apple-touch-icon.png", 180),
                ("android-chrome-192x192.png", 192),
                ("android-chrome-512x512.png", 512),
                (f"{base_name}_512.png", 512),
            ]
        else:
            # Just a high-res asset for monochrome variants
            png_variants = [
                (f"{base_name}_512.png", 512),
            ]

        for name, size in png_variants:
            output_path = os.path.join(ASSETS_DIR, name)
            cairosvg.svg2png(bytestring=scalable_svg.encode('utf-8'), write_to=output_path, output_width=size, output_height=size)
            print(f"Generated: {output_path}")

    # 3. ICO (Only for the primary one, usually)
    try:
        from PIL import Image
        ico_path = os.path.join(ASSETS_DIR, "favicon.ico")
        
        # Load the generated PNGs
        img32 = Image.open(os.path.join(ASSETS_DIR, "favicon-32x32.png"))
        img16 = Image.open(os.path.join(ASSETS_DIR, "favicon-16x16.png"))
        
        # Save as ICO
        img32.save(ico_path, sizes=[(32,32), (16,16)])
        print(f"Generated: {ico_path}")
        
    except ImportError:
        print("Warning: Pillow not found, skipping ICO.")
    except Exception as e:
        print(f"Warning: Failed to create ICO: {e}")

if __name__ == "__main__":
    generate_assets()