# Super NFC

Super NFC; FastAPI, SQLModel ve Jinja2 tabanlı hafif bir NFC kartvizit platformudur. Her fiziksel etikete yazılan sabit `/t/<shortid>` bağlantısı sunucu tarafında ilgili kullanıcının profil sayfasına yönlenir. Böylece claim işlemi tamamlandıktan sonra fiziksel etiketi yeniden yazmaya gerek kalmaz.

## Özellikler
- NFC etiketi okutulduğunda dinamik profil sayfası (`/t/<shortid>`)
- Claim/Giriş akışları ve profil düzenleme paneli
- QR kod üretimi ve admin kullanıcılar için toplu QR ZIP çıktısı
- İstatistik API'si ile ziyaret sayılarının takibi

## Gereksinimler
- Python 3.10+
- SQLite (varsayılan olarak proje dizininde `app.db` oluşturulur)

## Kurulum
```bash
python -m venv .venv
source .venv/bin/activate  # Windows için .venv\Scripts\activate
pip install -r requirements.txt
```

Projeyi ilk kez çalıştırmadan önce `.env` dosyası oluşturup ortam değişkenlerini tanımlayın:

```env
PUBLIC_BASE_URL=https://ornek-subdomain.trycloudflare.com
ADMIN_EMAILS=admin@example.com
PURCHASE_URL=https://satin-al.example.com
SUPPORT_EMAIL=destek@example.com
SECRET_KEY=degerinizi_burada_tutun
```

> **Not:** `PUBLIC_BASE_URL` değeri mutlaka **https://** ile başlamalıdır. QR kodları ve NFC linkleri bu adresi baz alarak üretilir.

İdari araçlar tarafından indirilen CSV ve benzeri çıktı dosyaları UTF-8 karakter setiyle oluşturulur; dosyaları Excel veya benzeri araçlarda açarken bu kodlamayı seçmeniz önerilir.

## Geliştirme Ortamında Public URL Alma
NFC etiketleri telefon üzerinden okutulduğunda yerel ağdaki `127.0.0.1:8000` adresine erişemez. Geliştirme sürecinde public bir tünel kullanarak yerel sunucunuzu dışarıya açmanız gerekir.

### Cloudflare Tunnel (önerilen)
```bash
cloudflared tunnel --url http://127.0.0.1:8000
```
Komut çalıştıktan sonra Cloudflare size `https://` ile başlayan geçici bir URL üretir. Bu URL'yi `.env` dosyanızdaki `PUBLIC_BASE_URL` değerine yazın.

### ngrok Alternatifi
```bash
ngrok http 8000
```
Çıktıdaki `https://` adresini `PUBLIC_BASE_URL` olarak kullanabilirsiniz.

## Uygulamayı Çalıştırma
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Uygulama ilk çalıştığında veritabanı tabloları ve eksik kolonlar otomatik olarak oluşturulur.

## Akış Özeti
1. NFC etiketi okutulduğunda kullanıcı `https://.../t/<shortid>` adresine yönlenir.
2. Etiket sahipsiz ise claim/register akışı devreye girer.
3. Claim tamamlandığında aynı `/t/<shortid>` adresi dinamik olarak kullanıcının profilini gösterir.
4. Profil düzenlendiğinde değişiklikler anında herkes tarafından görüntülenir; fiziksel etiketi yeniden programlamaya gerek yoktur.

## Yardım & Destek
- Destek e-postası: `SUPPORT_EMAIL`
- Yeni etiket satın alma bağlantısı: `PURCHASE_URL`

Admin kullanıcıları `/admin/unassigned` panelinden boş tag envanterini görüntüleyebilir, CSV import yapabilir ve toplu QR ZIP indirebilir.