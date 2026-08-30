"""
Constants for CajaClara daemon.
"""

MAX_ATTACHMENT_SIZE_BYTES = 25 * 1024 * 1024  # 25 MB
MAX_BODY_LENGTH_CHARS = 100_000
MAX_SUBJECT_LENGTH = 998
MAX_FILENAME_LENGTH = 255
ALLOWED_ATTACHMENT_EXTENSIONS = {".pdf", ".xml", ".xlsx", ".csv", ".png", ".jpg"}
