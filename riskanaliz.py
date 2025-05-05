import pandas as pd
import numpy as np
import requests
import random 
import scipy.stats as stats # dağılımlar için gerekli

try:
    from arch import arch_model # vollalite modellemesi için garch kullanılacak ondan dolayı arch lazım olacak
    GARCH_AVAILABLE = True
except ImportError: # herhangi bir nedenden dolayı arch kütüphanesi yoksa standart sapmaya göre hesaplayacak
    print("Uyarı: 'arch' kütüphanesi bulunamadı. GARCH modellemesi yerine basit standart sapma kullanılacaktır.")
    GARCH_AVAILABLE = False



API_WEEKLY_URL = "http://127.0.0.1:8000/get-weekly"
API_MOTHLY_URL = "http://127.0.0.1:8000/get-monthly"
API_YEARLY_URL = "http://127.0.0.1:8000/get-yearly"



def en_iyi_dagilimi_bul(veri_serisi, aday_dagilimlar, bins=20): #incelenecek veri serisi, incelenecek dağılımlar ve histogram için bin sayısı alır (kikare için)
    # başlangıç olarak aranan değerler boş olarak başlanıyor
    en_iyi_ortalama = float('inf') # inf her test sonucunda min değeri seçer
    en_iyi_dagilim = None
    en_iyi_parametreler = None

    for dagilim_adi in aday_dagilimlar: # listede ki her dağılımı tek tek alır
        dagilim = getattr(stats, dagilim_adi) # scipy dan ilgili dağılım nesnesini alır (örneğin dağılım adı "norm" ise "scipy.stats.norm" olur)
        try:
            parametreler = dagilim.fit(veri_serisi) # alınan dağılımın parametrelerini hesaplar (örneğin normal dağılım için veri serimizin ortalama ve standart sapmasını hesaplar)

            ks_stat, _ = stats.kstest(veri_serisi, dagilim_adi, args=parametreler) # kolmogorov-smirnov testi ile veri setimiz aday dağılım ile uygunluk testi yapılır kümülatif dağılım fonksiyonları karşılaştırılır (test istatistiği ve p-değeri döner)  
            
            try:
                if dagilim_adi in ['norm', 'expon', 'logistic', 'gumbel_l', 'gumbel_r']: # bizim dağılım adaylarımızın ad testi için desteklenen dağılımlardan olup olmadığı kontrol edilir (ad testi her dağılımı desteklemez)
                    ad_result = stats.anderson(veri_serisi, dist=dagilim_adi) # dağılım destekleniyorsa test gerçekleştirilir
                    ad_stat = ad_result.statistic # test istatistiği , kritik değerler gibi sonuçlar nesnesi döndürür
                else:
                    ad_stat = np.nan # dağılım desteklenmiyorsa
            except Exception:
                ad_stat = np.nan

            hist, bin_edges = np.histogram(veri_serisi, bins=bins) # veri serimizin histogramını oluşturur, hist ve bin_edges döner (her binin frekansı ve histogramın kenarları)
            cdf_vals = dagilim.cdf(bin_edges, *parametreler) # aday dağılımın cdf değerlerini hesaplar (bin kenarları ile birlikte) yani her binin üstündeki alanı verir
            expected = len(veri_serisi) * np.diff(cdf_vals) # her bin için beklenen frekanslardır (histogram frekanslarımız bu beklenen frekanslara yakın olmalı)
            with np.errstate(divide='ignore', invalid='ignore'): # karşılaştırma yapılırken frekanslar birbirine bölünür. bazı durumlarda bölüm sıfır olur yada nan değerler olur hata vermemesi için bu satır kullanılır
                chi2_stat = np.nansum((hist - expected) ** 2 / (expected + 1e-8)) # frekanslar farkı hesaplanır, farkın karesi alınır, beklenen frekansa bölünür ve çok küçük pozitif değer eklenir üstteki sıfır bölüm durumunu önlemek için en son nansum ile toplamı alınır (nansum, nan değerleri yoksayar bu da yine üstteki nan hatasını önler)
            
            scores = [ks_stat, chi2_stat] # ad testi nan olabilir önce diğer test sonuçları alınır
            if not np.isnan(ad_stat): # ad testi nan değilse o da eklenir
                scores.append(ad_stat)
            ortalama = np.mean(scores) # hepsinin ortalaması alınır
            if ortalama < en_iyi_ortalama: #  eğer ortalama en iyi ortalamadan küçükse yeni en iyi olarak atanır
                en_iyi_ortalama = ortalama
                en_iyi_dagilim = dagilim_adi
                en_iyi_parametreler = parametreler
        except Exception: # hatalar göz ardı edilir
            print(f"Uyarı: {dagilim_adi} dağılımı için hata oluştu Diğer testler devam edecek")   
            continue
    return en_iyi_dagilim, en_iyi_parametreler # en iyi uyum sağlanan dağılım ve parametreleri döndürülür



