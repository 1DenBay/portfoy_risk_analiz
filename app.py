import streamlit as st
import plotly.express as px 
import requests
import api 
import db
import riskanaliz
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import pandas as pd


st.set_page_config(page_title="Cüzdan Uygulaması", layout="wide") # sayfayı tam boyutunda kullanmak için


# Varlık türlerini sabit olarak tanımla
VARLIK_TURLERI = ["TL", "Altın", "Dolar", "Euro"]
VARLIK_KISALTMALARI = {"Dolar": "USD", "Euro": "EUR", "Altın": "XAU"} # tarihsel veri için


# API İLE BAĞLANTI
API_URL = "http://127.0.0.1:8000/get-market-data" #apinin güncel verileri json oalrak gösterdiği sayfa
API_WEEKLY_URL = "http://127.0.0.1:8000/get-weekly"
API_MONTHLY_URL = "http://127.0.0.1:8000/get-monthly"
API_YEARLY_URL = "http://127.0.0.1:8000/get-yearly"

@st.cache_data(ttl=3000) # sürekli veri yenilenmesin diye zamanlayıcı
def get_exchange_rates(): # apiden verileri çekerek bu ana dosyada kullanılmasını sağlayan fonksiyondur

    try:
        response = requests.get(API_URL)  # API'ye GET isteği gönderir
        if response.status_code == 200:  # Yanıt başarılıysa devam , 200 kodu http de başarılı kodudur
            return response.json()  # JSON verisini döndür
        else:
            return {"error": f"API hatası: {response.status_code}"}  # 200 dışında diğer kodlar hatadır , Hata mesajı
    
    except Exception as e:
        return {"error": str(e)} # hatanın nerde olduğunu görelim diye kodu fırlatır


@st.cache_data(ttl=10000)
def get_weekly_data():
    try:
        response = requests.get(API_WEEKLY_URL)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"error": f"Haftalık veri API hatası: {e}"}
    except ValueError:
        return {"error": "Haftalık veri API'sinden geçersiz JSON yanıtı"}


@st.cache_data(ttl=10000)
def get_monthly_data():
    try:
        response = requests.get(API_MONTHLY_URL)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"error": f"Aylık veri API hatası: {e}"}
    except ValueError:
        return {"error": "Aylık veri API'sinden geçersiz JSON yanıtı"}    


@st.cache_data(ttl=10000)
def get_yearly_data():
    try:
        response = requests.get(API_YEARLY_URL)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"error": f"Yıllık veri API hatası: {e}"}
    except ValueError:
        return {"error": "Yıllık veri API'sinden geçersiz JSON yanıtı"}

#------------------


# Kullanıcıdan alınan verileri kontrol eder ve save_wallet_data fonksiyonunu çağırır
def add_to_wallet(varlik_turu, miktar, satis_fiyati, alis_fiyati):
    if not miktar or alis_fiyati is None or satis_fiyati:  # Miktar ve maliyet bilgileri kontrol edilir
        st.sidebar.warning("Lütfen Miktar ve Alış Fiyat bilgilerini girin ve Satış Fiyatı boş bırakın.", icon="⚠️")
        return

    # Belirli bir varlık türü için bilgileri alır
    mevcut_varlik = db.load_wallet_data(varlik_turu)

    if mevcut_varlik and varlik_turu in mevcut_varlik: #varlık daha önceden cüzdanda varsa
        mevcut_miktar = mevcut_varlik[varlik_turu]["miktar"]
        mevcut_maliyet = mevcut_varlik[varlik_turu]["maliyet"]

        # yeni maliyet hesaplaması
        toplam_maliyet = (mevcut_miktar * mevcut_maliyet) + (miktar * alis_fiyati) # mevcut maliyet hesabı + yeni mesaliyet
        yeni_miktar = mevcut_miktar + miktar
        yeni_maliyet = toplam_maliyet / yeni_miktar

    else: #varlık cüzdan yoksa ilk defa giriliyorsa
        yeni_miktar = miktar
        yeni_maliyet = alis_fiyati # maliyet saten miktar * fiyat olacağından miktarlar gider direkt fiyata eşit olur ilk maliyet

    # Veritabanına kaydet
    db.save_wallet_data(varlik_turu, yeni_miktar, yeni_maliyet, alis_fiyati, satis_fiyati)

    st.success(f"{varlik_turu} cüzdana eklendi ve güncellendi!")
    st.sidebar.empty()  # Sidebar'ı temizle



