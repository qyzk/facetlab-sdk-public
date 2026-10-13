import struct
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from facetlab.product_tests import ProductTestsClient
from facetlab.exceptions import FacetLabError


def _chunk(kind, data):
    return struct.pack('>I', len(data)) + kind + data + b'\x00' * 4


def _png(w, h, color_type=2, extra=b''):
    return (b'\x89PNG\r\n\x1a\n' + _chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, color_type, 0, 0, 0))
            + extra + _chunk(b'IDAT', b'\x00'))


def _jpeg(w, h, sof=0xC0):
    app0 = b'\xff\xe0' + struct.pack('>H', 16) + b'JFIF\x00' + b'\x01\x01\x00\x00\x01\x00\x01\x00\x00'
    sofn = bytes([0xFF, sof]) + struct.pack('>HBHHB', 11, 8, h, w, 1) + b'\x01\x11\x00'
    return b'\xff\xd8' + app0 + b'\xff' + sofn + b'\xff\xda\x00\x02'   # extra 0xFF fill byte before SOF


def _riff(chunk, payload):
    body = b'WEBP' + chunk + struct.pack('<I', len(payload)) + payload
    return b'RIFF' + struct.pack('<I', len(body)) + body


def _webp_vp8(w, h):
    return _riff(b'VP8 ', b'\x00\x00\x00' + b'\x9d\x01\x2a' + struct.pack('<HH', w, h) + b'\x00' * 4)


def _webp_vp8l(w, h, alpha=False):
    bits = (w - 1) | ((h - 1) << 14) | ((1 << 28) if alpha else 0)
    return _riff(b'VP8L', b'\x2f' + struct.pack('<I', bits) + b'\x00' * 4)


def _webp_vp8x(w, h, alpha=False):
    return _riff(b'VP8X', (b'\x10' if alpha else b'\x00') + b'\x00\x00\x00'
                 + (w - 1).to_bytes(3, 'little') + (h - 1).to_bytes(3, 'little'))


def _resp(status, body):
    r = MagicMock(status_code=status, ok=200 <= status < 300)
    r.json.return_value = body
    return r


def test_create_uploads_each_arm_then_starts(tmp_path):
    a, b = tmp_path / 'a.png', tmp_path / 'b.jpg'
    a.write_bytes(_png(10, 10)); b.write_bytes(_jpeg(10, 10))
    session = MagicMock()
    session.post.side_effect = [
        _resp(201, {'id': 'pt_1', 'upload_urls': {'A': {'url': 'https://s3/a', 'content_type': 'image/png'},
                                                  'B': {'url': 'https://s3/b', 'content_type': 'image/jpeg'}}}),
        _resp(200, {'id': 'pt_1', 'status': 'queued'}),
    ]
    put = MagicMock(return_value=_resp(200, {}))
    client = ProductTestsClient(session, 'https://x/api/v1', put=put)
    test = client.create({'name': 'n', 'market': 'tiktok_us', 'arms': [{'id': 'A', 'label': 'a'}, {'id': 'B', 'label': 'b'}]},
                         images={'A': str(a), 'B': str(b)})
    assert test['status'] == 'queued'
    sent = session.post.call_args_list[0].kwargs['json']
    assert [arm['content_type'] for arm in sent['arms']] == ['image/png', 'image/jpeg']
    key = session.post.call_args_list[0].kwargs['headers']['Idempotency-Key']
    assert len(key) == 32
    assert [c.args[0] for c in put.call_args_list] == ['https://s3/a', 'https://s3/b']
    assert session.post.call_args_list[1].args[0] == 'https://x/api/v1/product-tests/pt_1/start'


def test_replay_without_upload_urls_only_starts():
    session = MagicMock()
    session.post.side_effect = [
        _resp(200, {'id': 'pt_1', 'status': 'queued', 'idempotent_replay': True}),
        _resp(200, {'id': 'pt_1', 'status': 'queued'}),
    ]
    put = MagicMock()
    client = ProductTestsClient(session, 'https://x/api/v1', put=put)
    import tempfile, os
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, 'a.png')
        open(p, 'wb').write(_png(10, 10))
        out = client.create({'arms': [{'id': 'A'}]}, images={'A': p}, idempotency_key='k' * 12)
    assert out['status'] == 'queued'
    put.assert_not_called()
    assert session.post.call_args_list[1].args[0].endswith('/product-tests/pt_1/start')


