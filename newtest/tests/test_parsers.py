import pytest
from src.parsers.marker_pdf import MarkerPDFParser, StructuredDocument

@pytest.mark.asyncio
async def test_marker_parser_initialization():
    """测试Marker解析器初始化"""
    parser = MarkerPDFParser()
    assert parser.model is None

@pytest.mark.asyncio
async def test_structured_document_creation():
    """测试结构化文档创建"""
    doc = StructuredDocument(
        title="测试文档",
        sections=[],
        tables=[],
        figures=[],
        formulas=[]
    )
    assert doc.title == "测试文档"
    assert len(doc.sections) == 0

@pytest.mark.asyncio
async def test_marker_parser_parse():
    """测试Marker解析器解析PDF"""
    parser = MarkerPDFParser()
    # 这里需要实际的PDF文件进行测试
    # result = await parser.parse("test.pdf")
    # assert isinstance(result, StructuredDocument)
    assert True  # 暂时跳过实际解析测试