# VARLIKLARIN TOPLAM DEĞERLERİNİ HESAPLAR (alış fiyatından)
def calculate_asset():
    exchange_rates = get_exchange_rates()  # API verilerini al
    toplam_deger = 0  # Toplam değer için havuz
    wallet_data = db.load_wallet_data()  # Veritabanından cüzdan verilerini al

    for varlik in wallet_data:  # Varlıktaki ögeler sırayla alınır
        miktar = wallet_data[varlik]["miktar"]

        if varlik == VARLIK_TURLERI[2]:  # Dolar
            price = exchange_rates["USDa"]   
        elif varlik == VARLIK_TURLERI[3]:  # Euro
            price = exchange_rates["EURa"]
        elif varlik == VARLIK_TURLERI[1]:  # Altın
            price = exchange_rates["Gold_Gram_TLa"]
        else:  # TL için
            price = 1

        if price is not None:  # Fiyat doğru alınmışsa
            toplam_deger += miktar * price  # O varlığın güncel fiyatı hesaplanır

    return toplam_deger  # Toplam değeri döndür



# Cüzdandan varlık çıkarma işlemi
def remove_wallet(varlik_turu, miktar, satis_fiyati):
    wallet_data = db.load_wallet_data(varlik_turu)  # Veritabanından cüzdan verilerini al

    if varlik_turu in wallet_data:
        mevcut_miktar = wallet_data[varlik_turu]["miktar"]
        mevcut_maliyet = wallet_data[varlik_turu]["maliyet"]
        mevcut_kar_zarar = wallet_data[varlik_turu]["kar_zarar"]

        if satis_fiyati is None: #alış fiyatı girilmiş iken satış fiyat boş olunca hata veriyorda ona çözüm
            st.sidebar.warning("Lütfen Satış Fiyatı bilgisini girin.", icon="⚠️")
        
        else:
            if miktar > mevcut_miktar:
                st.sidebar.warning(f"Yetersiz miktar. Mevcut miktar: {mevcut_miktar}", icon="⚠️")
            else:
                yeni_miktar = mevcut_miktar - miktar

                elde_bulunan_deger = mevcut_miktar * mevcut_maliyet
                satisi_yapilan = miktar * satis_fiyati
                toplam_kar_zarar = satisi_yapilan - elde_bulunan_deger #son işlemle beraber toplam kar-zarara durumu

                if yeni_miktar == 0:
                    db.remove_wallet_data(varlik_turu)  # Veritabanından varlığı sil
                    st.success(f"{varlik_turu} cüzdandan çıkarıldı!")
                    st.info(f"Son İşlemde Bu Varlıktan Elde Edilen Kâr/Zarar: {toplam_kar_zarar:.2f} TL")
                else:
                    db.update_wallet_data(varlik_turu, yeni_miktar, toplam_kar_zarar)  # Veritabanını güncelle
                    st.success(f"{varlik_turu} cüzdandan çıkarıldı ve güncellendi!")
    else:
        st.sidebar.warning(f"Cüzdanda yeterli {varlik_turu} yok.", icon="⚠️")



# Anlık Kar/Zarar Hesaplama
def kar_zarar_anlik(varlik):
    wallet_data = db.load_wallet_data(varlik)  # Veritabanından cüzdan verilerini al
    toplam_kar_zarar = 0

    for varlik, bilgiler in wallet_data.items():
        mevcut_miktar = bilgiler["miktar"]
        mevcut_maliyet = bilgiler["maliyet"]

        if varlik == VARLIK_TURLERI[2]:  # Dolar
            price = get_exchange_rates()["USDa"]
        elif varlik == VARLIK_TURLERI[3]:  # Euro
            price = get_exchange_rates()["EURa"]
        elif varlik == VARLIK_TURLERI[1]:  # Altın
            price = get_exchange_rates()["Gold_Gram_TLa"]
        else:  # TL için -> saten tl için çalışmayacak (display fonksiyonunda tl olursa fonksiyonu çağırmayacak)
            price = 1

        if price is not None:
            anlik_deger = mevcut_miktar * price
            toplam_kar_zarar += anlik_deger - (mevcut_maliyet * mevcut_miktar)

    return toplam_kar_zarar



