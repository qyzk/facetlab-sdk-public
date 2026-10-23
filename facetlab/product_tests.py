"""Product Tests: multi-arm purchase simulations (FacetLab API v1)."""

import os
import struct
import time
import uuid
from typing import Any, Callable, Dict, Optional, Tuple

import requests

from ._http import check

from .exceptions import FacetLabError, InsufficientFundsError

TERMINAL = {'completed', 'failed', 'cancelled'}
TIMEOUT = (10, 60)           # (connect, read) seconds for API calls
UPLOAD_TIMEOUT = (10, 300)   # image uploads to presigned S3 URLs
# A free test covers a product page test up to this size; larger ones are paid from the balance.
# What one free test covers; larger tests are paid from the balance.
FREE_TEST_LIMITS = {'persona_count': 100, 'variants': 2, 'sessions_per_arm': 5}
MAX_IMAGE_BYTES = 5 * 1024 * 1024
# Per-format pixel caps, as in docker-pipeline shared/image_fit.py (the pipeline rejects larger images).
MAX_PIXELS_JPEG = 80_000_000
MAX_PIXELS_PNG = 45_000_000
MAX_PIXELS_PNG_ALPHA = 25_000_000   # color type 4/6 or a tRNS chunk
MAX_PIXELS_WEBP = 12_000_000        # any WebP (decoder memory is much higher)
_CONTENT_TYPES = {
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.webp': 'image/webp',
}


# JPEG start-of-frame markers (baseline, extended, progressive, lossless; not DHT/JPG/DAC).
_JPEG_SOF = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}


ImageInfo = Tuple[int, int, str, bool]   # width, height, content type, has alpha


def _png_info(data: bytes) -> Optional[ImageInfo]:
    if data[:8] != b'\x89PNG\r\n\x1a\n' or data[12:16] != b'IHDR' or len(data) < 26:
        return None
    width, height = struct.unpack('>II', data[16:24])
    has_alpha = data[25] in (4, 6)
    at = 8   # tRNS must come before the image data; walk the chunks up to IDAT
    while not has_alpha and at + 8 <= len(data):
        kind = data[at + 4:at + 8]
        if kind in (b'IDAT', b'IEND'):
            break
        has_alpha = kind == b'tRNS'
        at += 12 + struct.unpack('>I', data[at:at + 4])[0]
    return width, height, 'image/png', has_alpha


def _jpeg_info(data: bytes) -> Optional[ImageInfo]:
    if data[:2] != b'\xff\xd8':
        return None
    i = 2
    while i < len(data):
        if data[i] != 0xFF:
            return None
        while i < len(data) and data[i] == 0xFF:   # fill bytes
            i += 1
        if i >= len(data):
            return None
        marker = data[i]
        i += 1
        if marker == 0x01 or 0xD0 <= marker <= 0xD8:   # standalone markers
            continue
        if marker in (0xD9, 0xDA) or i + 2 > len(data):   # end of image / scan data before any frame header
            return None
        length = struct.unpack('>H', data[i:i + 2])[0]
        if marker in _JPEG_SOF:
            if i + 7 > len(data):
                return None
            height, width = struct.unpack('>HH', data[i + 3:i + 7])
            return width, height, 'image/jpeg', False
        if length < 2:
            return None
        i += length
    return None


def _webp_info(data: bytes) -> Optional[ImageInfo]:
    if data[:4] != b'RIFF' or data[8:12] != b'WEBP':
        return None
    chunk, payload = data[12:16], data[20:]
    if chunk == b'VP8 ' and len(payload) >= 10 and payload[3:6] == b'\x9d\x01\x2a':
        width, height = struct.unpack('<HH', payload[6:10])
        return width & 0x3FFF, height & 0x3FFF, 'image/webp', False
    if chunk == b'VP8L' and len(payload) >= 5 and payload[:1] == b'\x2f':
        bits = struct.unpack('<I', payload[1:5])[0]
        return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1, 'image/webp', bool((bits >> 28) & 1)
    if chunk == b'VP8X' and len(payload) >= 10:
        return (int.from_bytes(payload[4:7], 'little') + 1, int.from_bytes(payload[7:10], 'little') + 1,
                'image/webp', bool(payload[0] & 0x10))
    return None


def _image_info(path: str) -> Optional[ImageInfo]:
    """Size, content type and alpha from the file header (PNG/JPEG/WebP only), or None if unreadable."""
    with open(path, 'rb') as f:
        data = f.read(256 * 1024)   # JPEG metadata (EXIF, ICC) can precede the frame header
    return _png_info(data) or _jpeg_info(data) or _webp_info(data)


def _image_size(path: str) -> Optional[Tuple[int, int]]:
    info = _image_info(path)
    return (info[0], info[1]) if info else None


