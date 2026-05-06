import concurrent.futures
import sqlite3
from bs4 import BeautifulSoup
import cloudscraper
import os
import re
import time

DB_DOSYASI = 'filmler.db'
BASE_URL = 'https://www.hdfilmizle.sh'

KATEGORILER = {
    '1':  ('Aile',        '/tur/aile/'),
    '2':  ('Aksiyon',     '/tur/aksiyon/'),
    '3':  ('Animasyon',   '/tur/animasyon-1/'),
    '4':  ('Belgesel',    '/tur/belgesel/'),
    '5':  ('Bilim Kurgu', '/tur/bilim-kurgu/'),
    '6':  ('Dram',        '/tur/dram/'),
    '7':  ('Fantastik',   '/tur/fantastik/'),
    '8':  ('Gerilim',     '/tur/gerilim/'),
    '9':  ('Gizem',       '/tur/gizem/'),
    '10': ('Komedi',      '/tur/komedi/'),
    '11': ('Korku',       '/tur/korku/'),
    '12': ('Macera',      '/tur/macera/'),
    '13': ('Müzik',       '/tur/muzik/'),
    '14': ('Romantik',    '/tur/romantik/'),
    '15': ('Savaş',       '/tur/savas/'),
    '16': ('Suç',         '/tur/suc/'),
    '17': ('Tarih',       '/tur/tarih/'),
    '18': ('TV Film',     '/tur/tv-film/'),
    '19': ('Vahşi Batı',  '/tur/vahsi-bati/'),
    '20': ('Yerli',       '/tur/yerli-film-izle-1/'),
}


scraper = cloudscraper.create_scraper(browser={
    'browser': 'chrome',
    'platform': 'windows',
    'desktop': True
})

def db_baglanti():
    conn = sqlite3.connect(DB_DOSYASI)
    conn.row_factory = sqlite3.Row
    return conn

def db_olustur():
    conn = db_baglanti()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS filmler (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            baslik TEXT,
            afis TEXT,
            orijinal_link TEXT UNIQUE,
            video_linki TEXT,
            kategoriler TEXT,
            imdb TEXT,
            yil TEXT,
            aciklama TEXT
        )
    ''')
    conn.commit()
    conn.close()

def link_var_mi(orijinal_link):
    conn = db_baglanti()
    row = conn.execute('SELECT id FROM filmler WHERE orijinal_link = ?', (orijinal_link,)).fetchone()
    conn.close()
    return row is not None

def kategori_guncelle(orijinal_link, yeni_kategori):
    conn = db_baglanti()
    row = conn.execute('SELECT kategoriler FROM filmler WHERE orijinal_link = ?', (orijinal_link,)).fetchone()
    if row:
        mevcut = row['kategoriler'].split(',') if row['kategoriler'] else []
        if yeni_kategori not in mevcut:
            mevcut.append(yeni_kategori)
            conn.execute('UPDATE filmler SET kategoriler = ? WHERE orijinal_link = ?', (','.join(mevcut), orijinal_link))
            conn.commit()
            conn.close()
            return True
    conn.close()
    return False

def film_kaydet(film):
    conn = db_baglanti()
    try:
        kategoriler = ','.join(film['kategoriler']) if isinstance(film['kategoriler'], list) else film['kategoriler']
        conn.execute('''
            INSERT OR IGNORE INTO filmler (baslik, afis, orijinal_link, video_linki, kategoriler, imdb, yil, aciklama)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (film['baslik'], film['afis'], film['orijinal_link'], film['video_linki'], kategoriler, film['imdb'], film['yil'], film.get('aciklama', '')))
        conn.commit()
    except Exception as e:
        print(f"  ⚠️ Kayıt hatası: {e}")
    finally:
        conn.close()

def film_sayisi():
    conn = db_baglanti()
    sayi = conn.execute('SELECT COUNT(*) FROM filmler').fetchone()[0]
    conn.close()
    return sayi

def imdb_puani_bul(soup):
    try:
        for cls in ['poster-imdb', 'rate', 'rating', 'imdb', 'imdb-rate']:
            el = soup.find(class_=cls)
            if el:
                text = el.get_text(strip=True)
                match = re.search(r'\d+\.?\d*', text)
                if match:
                    return match.group()
    except:
        pass
    return ""

