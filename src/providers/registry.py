from __future__ import annotations

from importlib import import_module

from src.providers.base import ProviderAdapter


PROVIDER_MODULES = {
	"tabelog": "src.providers.tabelog",
	"example_provider": "src.providers.example_provider",
}

_provider_cache: dict[str, ProviderAdapter] = {}


def list_providers() -> list[str]:
	return sorted(PROVIDER_MODULES)


def get_provider(name: str) -> ProviderAdapter:
	if name in _provider_cache:
		return _provider_cache[name]

	module_path = PROVIDER_MODULES.get(name)
	if module_path is None:
		raise KeyError(f"Unknown provider: {name}")

	module = import_module(module_path)
	provider = module.get_provider()
	if provider.name != name:
		raise ValueError(
			f"Provider registry mismatch: requested {name!r}, got {provider.name!r}"
		)

	_provider_cache[name] = provider
	return provider