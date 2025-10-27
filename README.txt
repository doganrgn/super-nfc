sunucuyu başlatmak için şu adımları izle 
cmd komutları 
1- cd C:\Users\Hp\Documents\nfc-tag-dashboard
(önce kütüphaneleri yükle)
2- pip install -r requirements.txt
(uvicorn un aktif olduğundan emin ol)
3- uvicorn main:app --reload --host 0.0.0.0 --port 8000
