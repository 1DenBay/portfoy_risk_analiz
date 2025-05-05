# SQLİTE BAĞLANTISI -> sqlite avantajı yerel dosyada saklama
import sqlite3

# Tablo adını sabit olarak tanımla
TABLE_NAME = "wallet"

# SQLite veritabanı dosyasına bağlanma
def connect_db():
    conn = sqlite3.connect('cuzdan.db')  # Veritabanı dosyasına bağlan
    return conn



# veritabanında tablo yoksa ilk kez tablo oluşturur
def initialize_db():
    conn = connect_db()
    cursor = conn.cursor()
    
    # Tablo adını sabit kullanarak oluştur
    cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
            varlik_turu TEXT PRIMARY KEY,
            miktar REAL,
            maliyet REAL,
            alis_fiyati REAL,
            satis_fiyati REAL,
            kar_zarar REAL
        )
    ''')      # Tabloyu wallet olarak oluşturuyoruz en başta sabit olsun diye adı atadık saten
    
    conn.commit()
    conn.close()



# Veritabanında cüzdan verilerini kaydetme
def save_wallet_data(varlik_turu, miktar, maliyet, alis_fiyati, satis_fiyati):

    conn = connect_db()
    cursor = conn.cursor()
    
    # Varlık türü veritabanında var mı kontrol et
    cursor.execute(f"SELECT * FROM {TABLE_NAME} WHERE varlik_turu = ?", (varlik_turu,))    
    bulunan_varlik = cursor.fetchone() # varsa ilgili satırı tuple olarak döndürür
    
    if bulunan_varlik:
        # Eğer varlık zaten varsa, miktar ve maliyeti güncelle
        cursor.execute(f"UPDATE {TABLE_NAME} SET miktar = ?, maliyet = ?, alis_fiyati = ?, satis_fiyati = ? WHERE varlik_turu = ?", 
                       (miktar, maliyet, alis_fiyati, satis_fiyati, varlik_turu))
    else:
        # Yeni varlık ekle
        cursor.execute(f"INSERT INTO {TABLE_NAME} (varlik_turu, miktar, maliyet, alis_fiyati, satis_fiyati) VALUES (?, ?, ?, ?, ?)", 
                       (varlik_turu, miktar, maliyet, alis_fiyati, satis_fiyati))

    conn.commit() # işlemleri kaydet
    conn.close() # bağlantıyı kapat



# Veritabanından cüzdan verilerini okuma
def load_wallet_data(varlik_turu=None): 
    
    conn = connect_db()
    cursor = conn.cursor()

    if varlik_turu:
        # Belirli bir varlık türünü getir
        cursor.execute(f"SELECT * FROM {TABLE_NAME} WHERE varlik_turu = ?", (varlik_turu,))
    else:
        # Tüm varlıkları getir
        cursor.execute(f"SELECT * FROM {TABLE_NAME}")

    data = cursor.fetchall()  # Bu bir tuple döndürecektir varlığa ait bilgileri
    conn.close()

    # Burada gelen veriyi bir sözlüğe dönüştürün
    wallet_data = {}
    for row in data:
        varlik_turu = row[0]
        miktar = row[1] if row[1] is not None else 0  # None kontrolü ise direkt 0 ata çünkü hem tüm cüzdan bilgilerini çeken hem de sadece özel bir varlık türü için bilgileri çeken çok yönlü bir fonksiyon
        maliyet = row[2] if row[2] is not None else 0  
        alis_fiyati = row[3] if row[3] is not None else 0
        satis_fiyati = row[4] if row[4] is not None else 0
        kar_zarar = row[5] if row[5] is not None else 0  
        wallet_data[varlik_turu] = {
            "miktar": miktar,
            "maliyet": maliyet,
            "alis_fiyati": alis_fiyati,
            "satis_fiyati": satis_fiyati,
            "kar_zarar": kar_zarar
        }
    return wallet_data   




# Veritabanında varlık miktarını güncelleme -> cüzdanda satış sonrası varlık miktarı değişikliği
def update_wallet_data(varlik_turu, yeni_miktar, yeni_kar_zarar):

    try:
        conn = connect_db()
        cursor = conn.cursor()

        cursor.execute(f"""
            UPDATE {TABLE_NAME} SET miktar = ?, kar_zarar = ? WHERE varlik_turu = ? """, (yeni_miktar, yeni_kar_zarar, varlik_turu))

        conn.commit()

    finally:
        if conn:
            conn.close()  # Bağlantıyı kapat



# Veritabanından varlık silme -> varlık miktarı satış sonrası sıfıra inince silme
def remove_wallet_data(varlik_turu):
    
    try:
        conn = connect_db()
        cursor = conn.cursor()

        # Cüzdandaki varlığı veritabanından sil
        cursor.execute(f"DELETE FROM {TABLE_NAME} WHERE varlik_turu = ?", (varlik_turu,))
        conn.commit()

    finally:
        if conn:
            conn.close()  # Bağlantıyı kapat  



def empty_wallet():
    """
    Cüzdandaki tüm varlıkları siler (veritabanındaki tüm kayıtları temizler).
    """
    try:
        conn = connect_db()  # Veritabanına bağlan
        cursor = conn.cursor()

        # Tüm varlıkları sil
        cursor.execute(f"DELETE FROM {TABLE_NAME}")
        conn.commit()  # Değişiklikleri kaydet
        conn.close()  # Bağlantıyı kapat

        return True  # İşlem başarılı
    except Exception as e:
        print(f"Cüzdan boşaltılırken bir hata oluştu: {str(e)}")
        return False  # İşlem başarısız
    
# artık session_state yerine veriler sqlite ile yerel bilgisayarda depolanacak veriler sayfa yenilenince kaybolmaycak 
# ileride uygulamayı kullanıma açıncada yerelde çalışmayacağı için sqlite - cloud bağlantısı yapacağız ve bu dosyalarıda globale taşıyarak sorunsuz şekilde uygulamayı açacağız
