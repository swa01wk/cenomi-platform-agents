import json
from pathlib import Path
from typing import Dict, Any

class ToolRegistryStore:
    def __init__(self, file_path: str = Path(__file__).parent.parent.parent / r"tools\registry\tool_registry.json"):
        self.file_path = Path(file_path)

        if not self.file_path.exists():
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            self._write({"tools": []})

    def load(self) -> Dict[str, Any]:
        with self.file_path.open("r", encoding="utf-8") as f:
            return json.load(f)

    def save(self, data: Dict[str, Any]) -> None:
        self._write(data)

    def _write(self, data: Dict[str, Any]) -> None:
        with self.file_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    store = ToolRegistryStore()
    registry_data = store.load()
    print("Loaded tool registry data:", registry_data)

    # Test saving function
    test_data = {
        "tools": [
            {
                "id": "test_tool",
                "type": "prebuilt",
                "name": "Test Tool",
                "description": "A tool for testing save functionality.",
                "input_schema": {},
                "output_schema": {},
                "metadata": {
                    "created_by": "user",
                    "created_at": "2026-01-10T12:00:00Z"
                }
            }
        ]
    }
    store.save(test_data)
    print("Saved test data.")

    # Reload to verify
    loaded = store.load()
    print("Reloaded data:", loaded)