# GÜNCEL CÜZDANI GÖSTERME
def display_wallet():
    st.subheader("💼 Cüzdan")

    wallet_data = db.load_wallet_data()

    if wallet_data:
        for varlik, bilgiler in wallet_data.items():
            if varlik.lower() == "tl":  # Eğer varlık TL ise
                st.write(f"**{varlik}** - Miktar: {bilgiler['miktar']:.2f}")
            else:
                anlik_kar_zarar = kar_zarar_anlik(varlik)  # TL dışındaki varlıklar için hesaplama
                st.write(f"**{varlik}** ➡️ Miktar: {bilgiler['miktar']:.2f} |--⚪️--| Maliyet: {bilgiler['maliyet']:.2f} TL  |--⚪️--| Güncel Kar/Zarar: {(anlik_kar_zarar):.2f} TL |--⚪️--| Son İşlem İçin Kar/Zarar: {bilgiler['kar_zarar']:.2f} TL")
    else:
        st.info("Henüz cüzdana eklenmiş bir varlık yok.")



# Cüzdan dağılımı için pasta grafik oluşturma
# def display_wallet_distribution():
#     st.subheader("📊 Cüzdan Dağılımı")
#     wallet_data = db.load_wallet_data()
#     if wallet_data:
#         labels = []
#         sizes = []  # Her varlığın yüzdesel olarak büyüklüğünü tutar
#         for varlik, bilgiler in wallet_data.items():
#             if varlik != "TL":
#                 labels.append(varlik)
#                 sizes.append(bilgiler["miktar"])

#         # Sunburst grafiği için DataFrame oluştur
#         df = pd.DataFrame({
#             'Varlık': labels,
#             'Miktar': sizes
#         })

#         # Plotly Express ile sunburst grafiği oluştur
#         fig = px.sunburst(
#             df,
#             path=['Varlık'],  # Hiyerarşik yapı: Sadece varlık türleri
#             values='Miktar',  # Her bölümün büyüklüğü
#             color='Varlık',  # Renklendirme (isteğe bağlı)
#             color_discrete_sequence=['gold', 'silver', 'skyblue', 'lightcoral'],  # Renk paleti
#         )

#         st.plotly_chart(fig, use_container_width=True, key="wallet_distribution")  # Grafiği Streamlit'te göster
#     else:
#         st.info("Henüz cüzdana eklenmiş bir varlık yok.")


# Anlık kar/zarar nokta grafiği fonksiyonu
# def display_kar_zarar_graph():
#     st.subheader("📈 Anlık Kar/Zarar Durumu")
#     wallet_data = db.load_wallet_data()
#     if wallet_data:
#         varliklar = []
#         kar_zararlar = []
#         for varlik, bilgiler in wallet_data.items():
#             if varlik != "TL":  # TL için kar/zarar hesaplamıyoruz
#                 anlik_kar_zarar = kar_zarar_anlik(varlik)
#                 varliklar.append(varlik)
#                 kar_zararlar.append(anlik_kar_zarar)

#         df = pd.DataFrame({'Varlık': varliklar, 'Kar/Zarar': kar_zararlar})

#         fig = px.scatter(df, x='Varlık', y='Kar/Zarar', size=[50]*len(df), color='Varlık',
#                          labels={'Kar/Zarar': 'Anlık Kar/Zarar (TL)'})
#         st.plotly_chart(fig, use_container_width=True, key="kar_zarar")
#     else:
#         st.info("Henüz cüzdana eklenmiş bir varlık yok.")