# Yıllık seri verileri API'den çeken fonksiyon (get-yearly endpoint'ini kullanır)
def yillik_veri_cek(api_url):
    try:
        response = requests.get(api_url)
        response.raise_for_status() # veri çekme sırasında bir hata varsa hata fırlatır
        data = response.json()

        if isinstance(data, dict):        # API'den gelen verinin beklenen formatta (sözlük) olup olmadığını kontrol et
             return data             # api.py'deki get_yearly fonksiyonu zaten doğru formatta veriyi döndürüyor.
        else:
            print(f"Uyarı: Yıllık veri API'sinden beklenmedik yanıt formatı: {type(data)}") # herhangi bir hata durumunda
            return {"error": "Yıllık veri API'sinden beklenmedik yanıt formatı."}

    except requests.exceptions.RequestException as e: # istek sırasında bir hata oluşursa hata dosyaları "e" etiketi ile tutulur
        print(f"Yıllık veri API hatası ({api_url}): {e}")
        return {"error": f"Yıllık veri API hatası: {e}"}
    except Exception as e:
        print(f"Beklenmeyen hata oluştu ({api_url}): {e}")
        return {"error": f"Beklenmeyen hata oluştu: {e}"}



# Log getiriyi hesaplayan fonksiyon (varlıkları tek tek alır hesaplar ve sözlük döndürür)
def log_getiri_hesapla(prices_dict): # bizim local url lerdeki tek sözlük içinde her varlığa ait liste içindeki fiyatları alır
    log_returns = {} # hesaplana log getileri tutacak
    for asset_key, prices in prices_dict.items(): # sözlük içinde varlık - fiyat listesi çiftini tek tek alır
        if prices and len(prices) > 1: # Log getiri için en az 2 fiyat noktası olmalı o yüzden fiyat ve en az 2 fiyat kontrolü yapılır
            price_series = pd.Series(prices) # kaydırma işlemleri (zamanı geri alma) zaman serilerinde kullanışlı olduğu için pandas serisi oluşturuyoruz
            log_return_series = np.log(price_series / price_series.shift(1)) # log getiri hesaplanır (önceki fiyat ile bölünür ve logaritması alınır. 1.günün öncekiğ günü nan olacağından 1.log getiri nan döner)
            log_returns[asset_key] = log_return_series.tolist() 
            # log getiriler tekrardan listeye dönüştürülüp fiyat verileri gibi sözlük içine eklenir (fiyat veri sayısı - 1 kadar log getiri olur ama ilk fiyatın önceki fiyatı nan olarak alındığından ilk log getiride nan olur o yüzden 1.nan toplam 7 veri olur)
        else:
            print(f"Uyarı: {asset_key} için fiyat verisi bulunamadı veya yetersiz ({len(prices) if prices else 0} nokta). Log getiri hesaplanamadı.")

    return log_returns



# Ortalama Getiri (Drift - log getirilerin ortalaması) hesaplayan fonksiyon
def drift_hesapla(log_returns_df): # log getirileri dataframe'i alır
    drift = {} # ortalama log getirilerin saklanacağı boş bir sözlük oluşturulur
    if not log_returns_df.empty: 
        drift = log_returns_df.mean().to_dict() # mean otomatik olarak NaN değerleri yoksayar ve her bir sütunun (yani her bir varlığın) ortalamasını hesaplar.
    else:
        print("Uyarı: Drift hesaplamak için log getiri DataFrame'i boş.")
    return drift



# Volatilite (Standart Sapma) hesaplayan fonksiyon
def volalite_hesapla(log_returns_df): # log getirileri dataframe'i alır
    volatility = {}
    if not log_returns_df.empty:
        volatility = log_returns_df.std().to_dict() # finansal alanda std volatilite (risk) olarak yorumlanır.
    else:
         print("Uyarı: Basit volatilite hesaplamak için log getiri DataFrame'i boş.")
    return volatility



# GARCH ile Koşullu Volatilite hesaplayan fonksiyon
def garch_volalite_hesapla(log_returns_df):
    garch_volatility = {}
    if not GARCH_AVAILABLE: #kütüphane yoksa (en başta false dönerse)
        print("GARCH kütüphanesi yüklü değil. GARCH volatilitesi hesaplanamayacak.")
        return garch_volatility
    if log_returns_df.empty: #log getiri sözlüğü boşsa
        print("Uyarı: GARCH volatilitesi hesaplamak için log getiri DataFrame'i boş.")
        return garch_volatility

    for asset in log_returns_df.columns: # her sütünu (varlığı) tek tek alır
        returns_series = log_returns_df[asset].dropna() # döngüde ki varlığın log getirisi serisini alır ve NaN değerleri atar
        if len(returns_series) > 30: # GARCH modeli için yeterli veri noktası var mı kontrolü (min 30 tercih edilir)
            try:
                try:
                    model = arch_model(returns_series, mean='zero', vol='Garch', p=1, q=1, distribution='t') # model tanımlanır
                    #modelin yapılacağı getiri verisi , ortalama sıfır alınır modeli birleştirmek için, GARCH modeli, p ve q arch garch terim gecikmeleri, model hataları dağılımo student t dağılımı olduğu varsayılır
                except TypeError:
                     print(f"Uyarı: 'arch' kütüphanesi 'distribution' argümanını desteklemiyor. Normal dağılım varsayılacak.")
                     model = arch_model(returns_series, mean='zero', vol='Garch', p=1, q=1)
                results = model.fit(disp='off') # model parametreleri tahmin edilip eğitilir , disp ayrıntıları ekrana yazdırmaması için 'off' kullanılır

                last_conditional_volatility = results.conditional_volatility.iloc[-1] # tahmni edilen volalitelerden en güncel yani en sondakini seçer  
                garch_volatility[asset] = last_conditional_volatility # seçilen volaliteye o anki varlığın adı anahtar olarak atanır

            except Exception as e:
                print(f"Uyarı: {asset} için GARCH(1,1) modeli uydurulurken hata oluştu: {e}")
                garch_volatility[asset] = 0.0 # Hata durumında 0.0 atanır ileriki durumlarda çağırıldığında hata olmaması için
        else:
            print(f"Uyarı: {asset} için GARCH(1,1) modeli uydurmak için yeterli veri yok ({len(returns_series)} nokta).")
            garch_volatility[asset] = 0.0 

    return garch_volatility



