
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
        # Do not call update() here; it will be called by the background thread
        # to ensure instantaneous UI startup.

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
            # Defensive check: ensure n is within current offset bounds
            if n < 0 or n >= len(self.offsets) - 1:
                return ""
            try:
                f = self._open_file()
                if not f: return ""
                
                start = self.offsets[n]
                end = self.offsets[n+1]
                    
                # Ensure end is valid
                if end < start: return ""
                
                f.seek(start)
                return f.read(end - start).decode('utf-8', errors='replace').rstrip('\n').replace('\t', '    ')
            except Exception:
                return ""

    def get_lines(self, start_idx, count):
        with self._lock:
            # Clamp start_idx
            if start_idx < 0:
                start_idx = 0
            
            # Use indexed lines only
            total = len(self)
            end_idx = min(start_idx + count, total)
            
            if start_idx >= end_idx:
                return []
            
            lines = []
            try:
                f = self._open_file()
                if not f: return []
                for i in range(start_idx, end_idx):
                    # Robust bounds check for the offset array
                    if i >= len(self.offsets) - 1:
                        break
                    start = self.offsets[i]
                    end = self.offsets[i+1]
                    
                    if end < start: continue
                        
                    f.seek(start)
                    lines.append(f.read(end - start).decode('utf-8', errors='replace').rstrip('\n').replace('\t', '    '))
            except Exception:
                pass
            return lines

    def __len__(self):
        with self._lock:
            # Return the count of lines we have fully indexed
            return len(self.offsets) - 1 if len(self.offsets) > 0 else 0

    def close(self):
        with self._lock:
            if self._f:
                self._f.close()
                self._f = None