def main():
    db.initialize_db()  # Veritabanını başlatır

    # yardım butonu
    if 'help_clicked' not in st.session_state: #sistem açıldığında tanımlama yapılır
        st.session_state.help_clicked = False
    def go_to_help_tab():
        st.session_state.help_clicked = True
    def close_help():
        st.session_state.help_clicked = False
    st.sidebar.button("Yardım (F1)", on_click=go_to_help_tab) # butona tıklandığında true döner
    if st.session_state.help_clicked: # true dönerse 
        help_container = st.container() # Yardım mesajı için bir konteyner oluştur (radio mesaj gibi bişey)
        with help_container:
            st.info("""
            🆘 Yardım ve Kullanım Kılavuzu 🆘
            
            Uygulama Nasıl Kullanılır?
            1. Sol kenar çubuğundan varlık türünü (TL, Altın, Dolar, Euro) seçin.
            2. 'Miktar' ve 'Alış Fiyatı' bilgilerini girin.
            3. '➕ Cüzdana Ekle' butonuna tıklayarak varlığı cüzdanınıza ekleyin.
            4. Cüzdanınızdaki varlıkları 'Portföy & Risk Analizi' sekmesinde görebilirsiniz.
            5. Risk analizi sonuçları aynı sekmede görüntülenecektir.
            6. Varlık satmak için 'Miktar' ve 'Satış Fiyatı' bilgilerini girip '➖ Cüzdandan Çıkar' butonuna tıklayın.
            7. '0️⃣ Cüzdanı Boşalt' butonu ile tüm cüzdanı temizleyebilirsiniz.
            """, icon="ℹ️")
            if st.button("❌ Kapat", key="close_help"): # kapat butonu
                close_help()
                st.rerun()


    st.sidebar.header("📌 Varlık Seçimi")

    # Varlık türleri için seçim kutusu
    varlik_turu = st.sidebar.selectbox("Varlık Türü", VARLIK_TURLERI)  # ilk başta belirlenen sabit liste kullanıldı
    # Miktar ve maliyet giriş kutuları
    miktar = st.sidebar.number_input("Miktar", min_value=0.0, format="%.2f", value=None)
    alis_fiyati = st.sidebar.number_input("Alış Fiyatı", min_value=0.0, format="%.2f", value=None)
    satis_fiyati = st.sidebar.number_input("Satış Fiyatı", min_value=0.0, format="%.2f", value=None)

    # Cüzdana Ekle butonu
    if st.sidebar.button("➕ Cüzdana Ekle"):
        add_to_wallet(varlik_turu, miktar, satis_fiyati, alis_fiyati)
    # Cüzdandan Çıkar butonu
    if st.sidebar.button("➖ Cüzdandan Çıkar"):
        remove_wallet(varlik_turu, miktar, satis_fiyati)
    # Cüzdanı Boşalt butonu
    if st.sidebar.button("0️⃣ Cüzdanı Boşalt"):
        db.empty_wallet()
        

    st.markdown("""
        <h1 style='color: #ffffff; font-family: "Thin 100"; font-size: 35px; text-align: center;'>
            Varlık Yönetimi ve Risk Analizi
        </h1>
    """, unsafe_allow_html=True)


    # Sekmeleri oluştur
    tab1, tab2, tab3 = st.tabs(
        ["Piyasa Verileri", "Portföy & Risk Analizi", "🆘 Yardım/Kullanım Kılavuzu"]
    )


    with tab1:
        guncel = get_exchange_rates() # data içerisinden json verileri sözlük şeklinde tutulur

        # Veri kontrolü
        if "error" in guncel: # hata alırak
            st.error(guncel["error"])  # Hatayı göster
        else: # hata yoksa
            st.markdown("<br>", unsafe_allow_html=True) # boşluk
            st.markdown("""
                <h2 style='color: #ffffff; font-family: "Thin 100"; text-align: center;'>
                    🏪  Güncel Piyasa Verileri 🏪
                </h2>
            """, unsafe_allow_html=True)

        
            col_usd, col_eur, col_gold = st.columns(3) #  # 3 sütun oluştur
            with col_usd:
                st.subheader("💵 Dolar/TL")
                st.write(f"**ALIŞ:** {guncel.get('USDa', '--')}") # .get() kullanarak anahtar yoksa hata yerine '--' göster
                st.write(f"**SATIŞ:** {guncel.get('USDs', '--')}")
            with col_eur:
                st.subheader("💶 Euro/TL")  
                st.write(f"**ALIŞ:** {guncel.get('EURa', '--')}")
                st.write(f"**SATIŞ:** {guncel.get('EURs', '--')}")
            with col_gold:
                st.subheader("🧈 Gram Altın/TL")
                st.write(f"**ALIŞ:** {guncel.get('Gold_Gram_TLa', '--')}")
                st.write(f"**SATIŞ:** {guncel.get('Gold_Gram_TLs', '--')}")


        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("""
            <h1 style='color: #ffffff; font-family: "Thin 100"; font-size: 35px; text-align: center;'>
                📈 Piyasa Grafikleri 📈
            </h1>
        """, unsafe_allow_html=True)


        # Grafik için zaman aralığı seçimi
        time_period = st.radio(
            "Grafik İçin Zaman Aralığını Seçin:",
            ('Haftalık', 'Aylık', 'Yıllık'),
            horizontal=True # Seçenekleri yan yana gösterir
        )

        # Seçime göre veriyi çek
        period_data = None
        data_keys = {} # API'den çekilen verideki varlık anahtarlarını tutacak

        if time_period == 'Haftalık':
            period_data = get_weekly_data()
            data_keys = {'Dolar': 'USDh', 'Euro': 'EURh', 'Altın': 'Gold_Gram_TLh'} # api.py'deki anahtarlar
        elif time_period == 'Aylık':
            period_data = get_monthly_data()
            data_keys = {'Dolar': 'USDa', 'Euro': 'EURa', 'Altın': 'Gold_Gram_TLa'} 
        elif time_period == 'Yıllık':
            period_data = get_yearly_data()
            data_keys = {'Dolar': 'USDy', 'Euro': 'EURy', 'Altın': 'Gold_Gram_TLy'}


        if period_data and "error" not in period_data:
            col1, col2, col3 = st.columns(3) # grafikler için 3 sütun oluştur
            asset_dfs = {} # varlıkların DataFrame'lerini saklamak için bir sözlük
            chart_asset_names = { # Grafik başlıkları için anahtarları eşleştir
                'USDh': 'Dolar/TL', 'EURh': 'Euro/TL', 'Gold_Gram_TLh': 'Gram Altın/TL',
                'USDa': 'Dolar/TL', 'EURa': 'Euro/TL', 'Gold_Gram_TLa': 'Gram Altın/TL',
                'USDy': 'Dolar/TL', 'EURy': 'Euro/TL', 'Gold_Gram_TLy': 'Gram Altın/TL'
            }

            for data_key in data_keys.values(): # data_keys'teki api.py anahtarlarını kullan
                prices = period_data.get(data_key, []) # API'den gelen fiyat listesi, hata olursa boş liste döndürecek
                asset_name_for_chart = chart_asset_names.get(data_key, data_key) # Grafik başlığı için isim al

                if prices: # fiyatlar alındıysa
                    today = datetime.now().date()
                    dates = [today - timedelta(days=i) for i in range(len(prices)-1, -1, -1)][::-1] # Tarihleri en eskiden en yeniye sırala
                    df = pd.DataFrame({'Date': dates, 'Price': prices})
                    asset_dfs[data_key] = df 
                else:
                    asset_dfs[data_key] = pd.DataFrame({'Date': [], 'Price': []})
                    st.info(f"{asset_name_for_chart} grafiği için veri yok.")


            # Grafikleri sütunlarda göster
            # data_keys'teki sıralamayı kullanarak sütunlara yerleştir
            chart_cols = st.columns(len(data_keys)) # Seçilen zaman aralığına göre sütun sayısı

            for i, (asset_display_name, data_key) in enumerate(data_keys.items()):
                with chart_cols[i]:
                    asset_name_for_chart = chart_asset_names.get(data_key, data_key) # Grafik başlığı için isim al
                    st.subheader(asset_name_for_chart)
                    if data_key in asset_dfs and not asset_dfs[data_key].empty:
                        st.line_chart(asset_dfs[data_key], x='Date', y='Price')
                        # else: # Veri yok mesajı yukarıda gösteriliyor
                        #     st.info(f"{asset_name_for_chart} grafiği için veri yok.")


        elif period_data and "error" in period_data:
            # Veri çekilirken hata oluşursa mesaj göster
            st.error(f"Grafik verisi çekilirken hata: {period_data['error']}")
        else:
            # Veri henüz yüklenmediyse veya mevcut değilse bilgi mesajı göster
            st.info("Grafik verisi yükleniyor veya mevcut değil.")

    with tab2:
        # Tab2 içeriği
        # Ana başlık
        st.markdown("""
            <h1 style='color: #ffffff; font-family: "Thin 100"; font-size: 35px; text-align: center;'>
                🛒 PORTFÖY
            </h1>
        """, unsafe_allow_html=True)

        
        # Cüzdanı göster
        display_wallet()
        # Cüzdan dağılım grafiğini göster
        # display_wallet_distribution()
        # Grafiklerin yan yana gösterimi için sütunlar oluştur 
        #display_kar_zarar_graph()
        toplam_deger = calculate_asset()


        if toplam_deger > 0:
            st.write(f"💰 Cüzdan Toplam Değeri: **{toplam_deger:.2f} TL**")
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown("""
                <h1 style='color: #ffffff; font-family: "Thin 100"; font-size: 35px; text-align: center;'>
                    📊 RİSK ANALİZİ
                </h1>
            """, unsafe_allow_html=True)

            wallet_data = db.load_wallet_data() # Cüzdan verilerini yükle
            initial_asset_values = {}
            exchange_rates = get_exchange_rates() # Güncel fiyatları al

            #RİSK ANALİZİ İÇİN VARLIKLARI DÜZENLE
            if wallet_data and exchange_rates and "error" not in exchange_rates:
                for varlik, bilgiler in wallet_data.items():
                    miktar = bilgiler["miktar"]
                    current_price = None

                    if varlik == "Dolar":
                        current_price = exchange_rates.get("USDa")
                        risk_analysis_key = "USD"
                    elif varlik == "Euro":
                        current_price = exchange_rates.get("EURa")
                        risk_analysis_key = "EUR"
                    elif varlik == "Altın":
                        current_price = exchange_rates.get("Gold_Gram_TLa")
                        risk_analysis_key = "Gold_Gram_TL"
                    elif varlik == "TL":
                        current_price = 1.0 # TL'nin değeri 1 TL
                        risk_analysis_key = "TL" # TL için risk analizi yapmıyacağımızdan gereksiz

                    # Sadece risk analizi yapılacak varlıkları (USD, EUR, Gold_Gram_TL) initial_asset_values'a ekle
                    if current_price is not None and risk_analysis_key in ["USD", "EUR", "Gold_Gram_TL"]:
                        initial_asset_values[risk_analysis_key] = miktar * current_price


            # initial_asset_values sözlüğü doluysa risk analizini çalıştır
            if initial_asset_values:
                sim_results = riskanaliz.risk_analiz_yap(initial_asset_values)

                # Simülasyon sonuçlarını kontrol et ve göster
                if sim_results and "error" not in sim_results:
                    # Sonuçları arayüzde göster
                    st.write(f"**Başlangıç Portföy Değeri:➡️** {sim_results['initial_value']:.2f} TL")
                    # Güven seviyesi %95 olarak ayarlandığından anahtarlar VaR_95 ve CVaR_95 olacaktır.
                    st.write(f"**%95 VaR (Beklenen Maksimum Kayıp):➡️** {sim_results.get('VaR_95', 0.0):.2f} TL")
                    st.write(f"**%95 CVaR (En Kötü Senaryoların Ortalama Kaybı):➡️** {sim_results.get('CVaR_95', 0.0):.2f} TL")

                    st.write("**Varlık Risk Sıralaması (Volatiliteye Göre)**")
                    # Risk sıralaması sözlüğünü kontrol etmeden döngüye girme
                    if sim_results.get('risk_ranking'):
                        for k, v in sim_results['risk_ranking'].items():
                            st.write(f"💠{k}: {v:.4f}") # Volatilite değerlerini 4 ondalık basamakla göster



                    st.markdown("""
                        <h1 style='color: #ffffff; font-family: "Thin 100"; font-size: 35px; text-align: center;'>
                            🦾 YATIRIM TAVSİYELERİ
                        </h1>
                    """, unsafe_allow_html=True)

                    # Yatırım önerileri sözlüğünü kontrol etm
                    if sim_results.get('suggestions'):
                        st.write("**Artırılması Önerilen Varlıklar:✅**", ", ".join(sim_results['suggestions'].get('arttir', [])))
                        st.write("**Azaltılması Önerilen Varlıklar:❌**", ", ".join(sim_results['suggestions'].get('azalt', [])))
                    else:
                        st.info("Yatırım önerileri oluşturulamadı.")

                else:
                    # Risk analizi fonksiyonundan hata döndüyse göster
                    st.error(f"Risk analizi çalıştırılırken hata oluştu: {sim_results.get('error', 'Bilinmeyen hata.')}")

            else:
                # initial_asset_values sözlüğü boşsa (cüzdanda USD, EUR, Altın yoksa)
                st.warning("Risk analizi yapmak için cüzdanınızda Dolar, Euro veya Altın bulunmalıdır.", icon="⚠️")

        else:
            st.markdown("""
                <h3 style='color: #ffcccb; text-align: center;'>
                    🚫 Cüzdan Boş Olduğundan - Risk Analizi Yapılamadı 🚫
                </h3>
            """, unsafe_allow_html=True)

    with tab3:
        # Tab3 içeriği
        st.markdown("""
            <h3 style='color: #ffffff; font-family: "Thin 100"; text-align: center;'>
                🆘 Yardım ve Kullanım Kılavuzu 🆘
            </h3>
        """, unsafe_allow_html=True)
        st.subheader("Uygulama Nasıl Kullanılır?")
        st.write("1. Sol kenar çubuğundan varlık türünü (TL, Altın, Dolar, Euro) seçin.")
        st.write("2. 'Miktar' ve 'Alış Fiyatı' bilgilerini girin.")
        st.write("3. '➕ Cüzdana Ekle' butonuna tıklayarak varlığı cüzdanınıza ekleyin.")
        st.write("4. Cüzdanınızdaki varlıkları 'Portföy & Risk Analizi' sekmesinde görebilirsiniz.")
        st.write("5. Risk analizi sonuçları aynı sekmede görüntülenecektir.")
        st.write("6. Varlık satmak için 'Miktar' ve 'Satış Fiyatı' bilgilerini girip '➖ Cüzdandan Çıkar' butonuna tıklayın.")
        st.write("7. '0️⃣ Cüzdanı Boşalt' butonu ile tüm cüzdanı temizleyebilirsiniz.")

        st.subheader("Piyasa Verileri Sekmesi")
        st.write("Bu sekmede güncel döviz ve altın fiyatlarını ve geçmiş fiyat grafiklerini görebilirsiniz.")

        st.subheader("Portföy & Risk Analizi Sekmesi")
        st.write("Bu sekmede cüzdanınızdaki varlıkların toplam değerini, risk analiz sonuçlarını (VaR, CVaR) ve yatırım önerilerini bulabilirsiniz.")

        st.subheader("Risk Analizi Hakkında")
        st.write("Risk analizi, portföyünüzün gelecekte belirli bir zaman ufkunda (örneğin 1 hafta) karşılaşabileceği potansiyel maksimum kaybı (VaR) ve en kötü senaryolardaki ortalama kaybı (CVaR) tahmin etmek için Monte Carlo simülasyonunu kullanır.")
        st.write("Analiz, geçmiş piyasa verilerinden (ortalama getiri, volatilite, varlıklar arası korelasyon) öğrenilen istatistiksel modellere dayanır.")
        st.write("**Önemli Not:** Risk analizi sonuçları tahminidir ve gelecekteki piyasa hareketlerinin garantisi değildir.")
        st.write("**Önemli Not:** Yatırım tavsiyeleri başlığında önerilen tavsiyeler tamamen tahmini olup kesin yatırım tavsiyesi değildir.")


# -- Programı başlat --
if __name__ == "__main__":
    main()
