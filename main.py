import concurrent.futures
import requests
from bs4 import BeautifulSoup
import cloudscraper
import json
import os
import re
import time

VERI_DOSYASI = 'filmler.json'
BASE_URL = 'https://www.hdfilmizle.so'

KATEGORILER = {
    'Aile':        '/tur/aile/',
    'Aksiyon':     '/tur/aksiyon/',
    'Animasyon':   '/tur/animasyon-1/',
    'Belgesel':    '/tur/belgesel/',
    'Bilim Kurgu': '/tur/bilim-kurgu/',
    'Dram':        '/tur/dram/',
    'Fantastik':   '/tur/fantastik/',
    'Gerilim':     '/tur/gerilim/',
    'Gizem':       '/tur/gizem/',
    'Komedi':      '/tur/komedi/',
    'Korku':       '/tur/korku/',
    'Macera':      '/tur/macera/',
    'Müzik':       '/tur/muzik/',
    'Romantik':    '/tur/romantik/',
    'Savaş':       '/tur/savas/',
    'Suç':         '/tur/suc/',
    'Tarih':       '/tur/tarih/',
    'TV Film':     '/tur/tv-film/',
    'Vahşi Batı':  '/tur/vahsi-bati/',
    'Yerli':       '/tur/yerli/',
}

scraper = cloudscraper.create_scraper(browser={
    'browser': 'chrome',
    'platform': 'windows',
    'desktop': True
})

def filmleri_oku():
    if not os.path.exists(VERI_DOSYASI):
        return []
    with open(VERI_DOSYASI, 'r', encoding='utf-8') as f:
        return json.load(f)

def filmleri_yaz(filmler_listesi):
    with open(VERI_DOSYASI, 'w', encoding='utf-8') as f:
        json.dump(filmler_listesi, f, ensure_ascii=False, indent=2)
    print(f"💾 Kaydedildi. Toplam: {len(filmler_listesi)} film")

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
        img_meta = soup.find('meta', property='og:image')
        afis = img_meta['content'] if img_meta else ""
        imdb = imdb_puani_bul(soup)

        video_kaynagi = ""
        vpx_iframe = soup.find('iframe', class_='vpx')
        if vpx_iframe and vpx_iframe.get('data-src'):
            video_kaynagi = vpx_iframe.get('data-src')
        else:
            iframes = soup.find_all('iframe')
            for iframe in iframes:
                src = iframe.get('data-src') or iframe.get('src')
                if src and "youtube" not in src.lower():
                    if any(x in src.lower() for x in ['vidrame', 'vidmoly', 'vidyome', 'moly', 'player', 'embed', 'upstream', 'dizizone', 'ok.ru']):
                        video_kaynagi = src
                        break

        if not video_kaynagi:
            pattern = r'https?://[^\s"\']+(?:vidrame|vidmoly|vidyome|embed|player|moly|upstream)[^\s"\']+'
            matches = re.findall(pattern, str(res.content))
            for match in matches:
                if "youtube" not in match.lower():
                    video_kaynagi = match
                    break

        if video_kaynagi:
            if video_kaynagi.startswith('//'):
                video_kaynagi = 'https:' + video_kaynagi
            video_kaynagi = video_kaynagi.replace('ap=1', 'ap=0').replace('autoplay=1', 'autoplay=0').replace('autoPlay=1', 'autoPlay=0')

        return {
            "baslik": title,
            "afis": afis,
            "video_linki": video_kaynagi,
            "kategoriler": [kategori_adi],
            "imdb": imdb
        }
    except Exception as e:
        return None

def film_cekici_isci(gorev):
    film_link, baslik, kategori_adi = gorev
    bilgi = video_kaynagi_bul(film_link, kategori_adi)
    if bilgi and bilgi.get('video_linki'):
        print(f"  ✅ Yeni Eklendi: {baslik} | IMDb: {bilgi['imdb']}")
        return {
            "baslik": bilgi["baslik"] or baslik,
            "afis": bilgi["afis"],
            "orijinal_link": film_link,
            "video_linki": bilgi["video_linki"],
            "kategoriler": bilgi["kategoriler"],
            "imdb": bilgi["imdb"]
        }
    else:
        print(f"  ❌ {baslik} (Video Bulunamadı)")
        return None

