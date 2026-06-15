from django.core.management.base import BaseCommand
from apps.products.models import Product, Variant
from apps.dashboard.models import StoreSettings

SPECS = {
    'iphone-15': """Display: 6.1" Super Retina XDR OLED
Chip: Apple A16 Bionic
Camera: 48MP Main + 12MP Ultra Wide
Battery: Up to 20 hours video playback
Storage: 128GB / 256GB / 512GB
OS: iOS 17
5G: Yes
Weight: 171g""",

    'iphone-15-pro': """Display: 6.1" Super Retina XDR OLED ProMotion
Chip: Apple A17 Pro
Camera: 48MP Main + 12MP Ultra Wide + 12MP 3x Telephoto
Battery: Up to 23 hours video playback
Storage: 128GB / 256GB / 512GB / 1TB
OS: iOS 17
5G: Yes
Weight: 187g""",

    'samsung-s24': """Display: 6.2" Dynamic AMOLED 2X 120Hz
Chip: Snapdragon 8 Gen 3
Camera: 50MP Main + 12MP Ultra Wide + 10MP 3x Telephoto
Battery: 4000mAh, 25W wired
RAM: 8GB
Storage: 128GB / 256GB
OS: Android 14 / One UI 6.1
5G: Yes""",

    'samsung-s24-ultra': """Display: 6.8" Dynamic AMOLED 2X 120Hz
Chip: Snapdragon 8 Gen 3
Camera: 200MP Main + 12MP Ultra Wide + 50MP 5x Telephoto
Battery: 5000mAh, 45W wired
RAM: 12GB
Storage: 256GB / 512GB / 1TB
S Pen: Included
5G: Yes""",

    'google-pixel-8': """Display: 6.2" OLED 120Hz
Chip: Google Tensor G3
Camera: 50MP Main + 12MP Ultra Wide
Battery: 4575mAh, 27W wired
RAM: 8GB
Storage: 128GB / 256GB
OS: Android 14
5G: Yes""",

    'oneplus-12': """Display: 6.82" LTPO AMOLED 120Hz
Chip: Snapdragon 8 Gen 3
Camera: 50MP Main + 48MP Ultra Wide + 64MP 3x Telephoto
Battery: 5400mAh, 100W wired
RAM: 12GB / 16GB
Storage: 256GB / 512GB
OS: OxygenOS 14
5G: Yes""",

    'macbook-air-m2': """Chip: Apple M2 (8-core CPU, 8-core GPU)
Display: 13.6" Liquid Retina, 2560×1664
RAM: 8GB / 16GB unified memory
Storage: 256GB / 512GB / 1TB SSD
Battery: Up to 18 hours
Ports: 2× USB-C / Thunderbolt, MagSafe 3
Weight: 1.24kg
OS: macOS Sonoma""",

    'macbook-pro-m3': """Chip: Apple M3 Pro (11-core CPU, 14-core GPU)
Display: 14.2" Liquid Retina XDR, ProMotion 120Hz
RAM: 18GB unified memory
Storage: 512GB / 1TB / 2TB SSD
Battery: Up to 18 hours
Ports: 3× Thunderbolt 4, HDMI, SD card, MagSafe 3
Weight: 1.61kg
OS: macOS Sonoma""",

    'dell-xps-15': """Chip: Intel Core i7-13700H
Display: 15.6" OLED 3.5K 60Hz
RAM: 16GB / 32GB DDR5
Storage: 512GB / 1TB NVMe SSD
GPU: NVIDIA GeForce RTX 4060
Battery: 86Wh, up to 13 hours
Ports: 2× Thunderbolt 4, USB-A, SD card
Weight: 1.86kg""",

    'lenovo-thinkpad-x1': """Chip: Intel Core i7-1365U
Display: 14" IPS 2.8K OLED
RAM: 16GB / 32GB LPDDR5
Storage: 512GB / 1TB SSD
Battery: 57Wh, up to 15 hours
Ports: 2× Thunderbolt 4, 2× USB-A, HDMI
Weight: 1.12kg
MIL-SPEC: MIL-STD-810H certified""",

    'hp-spectre-x360': """Chip: Intel Core Ultra 7 155H
Display: 14" 2.8K OLED 120Hz touch
RAM: 16GB / 32GB LPDDR5
Storage: 512GB / 1TB / 2TB SSD
Battery: 68Wh, up to 17 hours
Form Factor: 2-in-1 convertible
Pen: HP Rechargeable MPP2.0 Tilt Pen included
Weight: 1.41kg""",

    'asus-rog-strix': """Chip: Intel Core i9-14900HX
Display: 16" QHD 240Hz IPS
RAM: 16GB / 32GB DDR5
Storage: 1TB / 2TB NVMe SSD
GPU: NVIDIA GeForce RTX 4070
Battery: 90Wh
Cooling: ROG Intelligent Cooling with liquid metal
Weight: 2.5kg""",

    'ipad-air-m2': """Chip: Apple M2
Display: 11" / 13" Liquid Retina
Storage: 128GB / 256GB / 512GB / 1TB
Connectivity: Wi-Fi 6E, optional 5G
Camera: 12MP rear, 12MP front
Battery: Up to 10 hours
Pencil: Apple Pencil Pro compatible
Weight: 462g (11")""",

    'ipad-pro-m4': """Chip: Apple M4
Display: 13" Ultra Retina XDR OLED, ProMotion 120Hz
Storage: 256GB / 512GB / 1TB / 2TB
Connectivity: Wi-Fi 6E, optional 5G
Camera: 12MP rear, 12MP TrueDepth front
Battery: Up to 10 hours
Pencil: Apple Pencil Pro compatible
Weight: 579g""",

    'samsung-tab-s9': """Chip: Snapdragon 8 Gen 2
Display: 12.4" Dynamic AMOLED 2X 120Hz
RAM: 12GB
Storage: 256GB / 512GB
S Pen: Included
Battery: 10090mAh, 45W wired
Connectivity: Wi-Fi 6E, optional 5G
Weight: 581g""",

    'lg-ultragear-27': """Panel: 27" IPS QHD 2560×1440
Refresh Rate: 165Hz
Response Time: 1ms GtG
HDR: HDR10
Ports: 2× HDMI 2.0, 1× DisplayPort 1.4, 4× USB-A
Sync: NVIDIA G-Sync Compatible, AMD FreeSync Premium
Stand: Height / tilt / pivot adjustable
VESA: 100×100mm""",

    'dell-u2723d': """Panel: 27" IPS 4K UHD 3840×2160
Refresh Rate: 60Hz
Color: 100% sRGB, 98% DCI-P3
HDR: HDR400
Ports: Thunderbolt 4, 3× USB-A, HDMI 2.0, DP 1.4
USB Hub: Built-in 4-port
Stand: Height / tilt / swivel / pivot
VESA: 100×100mm""",

    'samsung-odyssey-g7': """Panel: 32" VA Curved 1000R QHD 2560×1440
Refresh Rate: 240Hz
Response Time: 1ms
HDR: HDR600
Ports: 2× HDMI 2.0, 1× DisplayPort 1.4
Sync: NVIDIA G-Sync Compatible, AMD FreeSync Premium Pro
Curvature: 1000R
VESA: 100×100mm""",

    'hp-laserjet-pro': """Type: Monochrome Laser
Print Speed: Up to 40 ppm
Resolution: 1200×1200 dpi
Connectivity: Ethernet, USB
Duplex: Automatic
Paper Capacity: 350 sheets
Monthly Duty Cycle: Up to 80,000 pages
Dimensions: 369×368×254mm""",

    'epson-ecotank-l3250': """Type: Colour Inkjet
Print Speed: 10 ppm (black), 5 ppm (colour)
Resolution: 5760×1440 dpi
Connectivity: Wi-Fi, USB
Tank Capacity: 127ml black, 70ml colour
Page Yield: 4500 black, 7500 colour
Functions: Print, Scan, Copy
Dimensions: 375×347×179mm""",

    'canon-pixma-g3470': """Type: Colour Inkjet MegaTank
Print Speed: 11 ipm (black), 6 ipm (colour)
Resolution: 4800×1200 dpi
Connectivity: Wi-Fi, USB
Tank Yield: 6000 black, 7700 colour
Functions: Print, Scan, Copy
Paper Size: A4, A5, B5, Letter
Dimensions: 445×330×145mm""",

    'logitech-mx-keys': """Switch Type: Scissor mechanism
Backlight: Smart per-key backlight
Connectivity: Bluetooth, USB-C receiver
Multi-device: Up to 3 devices
Battery: Up to 10 days (backlit), 5 months (no backlight)
Compatibility: Windows, macOS, Linux, iOS, Android
Layout: Full-size with numpad
Weight: 810g""",

    'keychron-k2-pro': """Switch Type: Gateron G Pro (Red / Brown / Blue)
Layout: 75% compact (84 keys)
Backlight: RGB per-key
Connectivity: Bluetooth 5.1, USB-C wired
Multi-device: Up to 3 devices
Hot-swap: Yes (5-pin)
Battery: 4000mAh
Frame: Aluminium""",

    'corsair-k100-rgb': """Switch Type: Corsair OPX Optical-Mechanical
Layout: Full-size with macro wheel
Backlight: Per-key RGB 44-zone
Connectivity: USB-A (wired only)
Polling Rate: 4000Hz
Macro Keys: 6 dedicated + iCUE wheel
Wrist Rest: Detachable leatherette
Weight: 1.27kg""",
}

