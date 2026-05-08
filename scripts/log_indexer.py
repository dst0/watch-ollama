
import os

class LogIndexer:
    def __init__(self, filename):
        self.filename = filename
        self.offsets = [0]
        self.last_pos = 0
        self._f = None
        self._last_size = 0
        self.update()

    def _open_file(self):
        if self._f is None:
            if os.path.exists(self.filename):
                self._f = open(self.filename, 'rb')
        return self._f

    def update(self):
        if not os.path.exists(self.filename):
            return False
        
        try:
            current_size = os.path.getsize(self.filename)
            if current_size < self.last_pos:
                # File truncated or rotated
                self.offsets = [0]
                self.last_pos = 0
                if self._f:
                    self._f.close()
                    self._f = None
            elif current_size == self._last_size:
                return False

            self._last_size = current_size
            f = self._open_file()
            if not f: return False
            
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
            
            return new_offsets_found or (current_size > self.offsets[-1])
        except Exception:
            return False

    def get_line(self, n):
        total_lines = len(self)
        if n < 0 or n >= total_lines:
            return ""
        try:
            f = self._open_file()
            if not f: return ""
            
            start = self.offsets[n]
            # End is the next offset, or end of file
            if n + 1 < len(self.offsets):
                end = self.offsets[n+1]
            else:
                end = self._last_size
                
            f.seek(start)
            return f.read(end - start).decode('utf-8', errors='replace').rstrip('\n').replace('\t', '    ')
        except Exception:
            return ""

    def get_lines(self, start_idx, count):
        if start_idx < 0:
            start_idx = 0
        total = len(self)
        end_idx = min(start_idx + count, total)
        if start_idx >= end_idx:
            return []
        
        lines = []
        try:
            f = self._open_file()
            if not f: return []
            for i in range(start_idx, end_idx):
                start = self.offsets[i]
                if i + 1 < len(self.offsets):
                    end = self.offsets[i+1]
                else:
                    end = self._last_size
                f.seek(start)
                lines.append(f.read(end - start).decode('utf-8', errors='replace').rstrip('\n').replace('\t', '    '))
        except Exception:
            pass
        return lines

    def __len__(self):
        # Number of lines is number of start offsets
        # If the file doesn't end with a newline, the trailing data is another line.
        # But wait, if offsets=[0, 10] and file size is 10, there are 2 lines?
        # Line 0: 0:10. Line 1: 10:EOF (empty).
        # We usually want to ignore the very last empty line if it follows a newline.
        
        if not os.path.exists(self.filename):
            return 0
            
        count = len(self.offsets)
        if self._last_size > self.offsets[-1]:
            # Trailing data without newline
            return count
        else:
            # Ends with newline
            # If the last character was a newline, offsets[-1] == last_size.
            # Example: "a\n" (size 2). offsets=[0, 2]. count=2.
            # Lines: 0:2 ("a\n"). Line 1: 2:2 ("").
            # Usually we only want Line 0.
            return count - 1 if count > 0 else 0

    def close(self):
        if self._f:
            self._f.close()
            self._f = None
