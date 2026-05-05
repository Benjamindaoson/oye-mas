"""BGM 素材库种子(Sprint 4 接入)。

读取 infrastructure/seeds/bgm.csv → 上传到 OSS → 写入 bgm_library 表。
V1 必备 mood:warning / sad / hopeful / urgent / cheerful / neutral / serious。
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))


async def main() -> None:
    print("BGM seed pipeline — TODO(Sprint 4)")
    # TODO: 读 CSV → boto3 上传 OSS → INSERT bgm_library


if __name__ == "__main__":
    asyncio.run(main())
