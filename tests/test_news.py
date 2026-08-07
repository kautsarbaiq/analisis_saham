"""Test lapisan berita & portofolio — mengunci perilaku KEJUJURAN, bukan cuma mekanik.

Yang dikunci:
- klasifikasi kategori memakai kata kunci a-priori (transparan & deterministik);
- mentions() cocok pada ticker ATAU nama emiten, tapi TIDAK pada substring;
- berita ber-simbol yang judulnya tak menyebut emitennya ditandai "?" dan
  relevansinya dipangkas (feed RSS Yahoo sering melampirkan berita nyerempet);
- pemisahan tegas TERUKUR (event aktif dari vol_ratio) vs HEURISTIK;
- portofolio kosong tidak melempar error.
"""
from datetime import datetime, timedelta, timezone

from config import portfolio
from src.engines import news_impact
from src.ingestion import news as news_mod


def _item(title, symbol=None, sentiment=0.0, jam_lalu=1):
    cat, w = news_mod.classify(title)
    return {
        "id": title[:16], "symbol": symbol, "title": title, "url": "https://x/y",
        "source": "Test", "available_at": datetime.now(timezone.utc) - timedelta(hours=jam_lalu),
        "published": "", "event_type": cat, "event_weight": w, "sentiment": sentiment,
    }


# ---------- klasifikasi kategori ----------

def test_classify_kategori_kata_kunci():
    assert news_mod.classify("Apple Q3 earnings beat estimates")[0] == "laba/guidance"
    assert news_mod.classify("XYZ files for bankruptcy protection")[0] == "bangkrut/gagal bayar"
    assert news_mod.classify("Fed signals rate cut in September")[0] == "makro/suku bunga"
    assert news_mod.classify("Sesuatu yang biasa saja")[0] == "umum"


def test_bobot_kategori_terurut_a_priori():
    """Kategori berat (bangkrut) harus berbobot > kategori ringan (rating analis)."""
    assert news_mod.classify("company files chapter 11")[1] > \
           news_mod.classify("analyst upgrade price target")[1]


# ---------- verifikasi keterkaitan ----------

def test_mentions_ticker_dan_nama():
    assert news_mod.mentions("PayPal to Stripe: The Offer Is Too Low", "PYPL")   # nama
    assert news_mod.mentions("NVDA soars on AI demand", "NVDA")                  # ticker
    assert not news_mod.mentions("Circle Internet Group Q2 Earnings", "BLK")     # tak terkait


def test_mentions_tidak_cocok_substring():
    """'AMD' tak boleh cocok di tengah kata (word-boundary)."""
    assert not news_mod.mentions("The pyramid scheme collapsed", "AMD")


# ---------- peringkat & kejujuran label ----------

def test_berita_tak_menyebut_emiten_ditandai_dan_dipangkas():
    kuat = _item("PayPal earnings beat expectations", symbol="PYPL")
    lemah = _item("Circle Internet Group Q2 Earnings Call", symbol="PYPL")
    out = news_impact.rank([kuat, lemah], holdings={"PYPL"}, watch=set(), sector_peers=set())
    by_title = {i["title"]: i for i in out}
    assert by_title[kuat["title"]]["relevansi"] == "dimiliki"
    assert by_title[lemah["title"]]["relevansi"] == "dimiliki?"      # ditandai ragu
    assert by_title[lemah["title"]]["judul_menyebut_emiten"] is False
    assert by_title[kuat["title"]]["impact"] > by_title[lemah["title"]]["impact"]


def test_holdings_diprioritaskan_di_atas_pasar():
    milik = _item("NVDA earnings beat", symbol="NVDA")
    pasar = _item("Fed signals rate cut", symbol=None)
    out = news_impact.rank([pasar, milik], holdings={"NVDA"}, watch=set(), sector_peers=set())
    assert out[0]["symbol"] == "NVDA"


def test_pemisahan_terukur_vs_heuristik():
    """Event aktif HANYA dari vol_ratio (data harga), bukan dari teks."""
    it = _item("Some headline", symbol="AAA", sentiment=0.9)
    ctx = {"AAA": {"vol_ratio": 2.4, "composite": 71.0}}
    r = news_impact.rank([it], holdings={"AAA"}, watch=set(), sector_peers=set(), ctx=ctx)[0]
    assert r["terukur"]["event_aktif"] is True and r["terukur"]["vol_ratio"] == 2.4
    assert r["terukur"]["composite"] == 71.0
    assert r["heuristik"]["sentimen"] == 0.9          # sentimen TIDAK masuk 'terukur'

    r2 = news_impact.rank([it], holdings={"AAA"}, watch=set(), sector_peers=set(),
                          ctx={"AAA": {"vol_ratio": 1.1}})[0]
    assert r2["terukur"]["event_aktif"] is False       # 1.1 < ambang 1.5


def test_tanpa_konteks_harga_event_tidak_diklaim_aktif():
    r = news_impact.rank([_item("Big news", symbol="ZZZ")], holdings=set(), watch=set(),
                         sector_peers=set())[0]
    assert r["terukur"]["event_aktif"] is False and r["terukur"]["vol_ratio"] is None


# ---------- portofolio ----------

def test_portfolio_kosong_aman(tmp_path, monkeypatch):
    monkeypatch.setattr(portfolio, "PORTFOLIO_FILE", tmp_path / "tidak_ada.json")
    assert portfolio.load() == {"holdings": [], "watch": []}
    assert portfolio.symbols() == [] and portfolio.is_empty()


def test_portfolio_rusak_tidak_melempar(tmp_path, monkeypatch):
    f = tmp_path / "portfolio.json"
    f.write_text("{ bukan json valid")
    monkeypatch.setattr(portfolio, "PORTFOLIO_FILE", f)
    assert portfolio.load() == {"holdings": [], "watch": []}


def test_portfolio_normalisasi_dan_urutan(tmp_path, monkeypatch):
    f = tmp_path / "portfolio.json"
    f.write_text('{"holdings": ["nvda", {"symbol": "bbca.jk", "note": "inti"}], '
                 '"watch": ["amd", "NVDA"]}')
    monkeypatch.setattr(portfolio, "PORTFOLIO_FILE", f)
    p = portfolio.load()
    assert [h["symbol"] for h in p["holdings"]] == ["NVDA", "BBCA.JK"]
    assert portfolio.symbols()[:3] == ["NVDA", "BBCA.JK", "AMD"]   # holdings dulu, tanpa duplikat
