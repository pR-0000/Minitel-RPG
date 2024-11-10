import subprocess
try:
    from PIL import Image
except ImportError:
    subprocess.check_call(["python", "-m", "pip", "install", "Pillow"])
    from PIL import Image

TILE_WIDTH, TILE_HEIGHT = 8, 9

# Palette Minitel en RGB
minitel_palette = [
    (0, 0, 0),       # Noir
    (255, 0, 0),     # Rouge
    (0, 255, 0),     # Vert
    (255, 255, 0),   # Jaune
    (0, 0, 255),     # Bleu
    (255, 0, 255),   # Magenta
    (0, 255, 255),   # Cyan
    (255, 255, 255)  # Blanc
]

color_codes = {
    (0, 0, 0): ("1B40", "1B50"),
    (255, 0, 0): ("1B41", "1B51"),
    (0, 255, 0): ("1B42", "1B52"),
    (255, 255, 0): ("1B43", "1B53"),
    (0, 0, 255): ("1B44", "1B54"),
    (255, 0, 255): ("1B45", "1B55"),
    (0, 255, 255): ("1B46", "1B56"),
    (255, 255, 255): ("1B47", "1B57")
}

pixel_to_g1_code = {
    "000000": "20", "100000": "21", "010000": "22", "110000": "23",
    "001000": "24", "101000": "25", "011000": "26", "111000": "27",
    "000100": "28", "100100": "29", "010100": "2A", "110100": "2B",
    "001100": "2C", "101100": "2D", "011100": "2E", "111100": "2F",
    "000010": "30", "100010": "31", "010010": "32", "110010": "33",
    "001010": "34", "101010": "35", "011010": "36", "111010": "37",
    "000110": "38", "100110": "39", "010110": "3A", "110110": "3B",
    "001110": "3C", "101110": "3D", "011110": "3E", "111110": "3F",
    "000001": "60", "100001": "61", "010001": "62", "110001": "63",
    "001001": "64", "101001": "65", "011001": "66", "111001": "67",
    "000101": "68", "100101": "69", "010101": "6A", "110101": "6B",
    "001101": "6C", "101101": "6D", "011101": "6E", "111101": "6F",
    "000011": "70", "100011": "71", "010011": "72", "110011": "73",
    "001011": "74", "101011": "75", "011011": "76", "111011": "77",
    "000111": "78", "100111": "79", "010111": "7A", "110111": "7B",
    "001111": "7C", "101111": "7D", "011111": "7E", "111111": "7F"
}

def convert_image_to_minitel_palette(image):
    image = image.convert("RGB")
    pixels = image.load()
    
    for y in range(image.height):
        for x in range(image.width):
            original_color = pixels[x, y]
            closest_color = min(minitel_palette, key=lambda color: sum((color[i] - original_color[i]) ** 2 for i in range(3)))
            pixels[x, y] = closest_color

    return image

def get_tiles(image):
    tiles = []
    img_width, img_height = image.size
    for y in range(0, img_height, TILE_HEIGHT):
        for x in range(0, img_width, TILE_WIDTH):
            tile = image.crop((x, y, x + TILE_WIDTH, y + TILE_HEIGHT))
            tiles.append(tile)
    return tiles

def get_dominant_colors(tile):
    pixels = list(tile.getdata())
    color_count = {}
    for pixel in pixels:
        color_count[pixel] = color_count.get(pixel, 0) + 1

    sorted_colors = sorted(color_count.items(), key=lambda item: item[1], reverse=True)
    background_color = sorted_colors[0][0]
    char_color = sorted_colors[1][0] if len(sorted_colors) > 1 else (255, 255, 255)
    if background_color == char_color:
        char_color = (0, 0, 0) if background_color != (0, 0, 0) else (255, 255, 255)
    return background_color, char_color

def get_g1_code_for_block(pixels, bg_color, fg_color):
    binary_string = ''.join(['1' if pixel == fg_color else '0' for pixel in pixels])
    return pixel_to_g1_code.get(binary_string, "7F")

def generate_tile_codes(tile, background_color, char_color):
    tile_codes = []
    bg_code, fg_code = color_codes[background_color][1], color_codes[char_color][0]
    tile_codes.append([f"{bg_code}{fg_code}"])
    for y in range(0, TILE_HEIGHT, 3):
        row_codes = []
        for x in range(0, TILE_WIDTH, 2):
            pixels = [
                tile.getpixel((x, y)),
                tile.getpixel((x + 1, y)),
                tile.getpixel((x, y + 1)),
                tile.getpixel((x + 1, y + 1)),
                tile.getpixel((x, y + 2)),
                tile.getpixel((x + 1, y + 2))
            ]
            g1_code = get_g1_code_for_block(pixels, background_color, char_color)
            row_codes.append(g1_code)
        tile_codes.append(row_codes)
    return tile_codes

def image_to_G1(filepath):
    image = Image.open(filepath)
    image = convert_image_to_minitel_palette(image)
    tiles = get_tiles(image)
    sprite_mosaic = []
    
    for tile in tiles:
        bg_color, fg_color = get_dominant_colors(tile)
        tile_codes = generate_tile_codes(tile, bg_color, fg_color)
        color_code = [f"{color_codes[bg_color][1]}{color_codes[fg_color][0]}"]
        formatted_tile = [color_code] + [[code for code in row] for row in tile_codes[1:]]
        
        sprite_mosaic.append(formatted_tile)
    
    return sprite_mosaic