# sale_price for selected variants (variant display_name → sale_price)
SALE_PRICES = {
    # Phones — storage variants
    'iphone-15':              {'128GB': 129000, '256GB': 149000},
    'samsung-s24':     {'128GB': 89000},
    'google-pixel-8':         {'128GB': 79000},
    # Laptops
    'macbook-air-m2':         {'8GB / 256GB': 185000},
    'dell-xps-15':            {'16GB / 512GB': 195000},
    'asus-rog-strix':     {'16GB / 1TB': 215000},
    # Keyboards
    'logitech-mx-keys':       {'Graphite': 12500},
}

DELIVERY_FEES = {
    'phones':    350,
    'laptops':   500,
    'tablets':   400,
    'monitors':  800,
    'printers':  700,
    'keyboards': 300,
}

FEATURED = [
    'macbook-air-m2',
    'iphone-15-pro',
    'samsung-s24-ultra',
    'ipad-pro-m4',
    'dell-u2723d',
    'keychron-k2-pro',
]


class Command(BaseCommand):
    help = 'Seed specs, sale prices, delivery fees and featured flags on existing products'

    def handle(self, *args, **kwargs):
        updated = 0

        for product in Product.objects.select_related('category').prefetch_related('variants'):
            changed = False

            # Specs
            if not product.specs and product.slug in SPECS:
                product.specs = SPECS[product.slug].strip()
                changed = True

            # Delivery fee
            cat_slug = product.category.slug if product.category else ''
            fee = DELIVERY_FEES.get(cat_slug, 350)
            if product.delivery_fee != fee:
                product.delivery_fee = fee
                changed = True

            # is_featured
            featured = product.slug in FEATURED
            if product.is_featured != featured:
                product.is_featured = featured
                changed = True

            if changed:
                product.save(update_fields=['specs', 'delivery_fee', 'is_featured'])
                updated += 1

            # Sale prices on variants
            sale_map = SALE_PRICES.get(product.slug, {})
            for variant in product.variants.all():
                sale = sale_map.get(variant.display_name)
                if sale and variant.sale_price != sale:
                    variant.sale_price = sale
                    variant.save(update_fields=['sale_price'])

        # Ensure StoreSettings has delivery timeframe
        settings = StoreSettings.get()
        if not settings.delivery_timeframe or settings.delivery_timeframe == '2-4 business days':
            settings.delivery_timeframe = '2–4 business days'
            settings.save(update_fields=['delivery_timeframe'])

        self.stdout.write(self.style.SUCCESS(f'Done. Updated {updated} products.'))