def test_replay_with_upload_urls_uploads_then_starts(tmp_path):
    a = tmp_path / 'a.webp'
    a.write_bytes(_webp_vp8x(10, 10))
    session = MagicMock()
    session.post.side_effect = [
        _resp(200, {'id': 'pt_1', 'idempotent_replay': True,
                    'upload_urls': {'A': {'url': 'https://s3/a', 'content_type': 'image/webp'}}}),
        _resp(200, {'id': 'pt_1', 'status': 'queued'}),
    ]
    put = MagicMock(return_value=_resp(200, {}))
    ProductTestsClient(session, 'https://x', put=put).create({'arms': [{'id': 'A'}]}, images={'A': str(a)})
    assert put.call_count == 1


def test_invalid_image_type_raises_before_http(tmp_path):
    a = tmp_path / 'a.gif'
    a.write_bytes(b'A')
    session = MagicMock()
    with pytest.raises(FacetLabError) as exc:
        ProductTestsClient(session, 'https://x').create({'arms': [{'id': 'A'}]}, images={'A': str(a)})
    assert exc.value.code == 'invalid_image'
    session.post.assert_not_called()


def test_oversize_image_raises_before_http(tmp_path):
    a = tmp_path / 'a.png'
    a.write_bytes(b'0' * (5 * 1024 * 1024 + 1))
    session = MagicMock()
    with pytest.raises(FacetLabError) as exc:
        ProductTestsClient(session, 'https://x').create({'arms': [{'id': 'A'}]}, images={'A': str(a)})
    assert exc.value.code == 'invalid_image'
    session.post.assert_not_called()


def test_missing_image_for_arm_raises_before_http():
    session = MagicMock()
    with pytest.raises(FacetLabError) as exc:
        ProductTestsClient(session, 'https://x').create({'arms': [{'id': 'A'}]}, images={})
    assert exc.value.code == 'invalid_image'
    session.post.assert_not_called()


def test_clone_reuses_parent_image_for_arms_without_new_image():
    session = MagicMock()
    session.post.side_effect = [
        _resp(201, {'id': 'pt_2', 'upload_urls': {}}),
        _resp(200, {'id': 'pt_2', 'status': 'queued'}),
    ]
    client = ProductTestsClient(session, 'https://x')
    client.clone('pt_1', {'arms': [{'id': 'A'}]})
    sent = session.post.call_args_list[0].kwargs['json']
    assert sent['arms'][0]['reuse_parent_image'] is True
    assert 'Idempotency-Key' in session.post.call_args_list[0].kwargs['headers']


def test_errors_raise_with_code():
    session = MagicMock()
    session.post.return_value = _resp(422, {'error': {'code': 'needs_info', 'message': 'Missing price', 'message_zh': '缺少售价'}})
    with pytest.raises(FacetLabError) as exc:
        ProductTestsClient(session, 'https://x').estimate({})
    assert exc.value.code == 'needs_info'


def test_non_json_error_body_raises_with_status():
    r = MagicMock(status_code=502, ok=False)
    r.json.side_effect = ValueError('no json')
    r.text = '<html>Bad Gateway</html>'
    session = MagicMock()
    session.post.return_value = r
    with pytest.raises(FacetLabError) as exc:
        ProductTestsClient(session, 'https://x').estimate({})
    assert '502' in str(exc.value)
    assert exc.value.code == 'http_502'


def test_wait_polls_until_terminal(monkeypatch):
    session = MagicMock()
    session.get.side_effect = [_resp(200, {'status': 'processing'}), _resp(200, {'status': 'completed', 'results': {}})]
    monkeypatch.setattr('time.sleep', lambda s: None)
    assert ProductTestsClient(session, 'https://x').wait('pt_1', poll_interval=0)['status'] == 'completed'


def test_extra_image_ids_rejected_on_create(tmp_path):
    a = tmp_path / 'a.png'; a.write_bytes(_png(10, 10))
    session = MagicMock()
    with pytest.raises(FacetLabError) as exc:
        ProductTestsClient(session, 'https://x').create({'arms': [{'id': 'A'}]}, images={'A': str(a), 'Z': str(a)})
    assert exc.value.code == 'invalid_image' and 'Z' in str(exc.value)
    session.post.assert_not_called()


def test_extra_image_ids_rejected_on_clone(tmp_path):
    a = tmp_path / 'a.png'; a.write_bytes(_png(10, 10))
    session = MagicMock()
    with pytest.raises(FacetLabError) as exc:
        ProductTestsClient(session, 'https://x').clone('pt_1', {'arms': [{'id': 'A'}]}, images={'B': str(a)})
    assert exc.value.code == 'invalid_image'
    session.post.assert_not_called()