# Korelasyon Matrisi hesaplayan fonksiyon
def korelasyon_hesapla(log_returns_df):
    if not log_returns_df.empty: #boş değilse
        min_data_points = len(log_returns_df.dropna()) # herhangi bir yerde nan içeren satırı komple atar tüm varlıklar için ortak geçerli yani nan'sız zaman periyodu oluşur
        min_periods_corr = max(2, int(min_data_points * 0.8)) # Önceki adımda bulunan tüm varlıklarda veri olan satır sayısının %80'i alınır tam sayı yapılır ve bunların en az iki adet olması garanti edilir. max derkende o iki varlıkta aynı anda en az kaç tane nan olmayan getiri değeri olduğuna bakılır
        correlation_matrix = log_returns_df.corr(min_periods=min_periods_corr) # üstte hazırlanan dataframenin korelasyonunu hesaplar matris oluşturulue
        return correlation_matrix
    else:
        print("Uyarı: Korelasyon matrisi hesaplamak için log getiri DataFrame'i boş.")
        return pd.DataFrame() # Boş DataFrame döndür



# Kovaryans Matrisi hesaplayan fonksiyon
def kovaryans_hesapla(log_returns_df, volatility_dict): # log getiri dfsi ve her varlığın volalitesini (std volalitesi garch değil) içeren sözlük
    correlation_matrix = korelasyon_hesapla(log_returns_df) #korelasyon hesaplaması ve korelasyon matrisini alır. aşağıda kovaryans hesaplamak için => kovaryans = korelasyan * 1.nin standartsama(volalite) * 2.nin std
    assets = correlation_matrix.columns.tolist() #sütun adları yani varlık isimleri listeye dönüştürülür
    num_assets = len(assets) # liste uzunluğu alınır
    if num_assets == 0: # liste boşsa
        print("Kovaryans matrisi hesaplamak için yeterli varlık veya korelasyon matrisi yok.")
        return np.array([]) #boş numpy dizisi döndürülür
    
    stdevs = np.array([volatility_dict.get(asset, 0.0) for asset in assets]) # her varlığın volatilitesini alır ve np dizisi yapar (volalitesi olmayan varlıklara 0.0 değeri atar)
    D = np.diag(stdevs) # köşegen matris oluşturulur (Bu matrisin ana köşegeninde varlıkların standart sapma değerleri bulunur, diğer tüm elemanları sıfırdır)
    Rho = correlation_matrix.values # Pandas DataFrame'den NumPy dizisine döndürülür yani korelasyon matrisidir.

    try:
        Sigma = D @ Rho @ D # sigma = kovaryans matrisi hesaplanır (Σ=D×ρ×D formülüyle bulunur.  korelasyon ile volaliteninin çarpımıdır. @ = matris çarpımı demektir)
        L = np.linalg.cholesky(Sigma) # Σ=LL^T formülü ile kovaryans matrisin Cholesky ayrışımı hesaplanır (monte carlo simülasyonu için bu L matrisi olmazsa olmazdır bu matrisi kovaryans matrisin özeti gibi düşünebiliriz. rastgele bağımsız şokları bununla çarparak birbirine bağımlı yani ilişkili daha tutarlı şoklar elde edeceğiz).
        print("Cholesky ayrışımı başarılı. L matrisi boyutu:", L.shape)
        return L # Başarılı olursa Cholesky matrisini döndür
    
    except np.linalg.LinAlgError as e: # bu hata kodu ayrışımın hesaplanamamasından kaynaklanır sebebi kovaryans matrisi her zaman pozitif yarı-tanımlı olmamasından kaynaklanır (eksik, hatalı verilerden kaynaklı olabilir)
        print(f"Hata: Kovaryans matrisinin Cholesky ayrışımı hesaplanamadı: {e}")
        print("Simülasyon korelasyon olmadan çalıştırılacak (Kovaryans matrisi yerine standart sapmaların köşegen matrisi (D Matrisi) kullanılacak).")
        print("Korelasyon atlandı. Kullanılan L matrisi (D matrisi) boyutu:", L.shape) # yani Formülde kullanılacak L matrisi artık yerine artık D matrisi kullanılacak
        return D # Hata durumunda D matrisini döndür



