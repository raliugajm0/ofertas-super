import json
from datetime import datetime, timedelta

import pytest

import ofertas.config as config
from ofertas.adaptadores import TIENDAS, vtex, walmart
from ofertas.analisis import evaluar
from ofertas.db import DB
from ofertas.modelos import Producto
from ofertas.profeco import importar
from ofertas.units import parse_cantidad, precio_unitario

CFG = config._DEFAULT


@pytest.mark.parametrize("txt,valor,u", [
    ("Aceite Nutrioli 850 ml", 0.85, "l"),
    ("Refresco Coca-Cola 6 pzas de 355 ml", 2.13, "l"),
    ("Arroz SOS 1 kg", 1.0, "kg"),
    ("Atún Dolores 12x140g", 1.68, "kg"),
    ("Papel higiénico Pétalo 32 rollos", 32, "pz"),
    ("Leche Lala Entera 1.5 L", 1.5, "l"),
])
def test_cantidades(txt, valor, u):
    c = parse_cantidad(txt)
    assert c.unidad == u and abs(c.valor - valor) < 0.01


def test_precio_unitario():
    assert precio_unitario(42.5, "Aceite 850 ml") == (50.0, "l")
    assert precio_unitario(10, "sin cantidad") is None


def test_vtex_parsear():
    data = [{"productId": "1", "productName": "Frijol Isadora 430 g", "brand": "Isadora", "link": "/frijol/p",
             "items": [{"itemId": "99", "images": [{"imageUrl": "http://i"}],
                        "sellers": [{"commertialOffer": {"Price": 25.0, "ListPrice": 30.0, "IsAvailable": True}}]}]}]
    p = vtex.parsear(data, "heb", "www.heb.com.mx")[0]
    assert (p.sku, p.precio, p.precio_antes, p.url) == ("99", 25.0, 30.0, "https://www.heb.com.mx/frijol/p")
    assert p.descuento_anunciado == 16.7


def test_walmart_parsear():
    nd = {"props": {"pageProps": {"initialData": {"searchResult": {"itemStacks": [{"items": [
        {"usItemId": "000750", "name": "Café Nescafé Clásico 200 g", "brand": "Nescafé",
         "canonicalUrl": "/ip/cafe/000750", "priceInfo": {"currentPrice": {"price": 139.0}, "wasPrice": {"price": 165.0}},
         "availabilityStatusV2": {"value": "IN_STOCK"}},
        {"usItemId": "x", "name": "Sin precio", "priceInfo": {}}]}]}}}}}
    html = f'<html><script id="__NEXT_DATA__" type="application/json">{json.dumps(nd)}</script></html>'
    ps = walmart.parsear(html, "walmart", "https://www.walmart.com.mx")
    assert len(ps) == 1 and ps[0].precio == 139.0 and ps[0].precio_antes == 165.0
    assert ps[0].url == "https://www.walmart.com.mx/ip/cafe/000750"


def _hist(*precios):
    return [{"precio": p, "precio_antes": None} for p in precios]


def test_veredictos():
    p = Producto("heb", "1", "x", 80.0)
    assert evaluar(p, _hist(100, 100, 98, 102), CFG).calificacion == "excelente"
    assert evaluar(Producto("heb", "1", "x", 99.0), _hist(100, 100, 98), CFG).calificacion == "normal"
    assert evaluar(Producto("heb", "1", "x", 120.0), _hist(100, 100, 98), CFG).calificacion == "cara"
    assert evaluar(p, [], CFG).calificacion == "sin historial"


def test_descuento_simulado():
    # Siempre costó ~100; ahora anuncian "antes 150, hoy 100"
    v = evaluar(Producto("walmart", "1", "x", 100.0, precio_antes=150.0), _hist(100, 101, 99, 100), CFG)
    assert v.sospechosa and len(v.alertas) == 2
    # descuento real: antes coincide con lo observado
    v = evaluar(Producto("walmart", "1", "x", 80.0, precio_antes=100.0), _hist(100, 101, 99, 100), CFG)
    assert not v.sospechosa


