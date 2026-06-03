"""文档解析器实现"""
from services.base import BaseParser


class MDParser(BaseParser):
    """Markdown 解析器——直接以 UTF-8 读取 .md 文件

    MVP 阶段只支持 Markdown。后续加 PDFParser / DOCXParser
    只需继承 BaseParser 并实现 parse()，Pipeline 代码不动。
    """

    def parse(self, file_path: str) -> str:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
