import tempfile
from pathlib import Path

from ..log import logger
from openai.types.file_object import FileObject
from openwebui_client import OpenWebUIClient

ACCEPTED_MIME_TYPES = {
    # PDF
    "application/pdf",
    # Spreadsheets
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel",
    "text/csv", "application/csv", "text/tsv", "text/x-iif", "application/x-iif",
    "application/vnd.google-apps.spreadsheet",
    # Rich documents
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword", "application/rtf", "text/rtf",
    "application/vnd.oasis.opendocument.text",
    "application/vnd.apple.pages", "application/vnd.google-apps.document",
    "application/vnd.apple.iwork",
    # Presentations
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/vnd.ms-powerpoint", "application/vnd.apple.keynote",
    "application/vnd.google-apps.presentation",
    # Text and code
    "application/javascript", "application/typescript", "text/xml",
    "text/x-shellscript", "text/x-rst", "text/x-makefile", "text/x-lisp",
    "text/x-asm", "text/vbscript", "text/css", "message/rfc822",
    "application/x-sql", "application/x-scala", "application/x-rust",
    "application/x-powershell", "text/x-diff", "text/x-patch", "application/x-patch",
    "text/plain", "text/markdown", "text/x-java", "text/x-script.python",
    "text/x-python", "text/x-c", "text/x-csrc", "text/x-c++", "text/x-golang", "text/html",
    "text/x-php", "application/x-php", "application/x-httpd-php",
    "application/x-httpd-php-source", "text/x-ruby", "text/x-sh", "text/x-bash",
    "application/x-bash", "text/x-zsh", "text/x-tex", "text/x-csharp",
    "application/json", "text/x-typescript", "text/javascript", "text/x-go",
    "text/x-rust", "text/x-scala", "text/x-kotlin", "text/x-swift", "text/x-lua",
    "text/x-r", "text/x-R", "text/x-julia", "text/x-perl", "text/x-objectivec",
    "text/x-objectivec++", "text/x-erlang", "text/x-elixir", "text/x-haskell",
    "text/x-clojure", "text/x-groovy", "text/x-dart", "text/x-awk", "application/x-awk",
    "text/jsx", "text/tsx", "text/x-handlebars", "text/x-mustache", "text/x-ejs",
    "text/x-jinja2", "text/x-liquid", "text/x-erb", "text/x-twig", "text/x-pug",
    "text/x-jade", "text/x-tmpl", "text/x-cmake", "text/x-dockerfile",
    "text/x-gradle", "text/x-ini", "text/x-properties", "text/x-protobuf",
    "application/x-protobuf", "text/x-sql", "text/x-sass", "text/x-scss",
    "text/x-less", "text/x-hcl", "text/x-terraform", "application/x-terraform",
    "text/x-toml", "application/x-toml", "application/graphql",
    "application/x-graphql", "text/x-graphql", "application/x-ndjson",
    "application/json5", "application/x-json5", "text/x-yaml", "application/toml",
    "application/x-yaml", "application/yaml", "text/x-astro", "text/srt",
    "application/x-subrip", "text/x-subrip", "text/vtt", "text/x-vcard",
    "text/calendar",
}

# Single temp directory shared for the lifetime of the bot process
TMP_DIR = Path(tempfile.mkdtemp(prefix="bot_"))


def upload_attachment(client: OpenWebUIClient, filename: str, data: bytes, content_type: str) -> FileObject:
    """
    Upload a file attachment to OpenWebUI via the shared temp directory.
    Returns the file object on success, or None if the MIME type is not accepted.
    """
    mime = content_type.split(";")[0].strip() if content_type else "application/octet-stream"

    if mime not in ACCEPTED_MIME_TYPES:
        logger.warning(
            f"Attachment '{filename}' has unsupported MIME type '{mime}'. Assuming octet-stream!")
        mime = "application/octet-stream"

    tmp_path = TMP_DIR / filename
    try:
        tmp_path.write_bytes(data)
        return client.files.from_path(tmp_path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()
