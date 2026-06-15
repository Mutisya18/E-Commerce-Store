import re
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

ICONS = [
    "arrow-clockwise", "arrow-left", "arrow-up-right", "arrows-clockwise",
    "bell", "buildings", "caret-left", "caret-right", "chart-bar",
    "chat-circle", "check", "check-circle", "clipboard-text", "credit-card",
    "currency-dollar", "device-mobile", "device-tablet", "download-simple",
    "envelope-simple", "eye", "fire", "gear", "grid-four", "headphones",
    "house", "house-line", "info", "instagram-logo", "keyboard", "laptop",
    "list", "lock", "magnifying-glass", "map-pin", "monitor", "package",
    "pencil-simple", "phone", "plant", "plug", "rocket-launch", "rows",
    "shopping-bag-open", "shopping-cart", "sign-out", "siren", "squares-four",
    "star", "star-regular", "tiktok-logo", "trash", "upload-simple",
    "user-circle", "users", "warning", "watch", "whatsapp-logo", "x",
    "x-circle", "x-logo",
]

# star-regular is an alias for star (regular weight = outline)
ALIASES = {"star-regular": "star"}


class Command(BaseCommand):
    help = "Generate static/icons/sprite.svg from @phosphor-icons/core"

    def handle(self, *args, **options):
        base_dir = settings.BASE_DIR
        assets_dir = base_dir / "node_modules" / "@phosphor-icons" / "core" / "assets" / "regular"
        out_path = Path(settings.STATICFILES_DIRS[0]) / "icons" / "sprite.svg"
        out_path.parent.mkdir(parents=True, exist_ok=True)

        symbols = []
        missing = []

        for name in ICONS:
            src_name = ALIASES.get(name, name)
            svg_file = assets_dir / f"{src_name}.svg"
            if not svg_file.exists():
                missing.append(name)
                continue
            raw = svg_file.read_text()
            viewbox = re.search(r'viewBox="([^"]+)"', raw)
            inner = re.sub(r"</?svg[^>]*>", "", raw).strip()
            vb = f'viewBox="{viewbox.group(1)}"' if viewbox else 'viewBox="0 0 256 256"'
            symbols.append(f'  <symbol id="ph-{name}" {vb}>{inner}</symbol>')

        out_path.write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" style="display:none">\n'
            + "\n".join(symbols)
            + "\n</svg>\n"
        )

        self.stdout.write(self.style.SUCCESS(f"Wrote {len(symbols)} symbols to {out_path}"))
        for name in missing:
            self.stdout.write(self.style.WARNING(f"  Missing: {name}"))
