"""
Constants for CajaClara daemon.
"""

MAX_ATTACHMENT_SIZE_BYTES = 8 * 1024 * 1024  # 8 MB (Hardening Cgroups MemoryMax=45M)
MAX_BODY_LENGTH_CHARS = 100_000
MAX_SUBJECT_LENGTH = 998
MAX_FILENAME_LENGTH = 255
ALLOWED_ATTACHMENT_EXTENSIONS = {".pdf", ".xml", ".xlsx", ".csv", ".png", ".jpg", ".zip"}
