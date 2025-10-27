# Super NFC

NFC etiketi okutulduğunda kullanıcıya ait kartvizit/iletişim sayfasını gösteren platform.

## Özellikler
- Sağda açılır/kapanır Options sidebar
- Her tag için sabit ID (site + server + tag üzerinde)
- NFC okutulmadan kayıt yok; giriş mümkün
- Hesaplar tag ID’ye atanır
- Kartvizit/iletişim sayfası (foto, logo, sosyal ikonlar)
- Çoklu sunucu desteği

### Options Sidebar Kullanımı
- Sayfanın sağ altındaki "Seçenekleri Aç" butonu ile paneli açabilir, ESC ile hızla kapatabilirsiniz.
- Panel açıkken odak içeride kalır; TAB ve SHIFT+TAB ile seçenekler arasında dolaşabilirsiniz.
- Mobilde panel ekranın altından çekmece olarak açılır, masaüstünde sağdan kayar.

## Geliştirme
- (Proje stack’i ve çalıştırma adımları buraya gelecek)

sunucuyu başlatmak için şu adımları izle 
cmd komutları 
1- cd C:\Users\Hp\Documents\nfc-tag-dashboard
(önce kütüphaneleri yükle)
2- pip install -r requirements.txt
(uvicorn un aktif olduğundan emin ol)
3- uvicorn main:app --reload --host 0.0.0.0 --port 8000
