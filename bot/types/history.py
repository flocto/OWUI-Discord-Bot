from typing import Literal, TypeAlias, TypedDict


class TextPart(TypedDict):
    type: Literal["text"]
    text: str


class ImageURL(TypedDict):
    url: str


class ImagePart(TypedDict):
    type: Literal["image_url"]
    image_url: ImageURL


ContentPart: TypeAlias = TextPart | ImagePart


class ConversationMessage(TypedDict):
    role: Literal["user", "assistant"]
    content: str | list[ContentPart]
