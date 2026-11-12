"""La interfaz se carga en memoria, sin referencias externas y con CSP estricta (RS-12, RS-13)."""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app  # noqa: E402


def test_html_autocontenido_y_con_csp():
    html = app.html_en_memoria()
    assert "default-src 'none'" in html and "connect-src 'none'" in html
    assert not re.search(r"<script[^>]*\ssrc=|<link[^>]*\shref=", html)
    assert "url(\"fonts/" not in html and "data:font/woff2;base64," in html
    assert "window.__catalogo" not in html and "demo" not in html.lower().split("</style>")[1][:2000]
    assert not re.search(r"https?://(?!www\.w3\.org/2000/svg|lucide\.dev)", html.split("<body>", 1)[1])


def test_js_no_usa_innerhtml_con_datos():
    js = open(os.path.join(os.path.dirname(app.__file__), "ui", "app.js"), encoding="utf-8").read()
    usos = re.findall(r"\.innerHTML\s*=\s*([^;]+);", js)
    assert usos == ["ICONOS[nombre] || ICONOS[\"hard-drive\"]"], usos      # solo iconos estáticos
    assert "eval(" not in js and "new Function" not in js and "document.write" not in js
