class SpreadSheetsClient:
    def __init__(self) -> None:
        ...

    async def get_cell(self) -> None:
        ...

    async def upsert_cell(self) -> None:
        ...

    async def _worksheet(self) -> None:
        ...


class FileSystemClient:
    def __init__(self) -> None:
        ...

    async def create_file(self) -> None:
        ...