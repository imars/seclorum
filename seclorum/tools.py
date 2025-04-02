# seclorum/tools.py
import os
from seclorum.models import FileListToolInput, FileListToolOutput

class FileListTool:
    def execute(self, input_data: FileListToolInput) -> FileListToolOutput:
        files = [f for f in os.listdir(input_data.directory) if f.endswith('.py')]
        return FileListToolOutput(files=files)