def _max_pixels_for(content_type: str, has_alpha: bool) -> int:
    if content_type == 'image/jpeg':
        return MAX_PIXELS_JPEG
    if content_type == 'image/webp':
        return MAX_PIXELS_WEBP
    return MAX_PIXELS_PNG_ALPHA if has_alpha else MAX_PIXELS_PNG


def _validate_image(arm_id: str, path: Optional[str]) -> str:
    """Return the content type for a local image, or raise FacetLabError('invalid_image')."""
    if not path:
        raise FacetLabError(f'No image provided for arm {arm_id}', code='invalid_image')
    content_type = _CONTENT_TYPES.get(os.path.splitext(str(path))[1].lower())
    if not content_type:
        raise FacetLabError(f'Arm {arm_id}: image must be PNG, JPEG or WebP', code='invalid_image')
    try:
        size = os.path.getsize(path)
    except OSError as e:
        raise FacetLabError(f'Arm {arm_id}: cannot read image {path}: {e}', code='invalid_image')
    if size > MAX_IMAGE_BYTES:
        raise FacetLabError(f'Arm {arm_id}: image is {size / 1e6:.1f} MB, over the 5 MB limit. Compress or resize it '
                            '(JPEG or WebP usually helps).', code='invalid_image', details={'bytes': size})
    try:
        info = _image_info(path)
    except OSError as e:
        raise FacetLabError(f'Arm {arm_id}: cannot read image {path}: {e}', code='invalid_image')
    # The header bytes decide the format; it must match the extension (which sets the declared content type).
    if not info or info[2] != content_type or not info[0] or not info[1]:
        raise FacetLabError(f'Arm {arm_id}: not a readable {content_type} image', code='invalid_image')
    width, height, _, has_alpha = info
    limit = _max_pixels_for(content_type, has_alpha)
    if width * height > limit:
        kind = {'image/jpeg': 'JPEG', 'image/webp': 'WebP'}.get(content_type,
                                                              'transparent PNG' if has_alpha else 'PNG')
        raise FacetLabError(f'Arm {arm_id}: image is {width}x{height}, over the {limit // 1_000_000} megapixels '
                            f'allowed for {kind} images', code='invalid_image')
    return content_type


def _arm_ids(arms) -> list:
    ids = []
    for arm in arms:
        arm_id = arm.get('id') if isinstance(arm, dict) else None
        if not arm_id:
            raise FacetLabError("Each arm must be a dict with an 'id'", code='invalid_spec')
        ids.append(arm_id)
    return ids


def _check_no_extra_images(arm_ids, images: Dict[str, str]) -> None:
    extra = sorted(set(images) - set(arm_ids))
    if extra:
        raise FacetLabError(f"Images given for unknown arm id(s): {', '.join(extra)}", code='invalid_image')


