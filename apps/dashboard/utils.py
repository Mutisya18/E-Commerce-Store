import uuid
from PIL import Image

ALLOWED_IMG_EXTENSIONS = {'jpg', 'jpeg', 'png', 'webp', 'gif'}


def validate_and_rename_image(f):
    """
    Validates f is a real image via Pillow magic-bytes check.
    Returns a safe UUID-based filename with a whitelisted extension.
    Raises ValueError if the file is not a valid image or has a bad extension.
    """
    ext = f.name.rsplit('.', 1)[-1].lower() if '.' in f.name else ''
    if ext not in ALLOWED_IMG_EXTENSIONS:
        raise ValueError(f'File type ".{ext}" is not allowed.')
    try:
        img = Image.open(f)
        img.verify()
    except Exception:
        raise ValueError('File is not a valid image.')
    f.seek(0)
    return f'{uuid.uuid4().hex}.{ext}'