def test_clone_images_without_arms_rejected(tmp_path):
    a = tmp_path / 'a.png'; a.write_bytes(_png(10, 10))
    session = MagicMock()
    with pytest.raises(FacetLabError) as exc:
        ProductTestsClient(session, 'https://x').clone('pt_1', {}, images={'A': str(a)})
    assert exc.value.code == 'invalid_image' and 'arms' in str(exc.value)
    session.post.assert_not_called()


def test_arm_without_id_rejected():
    session = MagicMock()
    with pytest.raises(FacetLabError) as exc:
        ProductTestsClient(session, 'https://x').create({'arms': [{'label': 'x'}]}, images={})
    assert 'id' in str(exc.value)
    session.post.assert_not_called()


def test_upload_failure_includes_status(tmp_path):
    a = tmp_path / 'a.png'; a.write_bytes(_png(10, 10))
    session = MagicMock()
    session.post.return_value = _resp(201, {'id': 'pt_1', 'upload_urls': {'A': {'url': 'u', 'content_type': 'image/png'}}})
    put = MagicMock(return_value=_resp(403, {}))
    with pytest.raises(FacetLabError) as exc:
        ProductTestsClient(session, 'https://x', put=put).create({'arms': [{'id': 'A'}]}, images={'A': str(a)})
    assert exc.value.code == 'upload_failed' and exc.value.details == {'status': 403}


def test_wait_sleep_capped_by_remaining_and_times_out(monkeypatch):
    session = MagicMock()
    session.get.return_value = _resp(200, {'status': 'processing'})
    now = [1000.0]
    sleeps = []
    monkeypatch.setattr('time.time', lambda: now[0])
    def fake_sleep(s):
        sleeps.append(s); now[0] += s
    monkeypatch.setattr('time.sleep', fake_sleep)
    with pytest.raises(FacetLabError) as exc:
        ProductTestsClient(session, 'https://x').wait('pt_1', poll_interval=20, timeout=50)
    assert exc.value.code == 'timeout'
    assert sleeps == [20, 20, 10]


def test_default_put_is_requests_put():
    import requests
    assert ProductTestsClient(MagicMock(), 'https://x')._put is requests.put


@pytest.mark.parametrize('base_url, expected', [
    (None, 'https://qyzkdesign.com/api/v1'),
    ('https://qyzkdesign.com/api/sdk', 'https://qyzkdesign.com/api/v1'),
    ('https://qyzkdesign.com/api/sdk/', 'https://qyzkdesign.com/api/v1'),
    ('https://h.example/api', 'https://h.example/api/v1'),
    ('https://h.example', 'https://h.example/api/v1'),
    ('https://h.example/', 'https://h.example/api/v1'),
    ('http://localhost:3000/api/sdk', 'http://localhost:3000/api/v1'),
])
def test_v1_base_derivation(base_url, expected):
    from facetlab.client import FacetLabClient
    assert FacetLabClient(api_key='fl_test', base_url=base_url).product_tests._base == expected


def test_all_requests_have_timeouts(tmp_path, monkeypatch):
    a = tmp_path / 'a.png'
    a.write_bytes(_png(10, 10))
    session = MagicMock()
    session.post.side_effect = [
        _resp(200, {'ready': True}),
        _resp(201, {'id': 'pt_1', 'upload_urls': {'A': {'url': 'https://s3/a', 'content_type': 'image/png'}}}),
        _resp(200, {'id': 'pt_1', 'status': 'queued'}),
        _resp(201, {'id': 'pt_2'}),
        _resp(200, {'id': 'pt_2', 'status': 'queued'}),
        _resp(200, {'id': 'pt_1', 'status': 'cancelled'}),
    ]
    session.get.return_value = _resp(200, {'id': 'pt_1', 'status': 'completed', 'data': []})
    put = MagicMock(return_value=_resp(200, {}))
    client = ProductTestsClient(session, 'https://x/api/v1', put=put)
    spec = {'arms': [{'id': 'A'}]}
    client.estimate(spec)
    client.create(spec, images={'A': str(a)})
    client.clone('pt_1', {})
    client.cancel('pt_1')
    client.get('pt_1')
    client.list()
    client.markets_audience('tiktok_us')
    client.wait('pt_1')
    for call in session.post.call_args_list + session.get.call_args_list:
        assert call.kwargs.get('timeout') == (10, 60), call
    assert put.call_args.kwargs.get('timeout') == (10, 300)


