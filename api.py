import requests
from flask import Flask, jsonify

api = Flask(__name__)

# AwesomeAPI URL
AWESOME_API_URL = "https://economia.awesomeapi.com.br/json/last/USD-TRY,EUR-TRY,XAU-USD" # güncel verileri çekeceğimiz url
AWESOME_API_DAILY_URL = "https://economia.awesomeapi.com.br/json/daily"


# GÜNCEL verileri çekme 
def get_market_data():
    response = requests.get(AWESOME_API_URL) #requests belirli kaynak yada api den veri almak için http get isteği oluşturur
    # yukarıda ki url apiye yapılacak isteğin urlsidir bu url AwesomeAPI'nin sağladığı endpoint
    # response apiden gelecek yanıtı tutar

    if response.status_code == 200: # http protkolünde 200 istek başarılı kodudur bu kod gelince yanıtı döndür demektir.
        data = response.json() # gelen veriye erişmek için (veri json formatında olur)

        try:
            usd_try_satis = round(float(data["USDTRY"]["ask"]), 2)  # Dolar/TL kuru "ask" satış fiyatı demektir,  "bid" alış fiyat
            eur_try_satis = round(float(data["EURTRY"]["ask"]), 2)
            xau_usd_satis = round(float(data["XAUUSD"]["ask"]), 2)  # Altın Ons/USD kuru altta çeviricez gram-tl ye
            xau_usd_alis = round(float(data["XAUUSD"]["bid"]), 2)
            usd_try_alis = round(float(data["USDTRY"]["bid"]), 2)
            eur_try_alis = round(float(data["EURTRY"]["bid"]), 2)
            # float dönüşümünün sebebi jsondan gelen veriler genelde string olur , round ve sondaki 2 de gösterilecek basamak sayısı

            gold_gram_tls = round((xau_usd_satis * usd_try_satis) / 31.1035, 2) # dolar*tl = altının tl cinsi olur ve ons altın olduğundan birde bölme yapırız
            gold_gram_tla = round((xau_usd_alis * usd_try_alis) / 31.1035 , 2)

            # gelen verilerden fiyatları hesaplayarak sözlükde tutar. Sözlükteki isimlendirmeleri
            exchange_rates = {
                "USDs": usd_try_satis,
                "EURs": eur_try_satis,
                "Gold_Gram_TLs": gold_gram_tls,
                "USDa": usd_try_alis,
                "EURa": eur_try_alis,
                "Gold_Gram_TLa": gold_gram_tla
            }
            return exchange_rates

        except KeyError: #try bloğu çalışmaz ise hata fırlatır
            return {"error": "API yanıtında beklenen veriler bulunamadı"}

    else: #http protokolünde başarılı kodu yani 200 haricinde birşey gelirse aşağıda hata kodunu döndürür ona göre nerede hata var bakarız
        return {"error": f"API yanıt veremedi, HTTP Kodu: {response.status_code}"}


@api.route('/get-market-data', methods=['GET']) # app.route belli bir urlye karşılık gelen fonksiyon tanımlar.
# get-market-data urlnin yolunu belirler yani urlye get (çağırma) isteği atıldığında def market_Data çağırılır , method da gönderilen hangi isteğe göre çağırılacağını belirtir
# yani bu route, "GET" isteklerine yanıt veren bir endpoint tanımlar
def market_data():
    return jsonify(get_market_data()) # getmarketdata apiden alınan verileri sözlüğü döndürüyodu üstte
    # jsonify de bu sözlüğü json formatina döndürür ve istemciye gönderir (yani http yanıtıdır biz görürüz)

# İŞLEMLER -> get isteğiyle http://127.0.0.1:8000/get-market-data ziyaret edilir , marketdata çağırılır , getmarketdata apiden verileri alır , jonify de verileri dönüştürüri flaskde istemciye cevap verir


#----------------------------

