import re
import uuid

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage


def sanitize_filename(filename):
    # Remove unwanted characters and replace spaces with underscores
    sanitized_filename = re.sub(r"[^a-zA-Z0-9._-]", "_", filename)
    sanitized_filename = sanitized_filename.strip()  # Remove leading/trailing spaces
    return sanitized_filename


def add_unique_suffix_to_filename(filename: str, length=8):
    # Split the filename into name and extension
    filename_list = filename.rsplit(".", 1)
    # Generate a unique UUID hex
    unique_suffix = str(uuid.uuid4().hex)[:length]
    # Combine the name, unique suffix, and extension
    new_filename = (
        f"{filename_list[0]}_{unique_suffix}.{filename_list[1]}"
        if len(filename_list) > 1
        else f"{filename_list[0]}_{unique_suffix}"
    )
    return new_filename


def save_to_s3(path, file_obj):
    sanitized_filename = add_unique_suffix_to_filename(sanitize_filename(file_obj.name))
    file_path = default_storage.save(f"{path}/{sanitized_filename}", ContentFile(file_obj.read()))
    file_url = settings.MEDIA_URL + file_path
    return file_url