def test_db_y_profeco(tmp_path):
    db = DB(tmp_path / "t.db")
    for i, precio in enumerate([30, 31, 29]):
        db.registrar(Producto("heb", "a", "Frijol", precio, fecha=datetime.now() - timedelta(days=i + 1)))
    pid = db.registrar(Producto("heb", "a", "Frijol", 20))
    assert len(db.historial(pid)) == 4
    db.registrar(Producto("heb", "a", "Frijol", 21))  # mismo día: reemplaza
    assert len(db.historial(pid)) == 4

    hoy = datetime.now().strftime("%Y-%m-%d")
    csv = tmp_path / "qqp.csv"
    csv.write_text(
        f'"ACEITE","BOTELLA 1 LT","NUTRIOLI","ACEITES","BASICOS","45.9","{hoy}","WAL-MART","SUPERMERCADO","WALMART VICTORIA","X","TAMAULIPAS","VICTORIA","0","0"\n'
        f'"ACEITE","BOTELLA 1 LT","NUTRIOLI","ACEITES","BASICOS","44.5","{hoy}","BODEGA AURRERA","SUPERMERCADO","BA","X","TAMAULIPAS","VICTORIA","0","0"\n'
        f'"ACEITE","BOTELLA 1 LT","NUTRIOLI","ACEITES","BASICOS","40","{hoy}","WAL-MART","SUPERMERCADO","W","X","NUEVO LEON","MONTERREY","0","0"\n',
        encoding="latin-1")
    assert importar(csv, db, CFG) == 2
    from ofertas.servicio import referencia_profeco
    ref = referencia_profeco("aceite nutrioli", db)
    assert {r["tienda"] for r in ref} == {"profeco:walmart", "profeco:aurrera"}


class Falsa:
    clave = nombre = "heb"

    def __init__(self, cfg):
        pass

    def buscar(self, q, limite=20):
        return [Producto("heb", "1", "Aceite Nutrioli 850 ml", 42.5, 55.0, url="http://x"),
                Producto("heb", "2", "Aceite Patrona 1 l", 39.0)]


def test_web(tmp_path, monkeypatch):
    monkeypatch.setitem(TIENDAS, "heb", Falsa)
    from ofertas.web import crear_app
    db = DB(tmp_path / "w.db")
    app = crear_app(db, {**CFG, "tiendas": ["heb"]}).test_client()
    r = app.get("/?q=aceite")
    html = r.get_data(as_text=True)
    assert r.status_code == 200 and "Aceite Patrona" in html and "$39.00/l" in html
    assert html.index("Patrona") < html.index("Nutrioli")  # orden por precio unitario
    assert app.post("/vigilancia", data={"consulta": "aceite", "objetivo": "40"}).status_code == 302
    r = app.post("/vigilancia/revisar")
    assert "Aceite Patrona" in r.get_data(as_text=True)
    assert app.get("/producto/1").status_code == 200
    assert app.get("/ofertas").status_code == 200


def test_grand_captura(tmp_path, monkeypatch):
    monkeypatch.setitem(TIENDAS, "heb", Falsa)
    from ofertas.web import crear_app
    db = DB(tmp_path / "g.db")
    app = crear_app(db, {**CFG, "tiendas": ["heb", "grand"]}).test_client()
    r = app.post("/captura", data={"tienda": "grand", "nombre": "Aceite Capullo 1 l", "precio": "35.90"})
    assert r.status_code == 302
    html = app.get("/?q=aceite&t=heb&t=grand").get_data(as_text=True)
    assert "GranD" in html and "$35.90/l" in html
    assert html.index("Capullo") < html.index("Patrona")  # GranD más barato por litro
    # si no se selecciona GranD, no aparece
    assert "Capullo" not in app.get("/?q=aceite&t=heb").get_data(as_text=True)


# ---------- Telegram ----------
class _Resp:
    def __init__(self, data, status=200):
        self._d, self.status_code = data, status

    def json(self):
        return self._d