class ProductTestsClient:
    def __init__(self, session: requests.Session, base_url: str, put: Optional[Callable] = None,
                 account: Optional[Callable] = None):
        self._s, self._base = session, base_url.rstrip('/')
        self._account = account
        self._put = put or requests.put   # presigned S3 PUTs must not carry the API key

    def _check(self, response) -> Dict[str, Any]:
        return check(response)

    def markets_audience(self, market: str) -> Dict[str, Any]:
        """Filter menu (field -> value -> count) for a market's persona pool."""
        return self._check(self._s.get(f'{self._base}/product-tests/audience', params={'market': market}, timeout=TIMEOUT))

    def estimate(self, spec: Dict[str, Any]) -> Dict[str, Any]:
        """Readiness, data gaps, eligible personas, credits and ETA - creates nothing."""
        return self._check(self._s.post(f'{self._base}/product-tests/estimate', json=spec, timeout=TIMEOUT))

    def create(self, spec: Dict[str, Any], images: Dict[str, str], idempotency_key: Optional[str] = None,
               check_balance: bool = True) -> Dict[str, Any]:
        """Create, upload one image per arm ({'A': 'control.png', 'B': 'treatment.png', ...}) and start.

        With check_balance (default), free tests and the prepaid balance are checked before anything is created:
        InsufficientFundsError when the test cannot be paid. Cost = personas x variants x sessions / 5 x the rate per
        persona per variant. A free test covers up to 100 personas, 2 variants and 5 sessions per variant; a larger
        test is paid from the balance even while free tests remain.
        The start is checked again on the server.
        """
        ids = _arm_ids(spec.get('arms') or [])
        if check_balance and self._account is not None:
            personas = spec.get('persona_count', 25)
            sessions = spec.get('sessions_per_arm', 5)
            variants = len(spec.get('arms') or [])
            units = personas * variants * (sessions / 5)
            self._check_funds(units, fits_free_test=personas <= FREE_TEST_LIMITS['persona_count']
                              and variants <= FREE_TEST_LIMITS['variants']
                              and sessions <= FREE_TEST_LIMITS['sessions_per_arm'])
        _check_no_extra_images(ids, images)
        spec = {**spec, 'arms': [{**arm, 'content_type': _validate_image(arm['id'], images.get(arm['id']))}
                                 for arm in spec['arms']]}
        created = self._check(self._s.post(f'{self._base}/product-tests', json=spec,
                                           headers={'Idempotency-Key': idempotency_key or uuid.uuid4().hex},
                                           timeout=TIMEOUT))
        return self._upload_and_start(created, images)

    def _check_funds(self, units: float, fits_free_test: bool) -> None:
        """A free test (if any is left) covers a free-size test; anything else must be covered by the balance."""
        acct = self._account()
        free = acct.get('free_tests') or {}
        if (fits_free_test and free.get('remaining', 0) > 0) or acct.get('balance') is None:
            return
        cost = round(max(1, -(-units // 1)) * acct['next_test_rate'], 2)
        if acct['balance'] < cost:
            raise InsufficientFundsError(
                f"Insufficient funds: this test costs about ${cost:.2f} and your balance is ${acct['balance']:.2f}. "
                'Top up at https://qyzkdesign.com/dashboard/billing', required=cost, balance=acct['balance'])

    def clone(self, test_id: str, overrides: Dict[str, Any], images: Optional[Dict[str, str]] = None,
              idempotency_key: Optional[str] = None) -> Dict[str, Any]:
        """Re-test. Arms without a new image in `images` reuse the parent's image."""
        images = images or {}
        if images and 'arms' not in overrides:
            raise FacetLabError("overrides['arms'] must list the arms when new images are provided", code='invalid_image')
        if 'arms' in overrides:
            _check_no_extra_images(_arm_ids(overrides['arms']), images)
            arms = []
            for arm in overrides['arms']:
                if arm['id'] in images:
                    arms.append({**arm, 'reuse_parent_image': False,
                                 'content_type': _validate_image(arm['id'], images[arm['id']])})
                else:
                    arms.append({**arm, 'reuse_parent_image': True})
            overrides = {**overrides, 'arms': arms}
        created = self._check(self._s.post(f'{self._base}/product-tests/{test_id}/clone', json=overrides,
                                           headers={'Idempotency-Key': idempotency_key or uuid.uuid4().hex},
                                           timeout=TIMEOUT))
        return self._upload_and_start(created, images)

    def _upload_and_start(self, created: Dict[str, Any], images: Dict[str, str]) -> Dict[str, Any]:
        # upload_urls is present on fresh creates and on replays that are still awaiting_upload.
        for arm, target in (created.get('upload_urls') or {}).items():
            path = images.get(arm)
            if not path:
                raise FacetLabError(f'No image provided for arm {arm}', code='invalid_image')
            with open(path, 'rb') as f:
                r = self._put(target['url'], data=f.read(), headers={'Content-Type': target['content_type']},
                              timeout=UPLOAD_TIMEOUT)
            if not r.ok:
                raise FacetLabError(f'Upload failed for arm {arm}', code='upload_failed',
                                    details={'status': getattr(r, 'status_code', None)})
        # start is idempotent, so it is safe to call on replays as well.
        return self._check(self._s.post(f"{self._base}/product-tests/{created['id']}/start", timeout=TIMEOUT))

    def get(self, test_id: str, include_personas: bool = False) -> Dict[str, Any]:
        params = {'include': 'personas'} if include_personas else None
        return self._check(self._s.get(f'{self._base}/product-tests/{test_id}', params=params, timeout=TIMEOUT))

    def list(self, partner_product_id: Optional[str] = None, limit: int = 20, cursor: Optional[str] = None):
        params = {k: v for k, v in {'partner_product_id': partner_product_id, 'limit': limit, 'cursor': cursor}.items() if v}
        return self._check(self._s.get(f'{self._base}/product-tests', params=params, timeout=TIMEOUT))

    def cancel(self, test_id: str) -> Dict[str, Any]:
        return self._check(self._s.post(f'{self._base}/product-tests/{test_id}/cancel', timeout=TIMEOUT))

    def wait(self, test_id: str, poll_interval: int = 20, timeout: int = 1800) -> Dict[str, Any]:
        deadline = time.time() + timeout
        while True:
            test = self.get(test_id)
            if test['status'] in TERMINAL:
                return test
            remaining = deadline - time.time()
            if remaining <= 0:
                raise FacetLabError(f'Timed out waiting for {test_id}', code='timeout')
            time.sleep(max(0, min(poll_interval, remaining)))
