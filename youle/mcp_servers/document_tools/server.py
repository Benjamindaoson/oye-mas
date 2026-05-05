"""mcp-document-tools:pptx / xlsx / docx / pdf / pdf_ocr。"""

from __future__ import annotations

from typing import Any

from mcp_servers._shared.http_app import make_app


async def pptx_assemble(arguments: dict[str, Any]) -> dict[str, Any]:
    # TODO(mcp-doc): python-pptx 组装
    return {"oss_ref": "oss://artifacts/output.pptx"}


async def xlsx_assemble(arguments: dict[str, Any]) -> dict[str, Any]:
    # TODO: openpyxl
    return {"oss_ref": "oss://artifacts/output.xlsx"}


async def docx_assemble(arguments: dict[str, Any]) -> dict[str, Any]:
    return {"oss_ref": "oss://artifacts/output.docx"}


async def pdf_extract(arguments: dict[str, Any]) -> dict[str, Any]:
    # TODO: pdfplumber
    return {"text": "[mock] extracted"}


async def pdf_ocr(arguments: dict[str, Any]) -> dict[str, Any]:
    # TODO: tesseract / 阿里云 OCR
    return {"text": "[mock] ocr"}


app = make_app(
    server_name="document-tools",
    tools={
        "pptx_assemble": pptx_assemble,
        "xlsx_assemble": xlsx_assemble,
        "docx_assemble": docx_assemble,
        "pdf_extract": pdf_extract,
        "pdf_ocr": pdf_ocr,
    },
)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=7005)