@pytest.mark.parametrize('name, data, size', [
    ('a.png', _png(1920, 31250), (1920, 31250)),
    ('a.jpg', _jpeg(4000, 3000), (4000, 3000)),
    ('a.jpeg', _jpeg(640, 480, sof=0xC2), (640, 480)),   # progressive
    ('a.webp', _webp_vp8(800, 600), (800, 600)),
    ('a.webp', _webp_vp8l(16383, 2), (16383, 2)),
    ('a.webp', _webp_vp8x(7000, 8000), (7000, 8000)),
])
def test_image_dimensions_parsed_from_headers(tmp_path, name, data, size):
    from facetlab.product_tests import _image_size
    p = tmp_path / name
    p.write_bytes(data)
    assert _image_size(str(p)) == size


@pytest.mark.parametrize('name, data, alpha', [
    ('a.png', _png(8, 6), False),
    ('a.png', _png(8, 6, color_type=6), True),
    ('a.png', _png(8, 6, color_type=4), True),
    ('a.png', _png(8, 6, color_type=3, extra=_chunk(b'PLTE', b'\x00' * 3) + _chunk(b'tRNS', b'\x00')), True),
    ('a.png', _png(8, 6, color_type=3, extra=_chunk(b'PLTE', b'\x00' * 3)), False),
    ('a.jpg', _jpeg(8, 6), False),
    ('a.webp', _webp_vp8(8, 6), False),
    ('a.webp', _webp_vp8l(8, 6, alpha=True), True),
    ('a.webp', _webp_vp8l(8, 6), False),
    ('a.webp', _webp_vp8x(8, 6, alpha=True), True),
    ('a.webp', _webp_vp8x(8, 6), False),
])
def test_image_alpha_detected_from_headers(tmp_path, name, data, alpha):
    from facetlab.product_tests import _image_info
    p = tmp_path / name
    p.write_bytes(data)
    assert _image_info(str(p))[3] is alpha


def test_max_pixels_match_pipeline_caps():
    from facetlab.product_tests import _max_pixels_for
    assert _max_pixels_for('image/jpeg', False) == 80_000_000
    assert _max_pixels_for('image/png', False) == 45_000_000
    assert _max_pixels_for('image/png', True) == 25_000_000
    assert _max_pixels_for('image/webp', False) == 12_000_000
    assert _max_pixels_for('image/webp', True) == 12_000_000


@pytest.mark.parametrize('name, data', [
    ('a.jpg', _jpeg(10000, 8000)),
    ('a.png', _png(9000, 5000)),
    ('a.png', _png(5000, 5000, color_type=6)),
    ('a.webp', _webp_vp8x(4000, 3000, alpha=True)),
])
def test_images_within_their_cap_accepted(tmp_path, name, data):
    from facetlab.product_tests import _validate_image
    p = tmp_path / name
    p.write_bytes(data)
    assert _validate_image('A', str(p)).startswith('image/')


@pytest.mark.parametrize('name, data, limit', [
    ('a.jpg', _jpeg(10000, 8001), 80),
    ('a.png', _png(9000, 5001), 45),
    ('a.png', _png(5001, 5000, color_type=6), 25),
    ('a.webp', _webp_vp8x(4000, 3001), 12),
    ('a.webp', _webp_vp8l(4000, 3001), 12),
])
def test_images_over_their_cap_rejected_before_http(tmp_path, name, data, limit):
    p = tmp_path / name
    p.write_bytes(data)
    session = MagicMock()
    with pytest.raises(FacetLabError) as exc:
        ProductTestsClient(session, 'https://x').create({'arms': [{'id': 'A'}]}, images={'A': str(p)})
    assert exc.value.code == 'invalid_image' and f'{limit} megapixels' in str(exc.value)
    session.post.assert_not_called()


@pytest.mark.parametrize('name, data', [
    ('a.png', b'not an image'),
    ('a.png', _jpeg(10, 10)),          # content does not match the extension
    ('a.jpg', b'\xff\xd8\xff\xda'),   # no frame header before scan data
    ('a.webp', b'RIFF\x00\x00\x00\x00WEBPXXXX'),
    ('a.png', b'GIF89a\x0a\x00\x0a\x00'),   # only PNG/JPEG/WebP content is accepted
])
def test_unreadable_or_mismatched_images_rejected(tmp_path, name, data):
    p = tmp_path / name
    p.write_bytes(data)
    session = MagicMock()
    with pytest.raises(FacetLabError) as exc:
        ProductTestsClient(session, 'https://x').create({'arms': [{'id': 'A'}]}, images={'A': str(p)})
    assert exc.value.code == 'invalid_image'
    session.post.assert_not_called()
