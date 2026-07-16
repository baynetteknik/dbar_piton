import json
import logging
import time
from datetime import datetime
from typing import Any, Callable
from sqlalchemy import text
from sqlalchemy.orm import Session
import requests

from src.core.models import Customer, UndoPoint, UndoLog, ChangeLog, Site
from src.adapters.dolibarr.dolibarr_client import DolibarrClient
from src.adapters.dolibarr.dolibarr_adapter import DolibarrAdapter

logger = logging.getLogger(__name__)


class CustomerSyncEngine:
    """Cari kartların Dolibarr ERP ile senkronizasyonunu, duraklatma/durdurma mekanizmasını,
    platform bazlı çakışma yönetimini ve geri alma (Undo) işlemlerini yöneten motor."""

    def __init__(self, db: Session, client: DolibarrClient = None, site_id: int = 1):
        self.db = db
        self.client = client
        self.site_id = site_id
        if client:
            self.adapter = DolibarrAdapter(site_id=site_id, client=client)
        else:
            self.adapter = None
            
        # Kontrol Bayrakları (Thread kontrolü için)
        self.is_paused = False
        self.is_cancelled = False

    def check_pause_and_cancel(self, log_fn: Callable[[str], None] = None):
        """Senkronizasyon esnasında duraklatma ve iptal durumlarını denetler."""
        if self.is_paused:
            if log_fn:
                log_fn("⏸️ Senkronizasyon duraklatıldı. Bekleniyor...")
            while self.is_paused:
                if self.is_cancelled:
                    break
                time.sleep(0.5)
            if not self.is_cancelled and log_fn:
                log_fn("▶️ Senkronizasyon devam ettiriliyor...")

        if self.is_cancelled:
            raise InterruptedError("İşlem kullanıcı tarafından durduruldu.")

    def parse_http_error(self, e: Exception) -> str:
        """HTTPError veya genel API hatalarının detaylarını parse eder."""
        if isinstance(e, requests.exceptions.HTTPError) and e.response is not None:
            status_code = e.response.status_code
            try:
                err_data = e.response.json()
                if isinstance(err_data, dict):
                    err_box = err_data.get("error", {})
                    if isinstance(err_box, dict):
                        messages = [str(v) for v in err_box.values() if v]
                        return f"HTTP {status_code}: {' | '.join(messages)}"
                    msg = err_data.get("message") or e.response.text
                    return f"HTTP {status_code}: {msg}"
            except Exception:
                pass
            return f"HTTP {status_code}: {e.response.text[:500]}"
        return str(e)

    def pull_customers_from_dolibarr(
        self,
        conflict_strategy: str = "ignore",  # "ignore" veya "overwrite"
        log_callback: Callable[[str], None] = None,
        progress_callback: Callable[[int, int], None] = None,
        site_id: int = 1
    ) -> int:
        """Belirtilen Dolibarr ERP sitemiz üzerinden carileri çekerek yerel veritabanı ile senkronize eder."""
        self.site_id = site_id
        
        # Seçilen sitenin client'ını dinamik ayağa kaldır (eğer önceden mocklanmadıysa)
        if not self.client:
            site = self.db.query(Site).filter(Site.id == site_id).first()
            if not site:
                raise ValueError(f"Site ID {site_id} bulunamadı.")
                
            from src.core.security.keyring_store import get_api_key
            api_key = get_api_key(site.api_key_account)
            self.client = DolibarrClient(base_url=site.url, api_key=api_key)
            self.adapter = DolibarrAdapter(site_id=site_id, client=self.client)
        else:
            site = self.db.query(Site).filter(Site.id == site_id).first()
            if not self.adapter:
                self.adapter = DolibarrAdapter(site_id=site_id, client=self.client)

        def log(msg: str):
            if log_callback:
                log_callback(msg)
            logger.info(msg)

        log(f"🔄 [{site.name if site else 'Uzak Sistem'}] üzerinden cariler çekiliyor...")
        
        # 1. Geri Alma Noktası oluştur
        undo_point = UndoPoint(
            operation_name="PULL_CUSTOMERS",
            description=f"Dolibarr'dan Cari Çekme. Site: {site.name if site else 'Mock'} | Çakışma: {conflict_strategy.upper()}"
        )
        self.db.add(undo_point)
        self.db.flush()
        
        pulled_count = 0
        added_count = 0
        updated_count = 0
        ignored_count = 0
        page = 0
        limit = 50

        try:
            # Önce toplam kayıt sayısını bulmak için bir HEAD / GET isteği yapalım
            total_records = 1000 # Tahmini üst limit
            
            while True:
                self.check_pause_and_cancel(log)
                
                endpoint = "/thirdparties"
                params = {
                    "limit": limit,
                    "page": page,
                    "sortfield": "t.rowid",
                    "sortorder": "ASC"
                }
                
                try:
                    thirdparties = self.client._request("GET", endpoint, params=params)
                except Exception as e:
                    err_msg = self.parse_http_error(e)
                    log(f"⚠️ Cariler çekilirken hata oluştu: {err_msg}")
                    break
                    
                if not thirdparties or not isinstance(thirdparties, list):
                    break
                    
                for tp in thirdparties:
                    self.check_pause_and_cancel(log)
                    
                    pulled_count += 1
                    fullname = tp.get("name", "Bilinmeyen Cari")
                    remote_id = str(tp.get("id"))
                    code = tp.get("code_client") or tp.get("code_compta")
                    email = tp.get("email")
                    phone = tp.get("phone")
                    phone2 = tp.get("phone2")
                    phone_home = tp.get("phone_home")
                    fax = tp.get("fax")
                    website = tp.get("url")
                    address = tp.get("address")
                    city = tp.get("town") or tp.get("city")
                    district = tp.get("state_name") or tp.get("county") or ""
                    country = tp.get("country") or ""
                    postcode = tp.get("zip")
                    tax_number = tp.get("tva_assuj") or tp.get("idprof1")
                    tax_office = tp.get("localtax1_assuj") or ""
                    
                    # Çakışma kontrolü
                    existing = self.db.query(Customer).filter(
                        (Customer.remote_id == remote_id) |
                        ((Customer.customer_code == code) & (Customer.customer_code != None))
                    ).first()
                    
                    if existing:
                        if conflict_strategy == "ignore":
                            ignored_count += 1
                            log(f"🟡 Çakışma: {fullname} (Kod: {code}) yerelde zaten var. Atlandı.")
                            continue
                        elif conflict_strategy == "overwrite":
                            # Eski verileri yedekle
                            old_data = {
                                "fullname": existing.fullname,
                                "email": existing.email,
                                "phone": existing.phone,
                                "phone2": existing.phone2,
                                "phone_home": existing.phone_home,
                                "fax": existing.fax,
                                "website": existing.website,
                                "address": existing.address,
                                "city": existing.city,
                                "district": existing.district,
                                "country": existing.country,
                                "postcode": existing.postcode,
                                "tax_office": existing.tax_office,
                                "tax_number": existing.tax_number,
                                "customer_code": existing.customer_code,
                                "status": existing.status,
                                "remote_id": existing.remote_id
                            }
                            
                            undo_log = UndoLog(
                                undo_point_id=undo_point.id,
                                table_name="customers",
                                record_id=existing.id,
                                action="update",
                                old_data=json.dumps(old_data, ensure_ascii=False)
                            )
                            self.db.add(undo_log)
                            
                            # Üzerine yaz
                            existing.fullname = fullname
                            existing.email = email
                            existing.phone = phone
                            existing.phone2 = phone2
                            existing.phone_home = phone_home
                            existing.fax = fax
                            existing.website = website
                            existing.address = address
                            existing.city = city
                            existing.district = district
                            existing.country = country
                            existing.postcode = postcode
                            existing.tax_office = tax_office
                            existing.tax_number = tax_number
                            existing.customer_code = code
                            existing.status = 1
                            existing.remote_id = remote_id
                            
                            updated_count += 1
                            log(f"🟢 Güncellendi (Üzerine Yazıldı): {fullname} (Kod: {code})")
                    else:
                        # Yeni Ekle
                        new_cust = Customer(
                            remote_id=remote_id,
                            marketplace="dolibarr",
                            fullname=fullname,
                            email=email,
                            phone=phone,
                            phone2=phone2,
                            phone_home=phone_home,
                            fax=fax,
                            website=website,
                            address=address,
                            city=city,
                            district=district,
                            country=country,
                            postcode=postcode,
                            tax_office=tax_office,
                            tax_number=tax_number,
                            customer_code=code,
                            status=1
                        )
                        self.db.add(new_cust)
                        self.db.flush()
                        
                        undo_log = UndoLog(
                            undo_point_id=undo_point.id,
                            table_name="customers",
                            record_id=new_cust.id,
                            action="insert",
                            old_data=None
                        )
                        self.db.add(undo_log)
                        
                        added_count += 1
                        log(f"➕ Eklendi: {fullname} (Kod: {code})")
                        
                    # Progress tetikle
                    if progress_callback:
                        progress_callback(pulled_count, total_records)
                        
                if len(thirdparties) < limit:
                    break
                page += 1
                
            self.db.commit()
            log(f"\n🎉 Senkronizasyon Tamamlandı!")
            log(f"Toplam Çekilen: {pulled_count} | Eklenen: {added_count} | Güncellenen: {updated_count} | Atlanan: {ignored_count}")
            return undo_point.id
            
        except InterruptedError as ie:
            self.db.rollback()
            log(f"\n🛑 Senkronizasyon durduruldu: {str(ie)}")
            raise ie
        except Exception as e:
            self.db.rollback()
            log(f"❌ Kritik Hata: {str(e)}")
            raise e

    def push_customers_to_dolibarr(
        self,
        conflict_strategy: str = "ignore", # "ignore" veya "overwrite"
        log_callback: Callable[[str], None] = None,
        progress_callback: Callable[[int, int], None] = None,
        site_id: int = 1,
        selected_ids: list[int] = None
    ) -> int:
        """Yerel yeni/güncellenmiş veya seçili carileri belirtilen Dolibarr ERP sistemine push eder."""
        self.site_id = site_id
        
        # Seçilen sitenin client'ını dinamik ayağa kaldır (eğer önceden mocklanmadıysa)
        if not self.client:
            site = self.db.query(Site).filter(Site.id == site_id).first()
            if not site:
                raise ValueError(f"Site ID {site_id} bulunamadı.")
                
            from src.core.security.keyring_store import get_api_key
            api_key = get_api_key(site.api_key_account)
            self.client = DolibarrClient(base_url=site.url, api_key=api_key)
        else:
            site = self.db.query(Site).filter(Site.id == site_id).first()

        def log(msg: str):
            if log_callback:
                log_callback(msg)
            logger.info(msg)

        log(f"🚀 Yerel cariler [{site.name if site else 'Uzak Sistem'}] sistemine gönderiliyor...")
        
        # Veritabanında status değeri None veya null veya 0 olanları 1 (Aktif) yapalım ki veri bütünlüğü korunsun
        try:
            self.db.execute(text("UPDATE customers SET status = 1 WHERE status IS NULL OR status = 0"))
            self.db.commit()
        except Exception:
            pass

        # Seçili ID'ler varsa sadece onları al
        if selected_ids:
            customers_to_push = self.db.query(Customer).filter(
                Customer.id.in_(selected_ids),
                Customer.is_deleted == False
            ).all()
            log(f"ℹ️ Seçilen {len(customers_to_push)} adet cari gönderiliyor...")
        else:
            # ChangeLog tablosunda bekleyen PENDING_PUSH durumundaki carileri al
            pending_changes = self.db.query(ChangeLog).filter(
                ChangeLog.entity_type == "customer",
                ChangeLog.status == "PENDING_PUSH"
            ).all()
            
            if not pending_changes:
                log("ℹ️ Dolibarr'a gönderilecek bekleyen yeni veya güncellenmiş cari bulunmuyor. Tüm cariler gönderilecek.")
                # Eğer bekleyen log yoksa, veritabanındaki remote_id'si boş olan tüm yerel carileri gönderelim!
                customers_to_push = self.db.query(Customer).filter(
                    Customer.remote_id == None,
                    Customer.is_deleted == False
                ).all()
            else:
                cust_ids = [c.entity_id for c in pending_changes]
                customers_to_push = self.db.query(Customer).filter(Customer.id.in_(cust_ids)).all()
                
        if not customers_to_push:
            log("ℹ️ Gönderilecek cari bulunmuyor.")
            return 0
            
        pushed_count = 0
        error_count = 0
        total_to_push = len(customers_to_push)

        for idx, customer in enumerate(customers_to_push):
            self.check_pause_and_cancel(log)
            
            # 🚀 Hızlı Çakışma Bypass Performans Optimizasyonu
            if customer.remote_id and conflict_strategy == "ignore":
                log(f"🟡 Çakışma: {customer.fullname} zaten uzak sistemle eşleştirilmiş (ID: {customer.remote_id}). Strateji gereği Hızlı Geçildi.")
                pushed_count += 1
                try:
                    change = self.db.query(ChangeLog).filter(
                        ChangeLog.entity_type == "customer",
                        ChangeLog.entity_id == customer.id,
                        ChangeLog.status == "PENDING_PUSH"
                    ).first()
                    if change:
                        change.status = "SUCCESS"
                except Exception:
                    pass
                    
                if progress_callback:
                    progress_callback(idx + 1, total_to_push)
                continue
            
            # Dinamik client/fournisseur tespiti
            client_status = 1
            fournisseur_status = 0
            g_name = (customer.group_name or "").upper()
            if "SATICI" in g_name and "ALICI" in g_name:
                client_status = 1
                fournisseur_status = 1
            elif "SATICI" in g_name:
                client_status = 0
                fournisseur_status = 1
            elif "POTANSİYEL" in g_name:
                client_status = 2
                fournisseur_status = 0
            else:
                client_status = 1
                fournisseur_status = 0

            tp_payload = {
                "name": customer.fullname,
                "client": client_status,
                "fournisseur": fournisseur_status,
                "status": 1  # Dolibarr listelerinde varsayılan olarak görünmesi için her zaman Aktif (1) gönderelim
            }

            # Sadece dolu olan alanları Dolibarr REST API'sine gönder
            if customer.customer_code:
                tp_payload["code_client"] = customer.customer_code
                if fournisseur_status == 1:
                    tp_payload["code_fournisseur"] = customer.customer_code
            if customer.email:
                tp_payload["email"] = customer.email
            if customer.phone:
                tp_payload["phone"] = customer.phone
            if customer.phone2:
                tp_payload["phone2"] = customer.phone2
            if customer.phone_home:
                tp_payload["phone_home"] = customer.phone_home
            if customer.fax:
                tp_payload["fax"] = customer.fax
            if customer.website:
                tp_payload["url"] = customer.website
            if customer.address:
                tp_payload["address"] = customer.address
            if customer.city:
                tp_payload["town"] = customer.city
            if customer.postcode:
                tp_payload["zip"] = customer.postcode
            if customer.tax_number:
                tp_payload["tva_assuj"] = customer.tax_number
            if customer.tax_office:
                tp_payload["localtax1_assuj"] = customer.tax_office
            
            try:
                # 1. Çakışma kontrolü (Eğer remote_id yoksa uzak sunucuda kod veya isimle sorgulama yapalım)
                remote_exists = False
                remote_obj_id = customer.remote_id
                
                if not remote_obj_id:
                    # A. Cari kodu ile sorgula
                    if customer.customer_code:
                        try:
                            search_res = self.client._request("GET", "/thirdparties", params={"sqlfilters": f"t.code_client:=:'{customer.customer_code}'"})
                            if search_res and isinstance(search_res, list) and len(search_res) > 0:
                                remote_obj_id = str(search_res[0].get("id"))
                                remote_exists = True
                        except Exception:
                            pass
                    
                    # B. Cari kodu ile bulunamadıysa Ticari Ünvan (nom) ile sorgula
                    if not remote_obj_id and customer.fullname:
                        try:
                            escaped_name = customer.fullname.replace("'", "''")
                            search_res = self.client._request("GET", "/thirdparties", params={"sqlfilters": f"t.nom:=:'{escaped_name}'"})
                            if search_res and isinstance(search_res, list) and len(search_res) > 0:
                                remote_obj_id = str(search_res[0].get("id"))
                                remote_exists = True
                        except Exception:
                            pass
                
                # Çakışma durumunda strateji uygula
                if remote_exists or customer.remote_id:
                    if conflict_strategy == "ignore" and not customer.remote_id:
                        log(f"🟡 Çakışma: {customer.fullname} uzak sunucuda zaten var. Strateji gereği ATLANDI.")
                        continue
                        
                if not remote_obj_id:
                    # Yeni kayıt oluştur (POST)
                    res = self.client._request("POST", "/thirdparties", json=tp_payload)
                    if res:
                        customer.remote_id = str(res)
                        pushed_count += 1
                        log(f"✅ Gönderildi (Yeni): {customer.fullname}")
                else:
                    # Kaydı güncelle (PUT)
                    url = f"/thirdparties/{remote_obj_id}"
                    self.client._request("PUT", url, json=tp_payload)
                    if not customer.remote_id:
                        customer.remote_id = remote_obj_id
                    pushed_count += 1
                    log(f"✅ Güncellendi (Uzak): {customer.fullname}")
                    
                # ChangeLog durumunu güncelle
                change = self.db.query(ChangeLog).filter(
                    ChangeLog.entity_type == "customer",
                    ChangeLog.entity_id == customer.id,
                    ChangeLog.status == "PENDING_PUSH"
                ).first()
                if change:
                    change.status = "SUCCESS"
                    
            except Exception as e:
                err_msg = self.parse_http_error(e)
                
                # 🛑 Kendi Kendini Onarma Katmanı: Herhangi bir HTTP hatası (400, 500) durumunda çakışma kontrolü ve otomatik düzeltme
                is_http_err = isinstance(e, requests.exceptions.HTTPError) and e.response is not None
                is_code_conflict_msg = "ErrorCustomerCodeAlreadyUsed" in err_msg
                is_bad_syntax_msg = "ErrorBadCustomerCodeSyntax" in err_msg
                
                # Eğer sunucu hatası alındıysa veya açık çakışma hata mesajı geldiyse
                if is_code_conflict_msg or (is_http_err and e.response.status_code in (400, 500)):
                    log(f"⚠️ Sunucu hatası veya çakışma şüphesi algılandı. Dolibarr sunucusundan cari eşleştiriliyor...")
                    found_remote_id = None
                    
                    # A. Cari kodu ile eşleşen var mı arayalım
                    if customer.customer_code:
                        try:
                            search_res = self.client._request("GET", "/thirdparties", params={"sqlfilters": f"t.code_client:=:'{customer.customer_code}'"})
                            if search_res and isinstance(search_res, list) and len(search_res) > 0:
                                found_remote_id = str(search_res[0].get("id"))
                        except Exception:
                            pass
                            
                    # B. Cari adı (fullname) ile eşleşen var mı arayalım
                    if not found_remote_id and customer.fullname:
                        try:
                            escaped_name = customer.fullname.replace("'", "''")
                            search_res = self.client._request("GET", "/thirdparties", params={"sqlfilters": f"t.nom:=:'{escaped_name}'"})
                            if search_res and isinstance(search_res, list) and len(search_res) > 0:
                                found_remote_id = str(search_res[0].get("id"))
                        except Exception:
                            pass
                            
                    if found_remote_id:
                        log(f"🎯 Dolibarr'da eşleşen cari bulundu (ID: {found_remote_id}). İşlem GÜNCELLEME (PUT) olarak otomatik yeniden deneniyor...")
                        try:
                            url = f"/thirdparties/{found_remote_id}"
                            self.client._request("PUT", url, json=tp_payload)
                            customer.remote_id = found_remote_id
                            pushed_count += 1
                            log(f"✅ Çakışma başarıyla giderildi ve güncellendi: {customer.fullname}")
                            
                            # ChangeLog'u temizle
                            change = self.db.query(ChangeLog).filter(
                                ChangeLog.entity_type == "customer",
                                ChangeLog.entity_id == customer.id,
                                ChangeLog.status == "PENDING_PUSH"
                            ).first()
                            if change:
                                change.status = "SUCCESS"
                            continue
                        except Exception as sub_e:
                            log(f"❌ Güncelleme denemesi başarısız oldu: {self.parse_http_error(sub_e)}")

                # 🛑 Kendi Kendini Onarma Katmanı 2: Kod maskesi hatası veya diğer kod kaynaklı reddedilmeler (Bypass)
                if is_bad_syntax_msg or (is_http_err and e.response.status_code in (400, 500) and "code_client" in tp_payload):
                    log(f"⚠️ Cari kod formatı veya sunucu uyumsuzluğu. Cari kod gönderimi kapatılarak otomatik atama deneniyor...")
                    temp_payload = tp_payload.copy()
                    if "code_client" in temp_payload:
                        del temp_payload["code_client"]
                    if "code_fournisseur" in temp_payload:
                        del temp_payload["code_fournisseur"]
                    try:
                        res = self.client._request("POST", "/thirdparties", json=temp_payload)
                        if res:
                            new_id = str(res)
                            customer.remote_id = new_id
                            # Dolibarr'ın otomatik atadığı yeni cari kodunu çekip yerelde güncelleyelim
                            try:
                                tp_detail = self.client._request("GET", f"/thirdparties/{new_id}")
                                if tp_detail and isinstance(tp_detail, dict):
                                    assigned_code = tp_detail.get("code_client") or tp_detail.get("code_compta")
                                    if assigned_code:
                                        customer.customer_code = assigned_code
                                        log(f"ℹ️ Dolibarr'ın otomatik atadığı cari kodu yerelde kaydedildi: {assigned_code}")
                            except Exception:
                                pass
                            pushed_count += 1
                            log(f"✅ Otomatik kod şablonu ile başarıyla gönderildi: {customer.fullname}")
                            
                            # ChangeLog'u temizle
                            change = self.db.query(ChangeLog).filter(
                                ChangeLog.entity_type == "customer",
                                ChangeLog.entity_id == customer.id,
                                ChangeLog.status == "PENDING_PUSH"
                            ).first()
                            if change:
                                change.status = "SUCCESS"
                            continue
                    except Exception as sub_e:
                        log(f"❌ Otomatik kod şablonu denemesi de başarısız oldu: {self.parse_http_error(sub_e)}")

                error_count += 1
                log(f"❌ Hata: {customer.fullname} gönderilemedi! Nedeni: {err_msg}")
                # Ayrıntılı Log Takibi için Payload ve Sunucu Cevabını göster
                try:
                    formatted_payload = json.dumps(tp_payload, indent=2, ensure_ascii=False)
                    log(f"   📋 [Gönderilen Ham Payload]:\n{formatted_payload}")
                except Exception:
                    pass
                if isinstance(e, requests.exceptions.HTTPError) and e.response is not None:
                    log(f"   📥 [Sunucu Hata Detayı (Raw Response)]: {e.response.text}")
                
            if progress_callback:
                progress_callback(idx + 1, total_to_push)
                
        self.db.commit()
        log(f"\n🎉 Push işlemi tamamlandı! Başarılı: {pushed_count} | Hatalı: {error_count}")
        return pushed_count

    def rollback_operation(self, undo_point_id: int, log_callback: Callable[[str], None] = None) -> bool:
        """Belirli bir geri alma noktasındaki (UndoPoint) tüm işlemleri ters sıralamayla geri alır (Rollback)."""
        def log(msg: str):
            if log_callback:
                log_callback(msg)
            logger.info(msg)

        undo_point = self.db.query(UndoPoint).filter(UndoPoint.id == undo_point_id).first()
        if not undo_point:
            log("❌ Hata: Geri alma noktası bulunamadı.")
            return False

        log(f"↩️ Geri Alma İşlemi Başlatıldı: {undo_point.operation_name} (Zaman: {undo_point.created_at})")
        
        undo_logs = self.db.query(UndoLog).filter(UndoLog.undo_point_id == undo_point_id).order_by(UndoLog.id.desc()).all()
        
        rollback_count = 0
        try:
            for undo_log in undo_logs:
                if undo_log.table_name == "customers":
                    customer = self.db.query(Customer).filter(Customer.id == undo_log.record_id).first()
                    
                    if undo_log.action == "insert":
                        if customer:
                            self.db.delete(customer)
                            rollback_count += 1
                            log(f"🗑️ Geri Alındı (Silindi): {customer.fullname}")
                            
                    elif undo_log.action == "update":
                        if customer and undo_log.old_data:
                            old_data = json.loads(undo_log.old_data)
                            customer.fullname = old_data.get("fullname", customer.fullname)
                            customer.email = old_data.get("email")
                            customer.phone = old_data.get("phone")
                            customer.phone2 = old_data.get("phone2")
                            customer.phone_home = old_data.get("phone_home")
                            customer.fax = old_data.get("fax")
                            customer.website = old_data.get("website")
                            customer.address = old_data.get("address")
                            customer.city = old_data.get("city")
                            customer.district = old_data.get("district")
                            customer.country = old_data.get("country")
                            customer.postcode = old_data.get("postcode")
                            customer.tax_office = old_data.get("tax_office")
                            customer.tax_number = old_data.get("tax_number")
                            customer.customer_code = old_data.get("customer_code")
                            customer.status = old_data.get("status", 1)
                            customer.remote_id = old_data.get("remote_id")
                            
                            rollback_count += 1
                            log(f"🔄 Geri Alındı (Eski Veriye Dönüldü): {customer.fullname}")
                            
                    elif undo_log.action == "delete":
                        if customer:
                            customer.is_deleted = False
                            rollback_count += 1
                            log(f"🟢 Geri Alındı (Aktifleştirildi): {customer.fullname}")
                            
            self.db.delete(undo_point)
            self.db.commit()
            log(f"\n✅ Geri alma başarıyla tamamlandı! {rollback_count} satır işlem geri alındı.")
            return True
            
        except Exception as e:
            self.db.rollback()
            log(f"❌ Geri alma sırasında kritik hata: {str(e)}")
            return False