def get_gecmis_veri(currency_pair: str, days: int): # aralıklı veriler buradan çekilir
    url = f"{AWESOME_API_DAILY_URL}/{currency_pair}/{days}"
    prices = [] # risk analizi yaparken başlangıç fiyatından başlanmalı listeyi riskanaliz.py içinde ters döndürerek kullanılmalı
    try:
        response = requests.get(url)
        response.raise_for_status() # HTTP hataları için exception fırlatır
        data = response.json()

        if data and isinstance(data, list): # eğer data mevcut ve liste türünde ise
            for item in data:
                # Her bir günün verisi bir sözlük içinde
                if 'bid' in item:
                    try:
                        prices.append(float(item['bid']))
                    except ValueError:
                        print(f"Uyarı: {currency_pair} için 'bid' değeri float değil: {item.get('bid')}")
                        pass # veya loglama yapılabilir

        return prices if prices else []

    except requests.exceptions.RequestException as e:
        print(f"Awesome API'dan geçmiş seri veri alınırken hata ({currency_pair}, son {days} gün): {e}")
        return [] # Hata durumunda boş liste dönüyoruz
    except Exception as e:
        print(f"Beklenmeyen hata oluştu ({currency_pair}, son {days} gün): {e}")
        return [] # Diğer beklenmeyen hatalar için boş liste dönüyoruz


@api.route('/get-historical-series/<currency_pair>/<int:days>', methods=['GET'])
def historical_series_route(currency_pair, days):

    prices = get_gecmis_veri(currency_pair, days)
    return jsonify(prices)

#----------------------------

def haftalik_veri():
    haftalik_veriler = {}

    haftalik_dolar_tl_seri = get_gecmis_veri("USD-TRY", 7)
    haftalik_veriler['USDh'] = haftalik_dolar_tl_seri

    haftalik_euro_tl_seri = get_gecmis_veri("EUR-TRY", 7)
    haftalik_veriler['EURh'] = haftalik_euro_tl_seri

    haftalik_altin_dolar_seri = get_gecmis_veri("XAU-USD", 7)

    haftalik_gram_altin_tl_seri = []
    if haftalik_dolar_tl_seri and haftalik_altin_dolar_seri and len(haftalik_dolar_tl_seri) == len(haftalik_altin_dolar_seri):
        for i in range(len(haftalik_dolar_tl_seri)):
            try:
                gram_altin_tl_fiyat = round((haftalik_altin_dolar_seri[i] * haftalik_dolar_tl_seri[i]) / 31.1035 , 2)
                haftalik_gram_altin_tl_seri.append(gram_altin_tl_fiyat)
            except Exception as e:
                print(f"Gram Altın/TL hesaplanırken hata oluştu (indeks {i}): {e}")
                haftalik_gram_altin_tl_seri.append(None) # Hata durumunda None ekle

    haftalik_veriler["Gold_Gram_TLh"] = haftalik_gram_altin_tl_seri # Gram Altın/TL fiyat serisi

    return haftalik_veriler


@api.route('/get-weekly', methods=['GET']) # bu local urller app.py den rahat ve sade erişmek için
def get_weekly():
    return jsonify(haftalik_veri())

#----------------------------

def aylik_veri():
    aylik_veriler = {}

    aylik_dolar_tl_seri = get_gecmis_veri("USD-TRY", 30)
    aylik_veriler['USDa'] = aylik_dolar_tl_seri

    aylik_euro_tl_seri = get_gecmis_veri("EUR-TRY", 30)
    aylik_veriler['EURa'] = aylik_euro_tl_seri

    aylik_altin_dolar_seri = get_gecmis_veri("XAU-USD", 30)

    aylik_gram_altin_tl_seri = []
    if aylik_dolar_tl_seri and aylik_altin_dolar_seri and len(aylik_dolar_tl_seri) == len(aylik_altin_dolar_seri):
        for i in range(len(aylik_dolar_tl_seri)):
            try:
                # Her bir gün için Gram Altın/TL'yi hesapla
                gram_altin_tl_fiyat = round((aylik_altin_dolar_seri[i] * aylik_dolar_tl_seri[i]) / 31.1035 , 2)
                aylik_gram_altin_tl_seri.append(gram_altin_tl_fiyat)
            except Exception as e:
                print(f"Aylık Gram Altın/TL hesaplanırken hata oluştu (indeks {i}): {e}")
                aylik_gram_altin_tl_seri.append(None) # Hata durumunda None ekle

    aylik_veriler["Gold_Gram_TLa"] = aylik_gram_altin_tl_seri # Gram Altın/TL fiyat serisi

    return aylik_veriler

