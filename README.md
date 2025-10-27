# super-nfc
NFC tag tabanlı kartvizit

# NFC Tag Claim Platform

NFC etiketi okutulduğunda kullanıcıya ait kartvizit/iletişim sayfasını gösteren platform.

## Özellikler
- Sağda açılır/kapanır Options sidebar
- Her tag için sabit ID (site + server + tag üzerinde)
- NFC okutulmadan kayıt yok, giriş mümkün
- Hesaplar tag ID’ye atanır
- Kartvizit/iletişim bilgisi sayfası (foto, logo, sosyal ikonlar)
- Çoklu sunucu desteği

## Kurulum
1) Gereksinimler: Node.js / Python / Docker (projene göre)
2) .env ayarları: `SERVER_URL=...` vb.

## Çalıştırma
```bash
# örnek
npm install
npm run dev
