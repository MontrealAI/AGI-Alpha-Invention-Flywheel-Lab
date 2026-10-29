"""Read-only HTTPS range adapter; ordinary HDF5 access, not an invention claim."""
import collections
import hashlib
import io
import os
import time
from urllib.parse import urlsplit
import requests


class RangeFile(io.RawIOBase):
    def __init__(self, url, size, max_bytes=100_000_000, block_size=1_048_576, cache_blocks=32, timeout=30):
        parsed = urlsplit(url)
        if parsed.scheme != 'https' or parsed.username or parsed.password or not parsed.hostname:
            raise ValueError('HTTPS_PUBLIC_SOURCE_REQUIRED')
        if type(size) is not int or size <= 0 or type(max_bytes) is not int or max_bytes < 1:
            raise ValueError('INVALID_SIZE_OR_BUDGET')
        if type(block_size) is not int or not 4096 <= block_size <= 16_777_216 or not 1 <= cache_blocks <= 128:
            raise ValueError('INVALID_CACHE_BOUNDS')
        self.url, self.size, self.max_bytes = url, size, max_bytes
        self.block_size, self.cache_blocks, self.timeout = block_size, cache_blocks, timeout
        self.position, self.received_bytes = 0, 0
        self.cache, self.receipts = collections.OrderedDict(), []
        self.session = requests.Session()
        self.session.proxies = requests.utils.get_environ_proxies(url)
        self.session.trust_env = False
        self.session.verify = os.environ.get("REQUESTS_CA_BUNDLE") or os.environ.get("CURL_CA_BUNDLE") or True

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.position

    def seek(self, offset, whence=0):
        if type(offset) is not int or whence not in (0, 1, 2):
            raise ValueError('INVALID_SEEK')
        position = offset if whence == 0 else self.position + offset if whence == 1 else self.size + offset
        if position < 0 or position > self.size:
            raise ValueError('SEEK_OUTSIDE_SOURCE')
        self.position = position
        return position

    def _block(self, number):
        if number in self.cache:
            self.cache.move_to_end(number)
            return self.cache[number]
        start = number * self.block_size
        end = min(start + self.block_size, self.size) - 1
        if self.received_bytes + end - start + 1 > self.max_bytes:
            raise ValueError('NETWORK_BYTE_BUDGET')
        started = time.monotonic()
        response = self.session.get(self.url, headers={'Range': 'bytes=%d-%d' % (start, end)}, stream=True, timeout=self.timeout)
        expected = 'bytes %d-%d/%d' % (start, end, self.size)
        receipt = {'start': start, 'end': end, 'status': response.status_code,
                   'content_range': response.headers.get('Content-Range')}
        if response.status_code != 206 or response.headers.get('Content-Range') != expected:
            response.close()
            self.receipts.append(receipt)
            raise ValueError('RANGE_RESPONSE_REFUSED')
        body = response.raw.read(end - start + 2)
        response.close()
        self.received_bytes += len(body)
        receipt.update({'received_bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest(), 'wall_seconds': time.monotonic()-started})
        self.receipts.append(receipt)
        if len(body) != end - start + 1:
            raise ValueError('RANGE_LENGTH_REFUSED')
        self.cache[number] = body
        while len(self.cache) > self.cache_blocks:
            self.cache.popitem(last=False)
        return body

    def read(self, count=-1):
        if type(count) is not int or count < 0:
            raise ValueError('UNBOUNDED_READ_REFUSED')
        count = min(count, self.size-self.position)
        pieces = []
        while count:
            number, within = divmod(self.position, self.block_size)
            piece = self._block(number)[within:within+count]
            pieces.append(piece)
            self.position += len(piece)
            count -= len(piece)
        return b''.join(pieces)

    def readinto(self, buffer):
        data = self.read(len(buffer))
        buffer[:len(data)] = data
        return len(data)

    def close(self):
        if not self.closed:
            self.session.close()
        super().close()