def kategori_filmlerini_cek(kategori_adi, kategori_url, filmler_dict):
    sayfa = 1
    guncel_kategori_url = BASE_URL + kategori_url
    degisiklik_var_mi = False
    yeni_eklenen_sayisi = 0
    guncellenen_sayisi = 0

    while True:
        if sayfa == 1:
            url = guncel_kategori_url
        else:
            if not guncel_kategori_url.endswith('/'):
                guncel_kategori_url += '/'
            url = guncel_kategori_url + f'page/{sayfa}/'

        print(f"\n📄 {kategori_adi} - Sayfa {sayfa}")

        try:
            res = scraper.get(url, timeout=15)
            if sayfa == 1:
                guncel_kategori_url = res.url
                
            soup = BeautifulSoup(res.content, 'html.parser')
            kartlar = soup.find_all('a', class_='poster')

            if not kartlar:
                print(f"  ⛔ Sayfa bitti veya film bulunamadı.")
                break

            gorevler = []
            for kart in kartlar:
                film_link = kart.get('href', '')
                if not film_link.startswith('http'):
                    film_link = BASE_URL + film_link
                baslik = kart.get('title', 'Bilinmeyen')

                # KANZİ'NİN HARİKA TESPİTİNİN ÇÖZÜMÜ BURADA!
                if film_link in filmler_dict:
                    mevcut_film = filmler_dict[film_link]
                    # Film varsa ama bu kategori listesinde yoksa, kategoriyi listeye ekliyoruz
                    if kategori_adi not in mevcut_film['kategoriler']:
                        mevcut_film['kategoriler'].append(kategori_adi)
                        print(f"  🔄 Etiket Eklendi: {baslik} (+{kategori_adi})")
                        degisiklik_var_mi = True
                        guncellenen_sayisi += 1
                    else:
                        print(f"  ⏭️ Zaten var: {baslik}")
                else:
                    gorevler.append((film_link, baslik, kategori_adi))

            if gorevler:
                print(f"  🚀 {len(gorevler)} yeni film indiriliyor (TURBO MOD)...")
                with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
                    sonuclar = list(executor.map(film_cekici_isci, gorevler))

                for sonuc in sonuclar:
                    if sonuc:
                        # Sözlüğe (Dictionary) yeni filmi kaydediyoruz
                        filmler_dict[sonuc['orijinal_link']] = sonuc
                        degisiklik_var_mi = True
                        yeni_eklenen_sayisi += 1

            sayfa += 1
            time.sleep(1)

        except Exception as e:
            print(f"  ❌ Hata: {e}")
            break

    return degisiklik_var_mi, yeni_eklenen_sayisi, guncellenen_sayisi

def main():
    print("🍿 Patlamış Mısır Vakti - 🚀 KUSURSUZ V8 BOT Başlıyor!\n")

    mevcut_filmler = filmleri_oku()
    
    # Filmleri orijinal linkine göre etiketleyip 'Sözlük' yapısına çeviriyoruz
    filmler_dict = {f['orijinal_link']: f for f in mevcut_filmler}
    print(f"📦 Mevcut: {len(filmler_dict)} film")

    for kategori_adi, kategori_url in KATEGORILER.items():
        degisiklik, yeni, guncellenen = kategori_filmlerini_cek(kategori_adi, kategori_url, filmler_dict)
        
        # Eğer yeni film eklendiyse veya eski filme yeni kategori eklendiyse diske yaz!
        if degisiklik:
            print(f"\n📊 Kategori Özeti ({kategori_adi}): {yeni} Yeni, {guncellenen} Etiket Güncellemesi")
            filmleri_yaz(list(filmler_dict.values()))
        else:
            print(f"\n✅ {kategori_adi} kategorisinde yeni bir şey bulunamadı.")

    print(f"\n🎉 Bitti! Toplam Sistemdeki Film: {len(filmler_dict)}")

if __name__ == '__main__':
    main()