# Monte Carlo simülasyonu çalıştıran fonksiyon
def mcs_yap(drift_dict, volatility_dict, cholesky_matrix_L, initial_asset_values, num_simulations=10000, num_days=7, varlik_dagilimlari=None):    # ortalama log getiri , varlıkların volatilitesi (std yada grachdan gelen), cholesky matrisi (yada std matrisi, getirilerin birlikte nasıl hareket edeceği), varlıkların başlangıç varlık değerleri, simülasyon sayısı ve gün sayısı alır
    simulated_portfolio_values = [] # Tüm simülasyonların sonucunda toplam portföy değerlerini saklamak için 

    assets = list(initial_asset_values.keys()) #varlıklar alınır
    num_assets = len(assets) # varlık sayısı alınır
    if num_assets == 0 or cholesky_matrix_L.shape[0] != num_assets: # varlık sayısı ile l matris satırı eşit olmalı ki simülasyon yapılabilsin
        print("Hata: Simülasyon için varlık sayısı veya Cholesky matrisi boyutu uyumsuz.")
        print(f"  Varlık sayısı (initial_asset_values): {num_assets}")
        print(f"  Cholesky matrisi boyutu: {cholesky_matrix_L.shape}")
        return [] # Boş liste döndür

    dt = 1.0 # simülasyonun ilerleyeceği Günlük adım
    print(f"Monte Carlo simülasyonu başlatılıyor ({num_simulations} simülasyon, {num_days} gün)...")
    for sim_num in range(num_simulations): # her simülasyon olası gelecek değeri gösterir
        if num_simulations >= 100 and sim_num % (num_simulations // 100) == 0: # Toplam simülasyon sayısının %1'inde bir ilerleme yazdır
             print(f"  Simülasyon {sim_num}/{num_simulations}...")
        current_asset_values = initial_asset_values.copy() # Başlangıç değerlerini kopyalanır her sim aynı noktadan başlar

        for day in range(num_days): # her simülasyon (10k) 7 günlük seriyi bulmak için çalışır. her 7 günlük seri 1 sim patikasıdır. Bu döngüde her patikanın 7 günlük serisinin 1 gününü temsil eder
            independent_random_shocks_Z = np.zeros(num_assets) # her varlık için üretilecek rastgele şoklar için sıfır matris oluşturulur
            for i, asset in enumerate(assets):
                if varlik_dagilimlari and asset in varlik_dagilimlari:
                    dagilim_adi = varlik_dagilimlari[asset]['dist']
                    parametreler = varlik_dagilimlari[asset]['params']
                    dagilim = getattr(stats, dagilim_adi)
                    try:
                        independent_random_shocks_Z[i] = dagilim.rvs(*parametreler) # testler sonucunda gelen dağılım parametrelerine göre rastgele değer üretilir yani rastgele şoklar üretilir
                    except Exception:
                        independent_random_shocks_Z[i] = np.random.normal() # herhangi bir hata durumunda normal dağılımdan rastgele değer üretilir
                else:
                    independent_random_shocks_Z[i] = np.random.normal()
                    
            correlated_random_shocks_epsilon = np.dot(cholesky_matrix_L, independent_random_shocks_Z) # np.dot=@ yani ikiside matris çarpımı demek. rastgele üretilen şoklar ile cholesky matrisinin çarpımı ile korelasyonlu şoklar üretilir. Bu işlemde L matrisinin Cholesky ayrışımından geldiği için varlıklar arası ilişkili şoklar üretilir. bu ilişki sonuç vektörüdür
            # burada korelasyon hesabında hata yoksa gerçekten L matrisi gelmiş ise varlıklar arası gerçek bir ilişki sağlanarak korelasyon yapısı oluşur ancak L matris yerine D matrsi gelmiş ise varlıklar kendi özel volalitelerini kullanır buda hata payı doğurur
            
            for i, asset in enumerate(assets): # gün içinde her varlığa ait tek tek fiyat güncellemesi
                S_t = current_asset_values.get(asset, 0.0) # varlığa ait o anki mevcut değer alınır boş ise 0.0 oto. atanır
                if S_t <= 0: # Fiyat sıfır veya negatifse simülasyonu durdur veya atla
                    current_asset_values[asset] = 0.0 # Değeri sıfır yap devam et
                    continue 

                mu_i = drift_dict.get(asset, 0.0) # drift değerleri
                sigma_i = volatility_dict.get(asset, 0.0) # volalite değerleri
                epsilon_i = correlated_random_shocks_epsilon[i] # o güne ait ilgili korele şok değerleri
                try:
                    exponent = (mu_i - 0.5 * sigma_i**2) * dt + sigma_i * epsilon_i * np.sqrt(dt) # Geometric Brownian Motion modeli kullanılarak varlığın bir sonraki zaman adımına ait log getirisini modelleyen üs kısmı hesaplanır.
                    # log getirinin beklenen değerini + rastgele şokun etkisi
                    S_t_plus_dt = S_t * np.exp(exponent) # Varlığın bir sonraki günkü değeri =  mevcut değeri * hesaplanan üsün loge üzeri
                    current_asset_values[asset] = max(0.0, S_t_plus_dt) # hesaplanan değer ilgili varlığın değerine atanır herhangi bir hata durumunda 0 atanır
                except Exception as e: # herhangi bir hata mesajı oluşursa varlık değeri eski halinde yani o anki fiyatında bırakılır
                    print(f"Hata: Simülasyon {sim_num}, Gün {day}, Varlık {asset} için GBM simülasyonunda hata oluştu: {e}")
                    current_asset_values[asset] = S_t # Hata durumunda önceki değeri koru veya 0 yapabilirsiniz

        final_portfolio_value = sum(current_asset_values.values()) # günler bittiğinde (yani 1 patika bitince o günkü varlık değerleri toplanır)
        simulated_portfolio_values.append(final_portfolio_value) # toplam değer listeye eklenir

    print("Monte Carlo simülasyonu tamamlandı.") # patikalar birince simülasyon bitmiş olur ve mesaj döndürülür
    return simulated_portfolio_values # her bir simülasyon patikasının sonundaki portföy değerlerini içeren listesini döndürür.



# VaR (Riskteki Değer) hesaplayan fonksiyon
def var_hesapla(simulated_values, initial_value, confidence_level=0.95): # sim sonunda oluşan toplam portföy değerleri litesi, sim başladığındaki toplam portföy değeri ve güven seviyesi (yani %95 için 0.95)
    if not simulated_values: # sim sonuç kontrolü boş ise to 0 atar
        return 0.0
    
    sorted_values = np.sort(simulated_values) # Simülasyon sonuçlarını küçükten büyüğe doğru sıralanır. Bu sıralama en kötü senaryoları (en düşük portföy değerlerini) listenin başına getirir.
    index = int((1 - confidence_level) * len(sorted_values)) # en kötü %5lik sim sonuçları için tekrar sayısına göre kaç sayı yaptığına bakılır (10k için %5 500 eleman demektir) bu kadar eleman alınır bunlarında bitiş indexi belirlenir
    var_value_at_level = sorted_values[index] # VaR'a karşılık gelen değeri alır (yani üstteki en kötü durumlar olan %5'lik dilimdeki en kötü senaryoların en kötüsünün başlangıç noktası yani içlerinden en min değer)
    var_loss = initial_value - var_value_at_level # başlangıç değerinden bulunan en kötü değer çıkarılır ve fark tespit edilir
    return max(0.0, var_loss) # var değerinin negatif olmaması için max ile 0.0 döndürülür. Eğer var kaybı negatifse 0 döner. Bu durumda kayıp yok demektir mantıken pozitiflikte de 0 olmalıdır ki risk yok demektir.



# CVaR (Koşullu Riskteki Değer) hesaplayan fonksiyon -- var ile aynı işler sadece burada ortalama hesaplanır
def cvar_hesapla(simulated_values, initial_value, confidence_level=0.95):
    if not simulated_values:
        return 0.0

    sorted_values = np.sort(simulated_values) # var da olduıpğu gibi simülasyon sonuçları küçükten büyüğe sıralanır en kötüler başta kalır
    index = int((1 - confidence_level) * len(sorted_values)) # %5'lik dilim için en kötü senaryoların başlangıç noktası bulunur
    cvar_values = sorted_values[:index] # sıranın başlangıç durumundan itibaren itibaren %5'lik dilim alınır (yani en kötü %5'lik dilim buda 10k sim tekrarı için 500 elaman eder)
    if cvar_values.size > 0:
        cvar_loss = initial_value - np.mean(cvar_values) # kuyruktaki yani en kötü durumdaki kayıpların ortalaması alınır. eğer en kötü %5'lik dilime düşersem, ortalama olarak ne kadar kaybederim" sorusunun cevabıdır.
        return max(0.0, cvar_loss)
    else:
        return 0.0



# Risk metriklerini (VaR ve CVaR) hesaplayan birleştirilmiş fonksiyon -- amaç tek bir fonkisyonda portföyün iki risk değerini ölçmek
def risk_metrikleri_hesapla(simulated_values, initial_value, confidence_level=0.95): # mcs den elde edilen ileriye dönük portföy toplam değer tahminlerinin olduğu liste , portföy başlangıç değeri , ölçülecek güven aralığı
    if not simulated_values:
        return {f"VaR_{int(confidence_level*100)}": 0.0, f"CVaR_{int(confidence_level*100)}": 0.0}

    var_loss = var_hesapla(simulated_values, initial_value, confidence_level)
    cvar_loss = cvar_hesapla(simulated_values, initial_value, confidence_level)

    return {
        f"VaR_{int(confidence_level*100)}": var_loss, # bilgi amaçlı hesaplanan risk değerlerinin anahtarlarına güven aralık değerleri yazılır
        f"CVaR_{int(confidence_level*100)}": cvar_loss
    }



def risk_analiz_yap(initial_asset_values: dict): # cüzdandaki varlıkları ve miktarılarını sözlük olarak alacak
    initial_portfolio_value = sum(initial_asset_values.values()) # cüzdandan alınan varlıkların toplam değeri hesaplanır
    if initial_portfolio_value <= 0: # varlık kontrolü
         return {"error": "Risk analizi için portföy değeri sıfır veya negatif olamaz."}


    wallet_asset_keys = set(initial_asset_values.keys()) # cüzdanaki varlık isimlerini küme olarak alınır. Küme alınmasının sebebi karşılaştırmanın rahat yapılması ('USD', 'EUR', 'Gold_Gram_TL' gibi anahtarlarla çalışıyor app.py de uyumlu olmalı)
    if not wallet_asset_keys:
         return {"error": "Risk analizi yapılacak cüzdanda Dolar, Euro veya Altın bulunmuyor."}


    print(f"Yıllık piyasa verileri çekiliyor ({API_YEARLY_URL})...")
    yearly_data = yillik_veri_cek(API_YEARLY_URL) # local url den yıllık veriler çekiliyor
    if "error" in yearly_data:
        print(f"Hata: Yıllık piyasa verileri çekilemedi: {yearly_data['error']}")
        return {"error": f"Risk analizi için gerekli yıllık piyasa verileri çekilemedi: {yearly_data['error']}"}


    prices_dict = {} # sonuç olarak bu sözlükte cüzdanda ki isimleri ile çekilen yıllık fiyatları tutacak
    for asset_key in wallet_asset_keys: # cüzdanda bulunan varlıklar alınır (EUR , USD , Gold_Gram_TL isimleriyle saklanır burada)
         api_key = asset_key + "y" # local urlde verilerin sonunda "y" harfi uyumu bozduğundan üstekilerle eşleşmesi için y ekliyoruz
         prices_dict[asset_key] = yearly_data.get(api_key, []) # boş liste koyulmasının sebebi verinin alınamaması durumunda hata vermemesi boş liste döndürmesi için


    valid_prices = {asset: prices for asset, prices in prices_dict.items() if prices and len(prices) > 1} # valid sözlüğü fiyatlarını çektiğimiz varlıkları (boş olmayanları) "varlık" : "fiyat olacak şekilde tek tek alır"
    if not valid_prices:
        print("Hata: Risk analizi için cüzdandaki varlıklar için yeterli geçerli fiyat serisi bulunamadı.")
        missing_data_assets = wallet_asset_keys - set(valid_prices.keys()) # fiyat verisi olmayan varlıkları bulur ve mesaj olarak basar
        error_message = f"Risk analizi yapılamıyor. Cüzdanınızda bulunan ancak analiz verisi (geçmiş fiyat) çekilemeyen/hesaplanamayan varlıklar: {list(missing_data_assets)}. Lütfen bu varlıklar için piyasa verisi kaynaklarını kontrol edin."
        return {"error": error_message}


    min_len = min(len(prices) for prices in valid_prices.values()) # fiyatları tek tek alıp en kısa olanı bulur
    aligned_prices_dict = {asset: prices[:min_len] for asset, prices in valid_prices.items()} # cüzdanda olan varlıkların fiyatlarını üstte bulduğumuz en kısa olanına göre baştan itibaren keser böylece tüm varlıkların fiyat listeleri aynı uzunlukta olur
    print(f"Veri hizalama tamamlandı. Kullanılan seriler {min_len} uzunluğunda.")


    print("Log getiriler hesaplanıyor...")
    log_getiriler = log_getiri_hesapla(aligned_prices_dict) # hizalanman fiyatları tek tek alır ve log getirilerini hesaplar
    print("Hesaplanan log getiriler anahtarları:", list(log_getiriler.keys()))
    if not log_getiriler or set(log_getiriler.keys()) != set(aligned_prices_dict.keys()): # log getiriler boşsa veya varlıkların isimler eşleşmiyorsa hata verir
         print("Hata: Log getiri hesaplamada sorun oluştu veya tüm hizalanmış varlıklar için getiri hesaplanamadı.")
         return {"error": "Risk analizi için log getiri hesaplamada sorun oluştu."}
    log_returns_df = pd.DataFrame(log_getiriler) # hizalama adımı filan yapıldığından dolayı artık log getiriler dataframe'e dönüştürülür
    print("Log getiriler DataFrame oluşturuldu. Boyut:", log_returns_df.shape)
    print("Log getiriler DataFrame sütunları:", log_returns_df.columns.tolist())
    
    
    aday_dagilimlar = ['norm', 't', 'laplace'] # en iyi dağılımı bulma fonksiyonun da kullanılacak
    varlik_dagilimlari = {} # her veri serisi yani varlık adını anahtar, o varlığa en iyi uyan dağılımın adı ve parametrelerini içeren bir başka sözlüğü değer olarak saklayacaktır
    for asset in log_returns_df.columns: # logdf sütunları yani varlık isimleri tek tek alınır
        seri = log_returns_df[asset].dropna() # ilgili varlığın log getirisi serisi alınır ve nan değerleri atılır
        dagilim_adi, parametreler = en_iyi_dagilimi_bul(seri, aday_dagilimlar) #  en iyi dağılımı bulma fonksiyonu çağrılır ve dönen dağılım adı ve parametreleri alınır
        varlik_dagilimlari[asset] = {'dist': dagilim_adi, 'params': parametreler} # her varlık için dağılım adı ve parametreleri saklanır (iç içe sözlük olarak en üstte boş sözlük tanımlanırken bahsedilmişti)


    if set(log_getiriler.keys()) != wallet_asset_keys: # hesaplanan log getiri varlıkları ile cüzdandaki varlıkları karşılaştırır
         print("Hata: Log getiri anahtarları ile cüzdan varlık anahtarları eşleşmiyor")
         print("Cüzdan Anahtarları:", list(wallet_asset_keys))
         print("Log Getiri Anahtarları:", list(log_getiriler.keys()))
         return {"error": "Varlık anahtarları eşleşmedi."}
    print("Varlık eşleşme kontrolü başarılı.")


    print("Drift hesaplanıyor...")
    drift = drift_hesapla(log_returns_df) # hazırlanan log getiriler dataframe'i alınır ve her sütunun ortalamasını (drift) hesaplanır
    if not any(drift.values()): # drift hesaplanamazsa hata verir
         print("Hata: Drift hesaplanamadı.")
         return {"error": "Risk analizi için drift hesaplanamadı."}
    print("Hesaplanan Drift:", drift)


    volatility = {}
    if GARCH_AVAILABLE: # en baştaki kontrolün aynısı true ise devam
        print("GARCH(1,1) ile volatilite hesaplanıyor...")
        volatility = garch_volalite_hesapla(log_returns_df) # hazırlanan log getiri df garch fonk. gönderilir
        if not all(v is not None and v > 0 for v in volatility.values()): # garch sonucu döndürülen sözlükteli volalitelerin hepsinin eksiksiz ve pozitiflik kontrolü
             print("Uyarı: GARCH volatilitesi hesaplanamadı veya sıfır/negatif. Basit standart sapma kullanılacak.")
             volatility = volalite_hesapla(log_returns_df) # eksiklik veya pozitif olmama durumunda normal volalite hesaplanır
    else: # en başta gach modelde sıkıntı çıkması durumunda da normal vol hesaplanır
        print("GARCH kütüphanesi yüklü değil. Basit standart sapma ile volatilite hesaplanıyor.")
        volatility = volalite_hesapla(log_returns_df)
    if not any(volatility.values()): # en az bir tane pozitif değer yoksa hata verir
         print("Hata: Yeterli volatilite verisi hesaplanamadı.")
         return {"error": "Risk analizi için yeterli volatilite verisi hesaplanamadı."}
    if not all(v > 0 for v in volatility.values()): # yine en son pozitiflik ve eksiklik kontrolü
         print("Uyarı: Bazı varlıklar için volatilite sıfır veya negatif hesaplandı. Bu durum simülasyonu etkileyebilir.")
    print("Hesaplanan Volatilite:", volatility)


    print("Kovaryans matrisi ve Cholesky ayrışımı hesaplanıyor...")
    cholesky_matrix_L = kovaryans_hesapla(log_returns_df, volatility)
    if cholesky_matrix_L.shape[0] == 0: # boş matris dönüp dönmedi yani ayrışım hesaplanıp hesaplanmadığı kontrolü
         print("Hata: Cholesky matrisi hesaplanamadı veya boş.")
         return {"error": "Risk analizi için kovaryans/korelasyon matrisi hesaplanamadı."}


    num_days_simulation = 7 # Kaç gün sonrası tahmin edilecek (1 hafta)
    num_monte_carlo_simulations = 10000 # kaç simülasyon yapılacağı (10bin kere 7 günlük patikalar yapılacak)

    simulated_values = mcs_yap(
        drift,  # log getirilerin ortalaması
        volatility, # Tercihen GARCH volatilitesi, yoksa basit volatilite kullanılır
        cholesky_matrix_L, # Hesaplanan Cholesky L matrisi
        initial_asset_values, # Başlangıç varlık değerleri (Sadece cüzdandaki varlıklar)
        num_simulations=num_monte_carlo_simulations,
        num_days=num_days_simulation,
        varlik_dagilimlari=varlik_dagilimlari # varlık dağılımı bilgileri (dağılım adı ve parametreleri)
    )

    if not simulated_values: # herhangi bir hata durumunda boş liste dönerse sim durur
        print("Hata: Monte Carlo simülasyonu sonuç üretmedi.")
        return {"error": "Monte Carlo simülasyonu sonuç üretmedi. Lütfen veri kaynaklarını ve parametreleri kontrol edin."}


    confidence_level = 0.95
    print(f"Risk metrikleri hesaplanıyor (Güven Seviyesi: %{int(confidence_level*100)})...")
    risk_metrics = risk_metrikleri_hesapla(simulated_values, initial_portfolio_value, confidence_level=confidence_level)
    # sim sonuçları , başlangıç portföy değeri ve güven aralığı ile risk metrikleri hesaplanır


    wallet_volatility = {asset: volatility.get(asset, 0.0) for asset in initial_asset_values.keys()} # cüzdanda bulunan varlıklar için yeni sözlük oluşturulur ve volaliteleri atanır yoksa oto 0 atanır
    risk_ranking = sorted(wallet_volatility.items(), key=lambda item: item[1], reverse=True) # varlık adı ve volatilite çiftlerinden oluşan sıralı bir liste döner. Listenin başı en riskli (en yüksek volatilite), sonu en az riskli (en düşük volatilite) varlığı temsil eder.
    risk_ranking_dict = {item[0]: item[1] for item in risk_ranking} # sıralı liste tekrar Sözlüğe dönüştürülür


    suggestions = {"arttir": [], "azalt": []} # yatırım önerileri için boş listeler oluşturulur
    if risk_ranking: # yukarıda ki risk listesi boş değilse
        suggestions["arttir"].append(risk_ranking[-1][0]) # liste sonundaki yani en düşük volaliteli varlık arttırılabilir
        if len(risk_ranking) > 1: # Birden fazla varlık varsa
            suggestions["azalt"].append(risk_ranking[0][0]) # liste başındaki varlığı azalt önerilir
    else: # risk listesi boşsa
        print("Uyarı: Risk sıralaması boş olduğundan yatırım önerileri oluşturulamadı.")

    results = { # hesaplanan sonuçlar burada saklanır
        "initial_value": initial_portfolio_value,
        f"VaR_{int(confidence_level*100)}": risk_metrics.get(f"VaR_{int(confidence_level*100)}", 0.0), # belirtilen anahtar yoksa .get ile eksikliklerde 0.0 atanır
        f"CVaR_{int(confidence_level*100)}": risk_metrics.get(f"CVaR_{int(confidence_level*100)}", 0.0),
        "risk_ranking": risk_ranking_dict,
        "suggestions": suggestions
    }
    print("Risk analizi tamamlandı.")
    return results



if __name__ == "__main__":
    risk_analiz_yap()
    # print("Risk analizi başlatılıyor ...")
    # # app.py'den gelecek örnek bir başlangıç varlık değerleri sözlüğü
    # # Bu değerler, kullanıcının cüzdanındaki her bir varlığın TL cinsinden güncel değeridir.
    # # Anahtarların run_risk_analysis içinde beklenen formatta olması önemlidir.
    # # Örnek kullanımda, cüzdanda sadece Altın olduğunu varsayalım.
    # example_initial_asset_values = {
    #     "USD": 50000.0, # 50.000 TL değerinde Dolar
    #     "EUR": 30000.0, # 30.000 TL değerinde Euro
    #     "Gold_Gram_TL": 20000.0 # 20.000 TL değerinde Gram Altın
    # }

    # risk_analysis_results = risk_analiz_yap(example_initial_asset_values)

    # if "error" not in risk_analysis_results:
    #     print("\nRisk Analizi Sonuçları:")
    #     print(f"Başlangıç Portföy Değeri: {risk_analysis_results['initial_value']:.2f} TL")
    #     # Güven seviyesi %95 olarak ayarlandığından anahtarlar VaR_95 ve CVaR_95 olacaktır.
    #     print(f"%95 VaR (Beklenen Maksimum Kayıp): {risk_analysis_results.get('VaR_95', 0.0):.2f} TL")
    #     print(f"%95 CVaR (En Kötü Senaryoların Ortalama Kaybı): {risk_analysis_results.get('CVaR_95', 0.0):.2f} TL")
    #     print("\nVarlık Risk Sıralaması (Volatiliteye Göre):")
    #     # Risk sıralaması sözlüğünü kontrol etmeden döngüye girmeyelim
    #     if risk_analysis_results.get('risk_ranking'):
    #         for asset, vol in risk_analysis_results['risk_ranking'].items():
    #             print(f"{asset}: {vol:.4f}")
    #     print("\nYatırım Önerileri:")
    #     # Yatırım önerileri sözlüğünü kontrol etmeden erişmeyelim
    #     if risk_analysis_results.get('suggestions'):
    #          print(f"Artırılması Önerilen: {', '.join(risk_analysis_results['suggestions'].get('arttir', []))}")
    #          print(f"Azaltılması Önerilen: {', '.join(risk_analysis_results['suggestions'].get('azalt', []))}")
    #     else:
    #          print("Yatırım önerileri oluşturulamadı.")

    # else:
    #     print(f"Risk analizi çalıştırılırken hata oluştu: {risk_analysis_results['error']}")