def video_kaynagi_bul(url, kategori_adi):
    try:
        res = scraper.get(url, timeout=15)
        soup = BeautifulSoup(res.content, 'html.parser')

        title = soup.find('title').text.split('|')[0].strip() if soup.find('title') else "Bilinmeyen Başlık"
        
        yil = ""
        yil_etiketi = soup.find('small', string=re.compile(r'Yıl', re.IGNORECASE))
        if yil_etiketi:
            parent_div = yil_etiketi.find_parent('div')
            if parent_div:
                yil_link = parent_div.find('a')
                if yil_link:
                    yil = yil_link.text.strip()
        
        if yil:
            title = title.replace(yil, '').replace('()', '').replace(' - ', '').strip()
        else:
            yil_match = re.search(r'\b(19\d{2}|20\d{2})\b', title)
            if yil_match:
                yil = yil_match.group()
                title = title.replace(yil, '').replace('()', '').replace(' - ', '').strip()

        aciklama = ""
        article = soup.find('article', class_='text-white')
        if article:
            p_tag = article.find('p')
            if p_tag:
                aciklama = p_tag.get_text(strip=True)

        img_meta = soup.find('meta', property='og:image')
        afis = img_meta['content'] if img_meta else ""
        imdb = imdb_puani_bul(soup)

        video_kaynagi = ""
        youtube_fragman = ""

        vpx_iframe = soup.find('iframe', class_='vpx')
        if vpx_iframe and vpx_iframe.get('data-src'):
            video_kaynagi = vpx_iframe.get('data-src')
        else:
            iframes = soup.find_all('iframe')
            for iframe in iframes:
                src = iframe.get('data-src') or iframe.get('src')
                if src:
                    if "youtube" in src.lower():
                        youtube_fragman = src
                    elif any(x in src.lower() for x in ['vidrame', 'vidmoly', 'vidyome', 'moly', 'player', 'embed', 'upstream', 'dizizone', 'ok.ru']):
                        video_kaynagi = src
                        break

        if not video_kaynagi:
            pattern = r'https?://[^\s"\']+(?:vidrame|vidmoly|vidyome|embed|player|moly|upstream)[^\s"\']+'
            matches = re.findall(pattern, str(res.content))
            for match in matches:
                if "youtube" not in match.lower():
                    video_kaynagi = match
                    break

        if not video_kaynagi and youtube_fragman:
            video_kaynagi = youtube_fragman

        if video_kaynagi:
            if video_kaynagi.startswith('//'):
                video_kaynagi = 'https:' + video_kaynagi
            video_kaynagi = video_kaynagi.replace('ap=1', 'ap=0').replace('autoplay=1', 'autoplay=0').replace('autoPlay=1', 'autoPlay=0')

            if "youtube.com/watch?v=" in video_kaynagi:
                video_kaynagi = video_kaynagi.replace("watch?v=", "embed/").split("&")[0]
            elif "youtu.be/" in video_kaynagi:
                video_kaynagi = video_kaynagi.replace("youtu.be/", "youtube.com/embed/").split("?")[0]

        return {
            "baslik": title,
            "afis": afis,
            "video_linki": video_kaynagi,
            "kategoriler": [kategori_adi],
            "imdb": imdb,
            "yil": yil,
            "aciklama": aciklama
        }
    except Exception as e:
        return None

def film_cekici_isci(gorev):
    film_link, baslik, kategori_adi = gorev
    bilgi = video_kaynagi_bul(film_link, kategori_adi)
    if bilgi and bilgi.get('video_linki'):
        print(f"  ✅ {baslik} | Yıl: {bilgi['yil']} | Açıklama: {'Var' if bilgi['aciklama'] else 'Yok'}")
        return {
            "baslik": bilgi["baslik"] or baslik,
            "afis": bilgi["afis"],
            "orijinal_link": film_link,
            "video_linki": bilgi["video_linki"],
            "kategoriler": bilgi["kategoriler"],
            "imdb": bilgi["imdb"],
            "yil": bilgi["yil"],
            "aciklama": bilgi["aciklama"]
        }
    else:
        print(f"  ❌ {baslik} (Video Bulunamadı)")
        return None

def kategori_isle(kategori_adi, kategori_url):
    sayfa = 1
    guncel_url = BASE_URL + kategori_url

    while True:
        url = guncel_url if sayfa == 1 else guncel_url.rstrip('/') + f'/page/{sayfa}/'
        print(f"\n📄 {kategori_adi} - Sayfa {sayfa}")

        try:
            res = scraper.get(url, timeout=15)
            if sayfa == 1:
                guncel_url = res.url

            soup = BeautifulSoup(res.content, 'html.parser')
            kartlar = soup.find_all('a', class_='poster')

            if not kartlar:
                print(f"  ⛔ Sayfa bitti.")
                break

            gorevler = []
            for kart in kartlar:
                film_link = kart.get('href', '')
                if not film_link.startswith('http'):
                    film_link = BASE_URL + film_link
                baslik = kart.get('title', 'Bilinmeyen')

                if link_var_mi(film_link):
                    guncellendi = kategori_guncelle(film_link, kategori_adi)
                    if guncellendi:
                        print(f"  🔄 Kategori eklendi: {baslik} (+{kategori_adi})")
                    else:
                        print(f"  ⏭️ Zaten var: {baslik}")
                else:
                    gorevler.append((film_link, baslik, kategori_adi))

            if gorevler:
                print(f"  🚀 {len(gorevler)} yeni film çekiliyor...")
                with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
                    sonuclar = list(executor.map(film_cekici_isci, gorevler))
                for sonuc in sonuclar:
                    if sonuc:
                        film_kaydet(sonuc)

            print(f"  💾 Sayfa {sayfa} işlendi. Veritabanında Toplam: {film_sayisi()} film var.")
            sayfa += 1
            time.sleep(1)

        except Exception as e:
            print(f"  ❌ Hata: {e}")
            break

def secim_menusu():
    print("\n" + "="*45)
    print("🍿  PATLAMIŞ MISIR VAKTİ - FİLM ÇEKİCİ (V12 FULL)")
    print("="*45)
    print("\nHangi kategoriyi çekmek istersin?\n")
    for no, (adi, _) in KATEGORILER.items():
        print(f"  {no:>2}. {adi}")
    print("\n   0. 🎬 Tüm Kategoriler")
    print("="*45)
    secim = input("\nSeçimin (örn: 3 veya 0): ").strip()
    return secim

def main():
    db_olustur()
    secim = secim_menusu()
    print(f"\n📦 Mevcut: {film_sayisi()} film\n")

    if secim == '0':
        for no, (adi, url) in KATEGORILER.items():
            print(f"\n{'='*45}")
            print(f"📂 Kategori: {adi}")
            print('='*45)
            kategori_isle(adi, url)
    elif secim in KATEGORILER:
        adi, url = KATEGORILER[secim]
        print(f"\n📂 Seçilen: {adi}\n")
        kategori_isle(adi, url)
    else:
        print("❌ Geçersiz seçim.")
        return

    print(f"\n🎉 Bitti! Toplam: {film_sayisi()} film")

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n⛔ Durduruldu. Toplam: {film_sayisi()} film güvenle kaydedildi! 🍿")
