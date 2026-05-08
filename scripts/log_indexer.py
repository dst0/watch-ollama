
import os
import threading

class LogIndexer:
    def __init__(self, filename):
        self.filename = filename
        self.offsets = [0]
        self.last_pos = 0
        self._f = None
        self._last_size = 0
        self._lock = threading.RLock()
        self.update()

    def _open_file(self):
        # Assumes caller holds self._lock
        if self._f is None:
            if os.path.exists(self.filename):
                try:
                    self._f = open(self.filename, 'rb')
                except Exception:
                    return None
        return self._f

    def update(self):
        with self._lock:
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
                
                # Check if file grew but no newline was found
                # offsets[-1] is the start of the last line.
                # If last_size > offsets[-1], there's content.
                return new_offsets_found or (self._last_size > self.offsets[-1])
            except Exception:
                return False

    def get_line(self, n):
        with self._lock:
            total_lines = len(self)
            if n < 0 or n >= total_lines:
                return ""
            try:
                f = self._open_file()
                if not f: return ""
                
                start = self.offsets[n]
                if n + 1 < len(self.offsets):
                    end = self.offsets[n+1]
                else:
                    end = self._last_size
                    
                f.seek(start)
                return f.read(end - start).decode('utf-8', errors='replace').rstrip('\n').replace('\t', '    ')
            except Exception:
                return ""

    def get_lines(self, start_idx, count):
        with self._lock:
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
        with self._lock:
            if not os.path.exists(self.filename):
                return 0
                
            count = len(self.offsets)
            if self._last_size > self.offsets[-1]:
                return count
            else:
                return count - 1 if count > 0 else 0

    def close(self):
        with self._lock:
            if self._f:
                self._f.close()
                self._f = None
