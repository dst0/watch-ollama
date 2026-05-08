
import os

class LogIndexer:
    def __init__(self, filename):
        self.filename = filename
        self.offsets = [0]
        self.last_pos = 0
        self.update()

    def update(self):
        if not os.path.exists(self.filename):
            return False
        
        try:
            current_size = os.path.getsize(self.filename)
            if current_size < self.last_pos:
                # File truncated or rotated
                self.offsets = [0]
                self.last_pos = 0
            elif current_size == self.last_pos:
                return False

            with open(self.filename, 'rb') as f:
                f.seek(self.last_pos)
                chunk_size = 1024 * 1024
                new_offsets_found = False
                while True:
                    start_pos = f.tell()
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    
                    pos = 0
                    while True:
                        next_nl = chunk.find(b'\n', pos)
                        if next_nl == -1:
                            break
                        abs_pos = start_pos + next_nl + 1
                        self.offsets.append(abs_pos)
                        pos = next_nl + 1
                        new_offsets_found = True
                
                self.last_pos = f.tell()
                # If the file doesn't end with a newline, the last segment is still a line.
                if len(self.offsets) > 0 and self.offsets[-1] != self.last_pos:
                    self.offsets.append(self.last_pos)
                    new_offsets_found = True
                return new_offsets_found
        except Exception:
            return False

    def get_line(self, n):
        if n < 0 or n >= len(self.offsets) - 1:
            return ""
        try:
            with open(self.filename, 'rb') as f:
                start = self.offsets[n]
                end = self.offsets[n+1]
                f.seek(start)
                return f.read(end - start).decode('utf-8', errors='replace').rstrip('\n').replace('\t', '    ')
        except Exception:
            return ""

    def get_lines(self, start_idx, count):
        if start_idx < 0:
            start_idx = 0
        end_idx = min(start_idx + count, len(self.offsets) - 1)
        if start_idx >= end_idx:
            return []
        
        lines = []
        try:
            with open(self.filename, 'rb') as f:
                for i in range(start_idx, end_idx):
                    start = self.offsets[i]
                    end = self.offsets[i+1]
                    f.seek(start)
                    lines.append(f.read(end - start).decode('utf-8', errors='replace').rstrip('\n').replace('\t', '    '))
        except Exception:
            pass
        return lines

    def __len__(self):
        return max(0, len(self.offsets) - 1)