def test_telegram(monkeypatch):
    from ofertas import telegram
    enviados = []

    def post(url, data=None, timeout=None):
        metodo = url.rsplit("/", 1)[-1]
        if "MALO" in url:
            return _Resp({"ok": False, "description": "Unauthorized"}, 401)
        if metodo == "getMe":
            return _Resp({"ok": True, "result": {"username": "MisOfertasBot"}})
        if metodo == "getUpdates":
            return _Resp({"ok": True, "result": [
                {"update_id": 1, "message": {"chat": {"id": 555, "first_name": "Ana"}, "text": "/start"}}]})
        enviados.append(data)
        return _Resp({"ok": True, "result": {}})

    monkeypatch.setattr(telegram.requests, "post", post)
    assert telegram.validar_bot("123:abc") == "MisOfertasBot"
    with pytest.raises(telegram.ErrorTelegram, match="token no es válido"):
        telegram.validar_bot("MALO")
    assert telegram.detectar_chat("123:abc") == ("555", "Ana")
    telegram.enviar("123:abc", "555", "hola")
    assert enviados[-1]["chat_id"] == "555"


# ---------- Programador ----------
def test_programador_cron_y_windows(monkeypatch):
    from ofertas import programador
    lineas = programador.lineas_cron([19, 8, 8])
    assert len(lineas) == 2 and lineas[0].startswith("0 8 * * * ") and "-m ofertas.cli alertas" in lineas[0]
    actual = "MAILTO=x\n30 2 * * * respaldo.sh\n0 7 * * * viejo # ofertas-super\n"
    nuevo = programador.fusionar_cron(actual, lineas)
    assert "respaldo.sh" in nuevo and "viejo" not in nuevo and nuevo.count(programador.MARCA) == 2
    assert programador.MARCA not in programador.fusionar_cron(nuevo, [])
    cmds = programador.comandos_windows([8])
    assert cmds[0][:2] == ["schtasks", "/Create"] and "08:00" in cmds[0] and "OfertasSuper-08" in cmds[0]
    with pytest.raises(ValueError):
        programador.lineas_cron([25])


def test_programar_cron_simulado(monkeypatch):
    from ofertas import programador
    cron = {"t": "30 2 * * * respaldo.sh\n"}
    monkeypatch.setattr(programador.platform, "system", lambda: "Linux")
    monkeypatch.setattr(programador.shutil, "which", lambda x: "/usr/bin/crontab")
    monkeypatch.setattr(programador, "_leer_cron", lambda: cron["t"])
    monkeypatch.setattr(programador, "_escribir_cron", lambda t: cron.update(t=t))
    programador.programar([8, 19])
    assert programador.estado() == ["08:00", "19:00"] and "respaldo.sh" in cron["t"]
    programador.quitar()
    assert programador.estado() == [] and "respaldo.sh" in cron["t"]


def test_web_ajustes(tmp_path, monkeypatch):
    from ofertas import programador, telegram
    from ofertas.web import crear_app
    monkeypatch.setattr(config, "BASE", tmp_path)
    monkeypatch.setattr(config, "LOG_PATH", tmp_path / "alertas.log")
    monkeypatch.setattr(telegram, "validar_bot", lambda t: "MisOfertasBot")
    monkeypatch.setattr(telegram, "detectar_chat", lambda t, espera_seg=0: ("555", "Ana"))
    enviados = []
    monkeypatch.setattr(telegram, "enviar", lambda t, c, m: enviados.append((c, m)))
    horas = {}
    monkeypatch.setattr(programador, "programar", lambda h: horas.update(h=h) or "ok programado")
    monkeypatch.setattr(programador, "estado", lambda: [f"{h:02d}:00" for h in horas.get("h", [])])
    cfg = dict(CFG)
    app = crear_app(DB(tmp_path / "a.db"), cfg).test_client()
    assert "sin conectar" in app.get("/ajustes").get_data(as_text=True)
    assert "@MisOfertasBot" in app.post("/ajustes", data={"accion": "token", "token": "1:a"}).get_data(as_text=True)
    html = app.post("/ajustes", data={"accion": "detectar"}).get_data(as_text=True)
    assert "Conectado con Ana" in html and enviados[-1][0] == "555"
    assert json.loads((tmp_path / "config.json").read_text())["telegram_chat_id"] == "555"
    html = app.post("/ajustes", data={"accion": "programar", "hora": ["8", "19"]}).get_data(as_text=True)
    assert horas["h"] == [8, 19] and "activa: 08:00, 19:00" in html
