import pytest

from ssc_codegen.targets.resolver import ResolutionError, resolve
from ssc_codegen.targets.spec import TargetSpec


def test_resolver_accepts_httpx2_for_python() -> None:
    profile = resolve(TargetSpec(lang="python", http_client="httpx2"))
    assert profile.language == "python"
    assert "httpx2" in profile.http_clients


@pytest.mark.parametrize("lang", ["javascript", "js", "go", "rust"])
def test_resolver_rejects_httpx2_for_non_python(lang: str) -> None:
    with pytest.raises(ResolutionError):
        resolve(TargetSpec(lang=lang, http_client="httpx2"))


def test_resolver_rejects_invalid_http_client_for_python() -> None:
    with pytest.raises(ResolutionError, match="httpx2"):
        resolve(TargetSpec(lang="python", http_client="urllib3"))
