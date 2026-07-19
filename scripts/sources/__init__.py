# Community Pulse - Source Collectors
# Each module in this package exports a `collect() -> list[dict]` function.
# Register new sources by adding the module here and listing the source
# in the SOURCES registry below.

SOURCES = {
    "reddit": "scripts.sources.reddit",
    "discord": "scripts.sources.discord",
    "github_discussions": "scripts.sources.github_discussions",
}