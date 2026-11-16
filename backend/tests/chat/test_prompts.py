"""A prompt version identifies exact bytes, including language-specific renderings."""

import hashlib
from types import ModuleType

import pytest

from app.chat import EXPLANATION_PROMPT_VERSION
from app.chat.prompts import explanation, judge, translation, understanding, verifier
from app.languages.codes import Language

# Retain older entries when introducing a new version.
PROMPT_HASHES = {
    (
        "explanation",
        "constitution-english-v11",
    ): "012f485cdb84604a1d5f8cc5ef153ed19527feda59621062e2f1cd7680aa9495",
    (
        "verifier",
        "constitution-verifier-v1",
    ): "6bde26335e71fefe999831714ff29ab499d207efb7f153d5daf6559c8c1c4446",
    (
        "understanding",
        "reader-understanding-v1",
    ): "96ad3e43c7ed04288a76383e011fd123c8563a796553849a2054190c3a335506",
    (
        "judge",
        "translation-judge-v2",
    ): "7e57e2466c2089910f471238502580c63f43d2603752b779e0d2c25ce5698c86",
    (
        "translation",
        "answer-translation-v2",
    ): "36d7ddb8bcaa4c44f556f0ebb04d781cb541dc3da32d27810479315184c88f87",
}

TRANSLATION_HASHES = {
    (
        "en",
        "answer-translation-v2",
    ): "51efe75112ec59e81c9d31541525ec6ca5020ee6764110f5287a9c9093d3bab0",
    (
        "pcm",
        "answer-translation-v2",
    ): "5e8a4948a2c3468af7c61f4f7fd1626b13df6fefa64f2bd0fd1adce2ba827b7c",
    (
        "yo",
        "answer-translation-v2",
    ): "1723931d42cfa04616696146c3f7ff52e2690e8deee1dcc64b77e2876ecb06f3",
    (
        "ha",
        "answer-translation-v2",
    ): "7b0269ceb5a89767eb95516b97b6ef3af74ec57d5a2adeb2867d31042f7e2cad",
    (
        "ig",
        "answer-translation-v2",
    ): "c080bba3c18c04408f9af628960580ae4cb0259879618fcaeb217a1aa00a271f",
}


@pytest.mark.parametrize(
    "prompt", [explanation, verifier, understanding, translation, judge]
)
def test_prompt_version_pins_exact_text(prompt: ModuleType) -> None:
    name = prompt.__name__.rsplit(".", 1)[-1]
    assert (
        hashlib.sha256(prompt.TEXT.encode()).hexdigest()
        == PROMPT_HASHES[(name, prompt.VERSION)]
    )


@pytest.mark.parametrize("language", list(Language))
def test_translation_version_pins_rendered_text(language: Language) -> None:
    assert (
        hashlib.sha256(translation.render(language).encode()).hexdigest()
        == TRANSLATION_HASHES[(language.value, translation.VERSION)]
    )


def test_explanation_version_remains_public() -> None:
    assert (
        EXPLANATION_PROMPT_VERSION == explanation.VERSION == "constitution-english-v11"
    )
