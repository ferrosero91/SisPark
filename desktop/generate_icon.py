"""
Genera el icono profesional para SoluPark Desktop.
Genera un .ico válido para Windows System.Drawing (formato BMP interno).
"""
import struct
import io
from pathlib import Path
from PIL import Image, ImageDraw


def create_solupark_icon():
    """Crea un icono profesional para SoluPark."""
    
    output_dir = Path(__file__).parent / 'assets'
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Generar imagen principal a 256x256
    img_256 = render_icon(256)
    
    # Guardar PNG (para uso general)
    png_path = output_dir / 'icon.png'
    img_256.save(str(png_path), format='PNG')
    
    # Crear .ico manualmente con formato BMP (compatible con System.Drawing)
    ico_path = output_dir / 'icon.ico'
    create_ico_file(img_256, ico_path, [16, 32, 48, 64])
    
    print(f"✓ Icono ICO generado: {ico_path}")
    print(f"✓ Icono PNG generado: {png_path}")


def create_ico_file(source_img, output_path, sizes):
    """
    Crea un archivo .ico con formato BMP interno.
    Compatible con System.Drawing de .NET.
    """
    # Generar las imágenes en cada tamaño
    entries = []
    for size in sizes:
        resized = source_img.resize((size, size), Image.LANCZOS)
        # Convertir a BGRA (formato BMP de Windows)
        bmp_data = create_bmp_entry(resized)
        entries.append((size, bmp_data))
    
    # Escribir archivo ICO
    with open(str(output_path), 'wb') as f:
        # ICO Header
        num_images = len(entries)
        f.write(struct.pack('<HHH', 0, 1, num_images))  # Reserved, Type=1(ICO), Count
        
        # Calcular offsets
        header_size = 6 + (num_images * 16)  # ICO header + directory entries
        offset = header_size
        
        # Directory entries
        for size, bmp_data in entries:
            w = size if size < 256 else 0
            h = size if size < 256 else 0
            f.write(struct.pack('<BBBBHHII',
                w,              # Width (0 = 256)
                h,              # Height (0 = 256)
                0,              # Color palette
                0,              # Reserved
                1,              # Color planes
                32,             # Bits per pixel
                len(bmp_data),  # Size of image data
                offset          # Offset to image data
            ))
            offset += len(bmp_data)
        
        # Image data
        for size, bmp_data in entries:
            f.write(bmp_data)


def create_bmp_entry(img):
    """Crea los datos BMP para una entrada del ICO."""
    width, height = img.size
    img = img.convert('RGBA')
    
    # BMP Info Header (BITMAPINFOHEADER)
    header = struct.pack('<IiiHHIIiiII',
        40,             # Header size
        width,          # Width
        height * 2,     # Height (doubled for ICO: image + mask)
        1,              # Planes
        32,             # Bits per pixel
        0,              # Compression (none)
        0,              # Image size (can be 0 for uncompressed)
        0,              # X pixels per meter
        0,              # Y pixels per meter
        0,              # Colors used
        0               # Important colors
    )
    
    # Pixel data (bottom-up, BGRA)
    pixels = bytearray()
    for y in range(height - 1, -1, -1):  # Bottom to top
        for x in range(width):
            r, g, b, a = img.getpixel((x, y))
            pixels.extend([b, g, r, a])  # BGRA order
    
    # AND mask (1-bit transparency mask, all zeros since we use alpha)
    mask_row_size = ((width + 31) // 32) * 4  # Padded to 4 bytes
    mask = bytes(mask_row_size * height)
    
    return header + bytes(pixels) + mask


def render_icon(size):
    """Renderiza el icono a un tamaño dado con supersampling 4x."""
    
    rs = size * 4  # Render size (4x para antialiasing)
    img = Image.new('RGBA', (rs, rs), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Colores SoluPark
    bg_dark = (15, 23, 42, 255)       # slate-900
    blue_main = (14, 165, 233, 255)   # sky-500
    blue_light = (56, 189, 248, 255)  # sky-400
    
    padding = int(rs * 0.04)
    radius = int(rs * 0.16)
    
    # Fondo redondeado
    rounded_rect(draw, padding, padding, rs - padding, rs - padding, radius, bg_dark)
    
    # === Letra P estilizada ===
    cx = rs / 2
    cy = rs / 2
    
    stroke_w = rs * 0.09
    p_h = rs * 0.52
    p_w = rs * 0.40
    
    p_left = cx - p_w * 0.5
    p_top = cy - p_h * 0.5
    p_bottom = cy + p_h * 0.5
    
    # Barra vertical
    rounded_rect(
        draw,
        int(p_left), int(p_top),
        int(p_left + stroke_w), int(p_bottom),
        int(stroke_w * 0.35),
        blue_main
    )
    
    # Cabeza de la P (rectángulo redondeado hueco)
    head_left = int(p_left + stroke_w * 0.4)
    head_top = int(p_top)
    head_right = int(p_left + p_w + rs * 0.05)
    head_bottom = int(cy + rs * 0.02)
    head_radius = int((head_bottom - head_top) * 0.42)
    
    # Exterior de la cabeza
    rounded_rect(draw, head_left, head_top, head_right, head_bottom, head_radius, blue_light)
    
    # Interior hueco
    margin = int(stroke_w)
    inner_radius = int((head_bottom - head_top - 2 * margin) * 0.35)
    rounded_rect(
        draw,
        head_left + margin, head_top + margin,
        head_right - margin, head_bottom - margin,
        inner_radius, bg_dark
    )
    
    # Re-dibujar barra vertical encima
    rounded_rect(
        draw,
        int(p_left), int(p_top),
        int(p_left + stroke_w), int(p_bottom),
        int(stroke_w * 0.35),
        blue_main
    )
    
    # Línea decorativa inferior
    line_y = int(p_bottom + rs * 0.07)
    line_h = max(4, int(rs * 0.022))
    line_left = int(cx - rs * 0.18)
    line_right = int(cx + rs * 0.18)
    rounded_rect(draw, line_left, line_y, line_right, line_y + line_h, line_h // 2, blue_main)
    
    # Reducir con antialiasing
    img = img.resize((size, size), Image.LANCZOS)
    
    return img


def rounded_rect(draw, x1, y1, x2, y2, radius, color):
    """Dibuja un rectángulo con esquinas redondeadas."""
    w = x2 - x1
    h = y2 - y1
    max_r = min(w // 2, h // 2)
    radius = min(radius, max(0, max_r))
    
    if radius <= 0:
        draw.rectangle([x1, y1, x2, y2], fill=color)
        return
    
    d = radius * 2
    draw.ellipse([x1, y1, x1 + d, y1 + d], fill=color)
    draw.ellipse([x2 - d, y1, x2, y1 + d], fill=color)
    draw.ellipse([x1, y2 - d, x1 + d, y2], fill=color)
    draw.ellipse([x2 - d, y2 - d, x2, y2], fill=color)
    draw.rectangle([x1 + radius, y1, x2 - radius, y2], fill=color)
    draw.rectangle([x1, y1 + radius, x2, y2 - radius], fill=color)


if __name__ == '__main__':
    create_solupark_icon()
