from careerpilot.mcp.catalog import McpToolCatalog
from careerpilot.mcp.models import McpToolDescriptor


def _tool(
    name: str,
    description: str,
    *,
    server: str = "career",
    title: str | None = None,
) -> McpToolDescriptor:
    return McpToolDescriptor(
        server_name=server,
        tool_name=name,
        title=title,
        description=description,
        input_schema={"type": "object", "properties": {}},
        read_only=True,
        destructive=False,
        server_description="Career workspace tools",
    )


def test_catalog_prioritizes_explicit_name_then_description_match() -> None:
    descriptors = (
        _tool("search_jobs", "Find current roles"),
        _tool("read_resume", "Read a resume", title="Resume reader"),
        _tool("list_files", "List resume files"),
    )

    selected = McpToolCatalog().select("Please use read_resume for my resume", descriptors)

    assert [item.tool_name for item in selected] == [
        "read_resume",
        "list_files",
    ]


def test_catalog_is_deterministic_caps_results_and_deduplicates_names() -> None:
    descriptors = tuple(
        _tool(f"search_jobs_{index:02d}", "Search career jobs") for index in range(12)
    ) + (_tool("search_jobs_00", "Duplicate search tool"),)

    selected = McpToolCatalog().select("search career jobs", descriptors)

    assert len(selected) == 8
    assert len({item.namespaced_name for item in selected}) == 8
    assert [item.namespaced_name for item in selected] == sorted(
        item.namespaced_name for item in selected
    )


def test_catalog_returns_none_for_empty_or_unrelated_query() -> None:
    descriptors = (_tool("read_resume", "Read an approved resume"),)
    catalog = McpToolCatalog()

    assert catalog.select("", descriptors) == ()
    assert catalog.select("weather in Paris", descriptors) == ()


def test_catalog_keeps_servers_namespaced() -> None:
    descriptors = (
        _tool("search", "Search jobs", server="jobs"),
        _tool("search", "Search interview preparation", server="preparation"),
    )

    selected = McpToolCatalog().select("search", descriptors)

    assert [item.namespaced_name for item in selected] == [
        "mcp__jobs__search",
        "mcp__preparation__search",
    ]


def test_catalog_matches_overlapping_chinese_phrases() -> None:
    descriptors = (
        _tool("search_jobs", "搜索当前产品经理岗位"),
        _tool("read_resume", "读取本地简历"),
    )

    selected = McpToolCatalog().select("帮我搜索最新产品岗位", descriptors)

    assert [item.tool_name for item in selected] == ["search_jobs"]