@api.route('/get-monthly', methods=['GET']) 
def get_monthly():
    return jsonify(aylik_veri())

#----------------------------

def yillik_veri():
    yillik_veriler = {}

    yillik_dolar_tl_seri = get_gecmis_veri("USD-TRY", 360)
    yillik_veriler['USDy'] = yillik_dolar_tl_seri

    yillik_euro_tl_seri = get_gecmis_veri("EUR-TRY", 360)
    yillik_veriler['EURy'] = yillik_euro_tl_seri

    yillik_altin_dolar_seri = get_gecmis_veri("XAU-USD", 360)

    yillik_gram_altin_tl_seri = []
    if yillik_dolar_tl_seri and yillik_altin_dolar_seri:
        for i in range(len(yillik_dolar_tl_seri)):
            try:
                # Her bir gün için Gram Altın/TL'yi hesapla
                gram_altin_tl_fiyat = round((yillik_altin_dolar_seri[i] * yillik_dolar_tl_seri[i]) / 31.1035 , 2)
                yillik_gram_altin_tl_seri.append(gram_altin_tl_fiyat)
            except Exception as e:
                print(f"Yıllık Gram Altın/TL hesaplanırken hata oluştu (indeks {i}): {e}")
                yillik_gram_altin_tl_seri.append(None) # Hata durumunda None ekle

    yillik_veriler["Gold_Gram_TLy"] = yillik_gram_altin_tl_seri # Gram Altın/TL fiyat serisi

    return yillik_veriler

@api.route('/get-yearly', methods=['GET']) # bu local urller app.py den rahat ve sade erişmek için
def get_yearly():
    return jsonify(yillik_veri())



# günlük, haftalık ve aylık verileri almak için tarihleri ayarladık  
if __name__ == '__main__': #başka dosyadan import edilmeden direkt ana dosya olarak çalıştırılıyorsayı kontrol eder.
    # yani bir projenin bir parçası da olabilir bu dosya o yüzden özel bir port açmak yerine saten projenin ilerlediği porta bilgiler kullanılır anlamına gelir.
    api.run(debug=True, port=8000)  # flaskı çalıştırır , debug geliştirici modudur kodda değişiklik yapıp kaydedince oto yeniden başlatır yani zaman kaybettirmez  




#----------------------------


# tarihe göre kapanış fiyatlarını bu fonksiyon üzerinden çalışır
# def get_historical_data(currency_pair, target_date): # sadece hedef tarihi alıyor
#     url = f"{AWESOME_API_DAILY_URL}/{currency_pair}/?start_date=20220202&end_date={target_date}" # Başlangıç tarihi önemsiz
#     try:
#         response = requests.get(url)
#         response.raise_for_status()
#         historical_data = response.json()
#         if historical_data and len(historical_data) > 0:
#             return float(historical_data[0]["bid"]) # varlık hakkında birçok veri döner biz sadece fiyatı alırız   
#         else:
#             return None
#     except requests.exceptions.RequestException as e:
#         return {"error": f"Awesome API'dan geçmiş veri alınırken hata ({currency_pair}): {e}"}
#     except ValueError:
#         return {"error": f"Awesome API'dan geçersiz geçmiş veri yanıtı ({currency_pair})"}


# @api.route('/get-historical-data/<currency_pair>/<string:target_date>', methods=['GET']) # istenirse app.py den direkt tarihli istek atılabilir
# def historical_data_route(currency_pair, target_date):
#     return jsonify(get_historical_data(currency_pair, target_date))