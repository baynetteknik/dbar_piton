<?php
declare(strict_types=1);
// Müşteri teklif sayfası: view.php?t=<64 karakterlik token>. Veri /api/v1/p/<token> üzerinden yüklenir.
$t = (string)($_GET['t'] ?? '');
$valid = preg_match('/^[0-9a-f]{64}$/', $t) === 1;
header('Cache-Control: no-store');
header('X-Robots-Tag: noindex, nofollow');
?><!doctype html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<title>Teklif</title>
<style>
  :root{--bg:#f8fafc;--card:#fff;--ink:#1e293b;--mut:#64748b;--line:#e2e8f0;--pri:#2563eb;--ok:#15803d;--bad:#b91c1c}
  @media (prefers-color-scheme:dark){:root{--bg:#0f172a;--card:#1e293b;--ink:#e2e8f0;--mut:#94a3b8;--line:#334155}}
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
  .wrap{max-width:900px;margin:0 auto;padding:16px}
  .card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px;margin-bottom:14px}
  h1{font-size:20px;margin:0 0 4px}.mut{color:var(--mut);font-size:13px}
  table{width:100%;border-collapse:collapse}
  th,td{text-align:left;padding:8px 6px;border-bottom:1px solid var(--line);vertical-align:top}
  th{font-size:12px;color:var(--mut);text-transform:uppercase}
  td.n,th.n{text-align:right;white-space:nowrap}
  .extras{font-size:12px;color:var(--mut)}
  .total{font-size:18px;font-weight:700;text-align:right;margin-top:10px}
  .banner{padding:10px 14px;border-radius:8px;font-weight:600;margin-bottom:14px}
  .banner.ok{background:#dcfce7;color:var(--ok)}.banner.bad{background:#fee2e2;color:var(--bad)}.banner.info{background:#dbeafe;color:#1e40af}
  .actions{display:flex;flex-wrap:wrap;gap:8px}
  button{font:inherit;font-weight:600;border:0;border-radius:8px;padding:10px 16px;cursor:pointer;color:#fff}
  .b-ok{background:var(--ok)}.b-bad{background:var(--bad)}.b-cnt{background:var(--pri)}
  button:disabled{opacity:.5;cursor:default}
  textarea,input{width:100%;font:inherit;padding:8px;border:1px solid var(--line);border-radius:6px;background:var(--card);color:var(--ink);margin-top:6px}
  .form{display:none;margin-top:12px}.form.show{display:block}
  @media (max-width:560px){.hide-m{display:none}}
</style>
</head>
<body>
<div class="wrap" id="app"><div class="card">Yükleniyor…</div></div>
<script>
(function(){
  var TOKEN = <?= json_encode($valid ? $t : '') ?>;
  var API = 'api/v1/p/' + TOKEN;
  var app = document.getElementById('app');
  var MSG = {not_found:'Bu teklif bulunamadı.',expired:'Bu teklif bağlantısının süresi dolmuş.',revoked:'Bu teklif iptal edilmiş.',already_decided:'Bu teklif için karar zaten verilmiş.',counter_not_allowed:'Karşı teklife izin verilmiyor.',invalid_amount:'Geçerli bir tutar girin.'};
  function el(tag, cls, text){var e=document.createElement(tag);if(cls)e.className=cls;if(text!==undefined)e.textContent=text;return e;}
  function money(v,cur){return Number(v||0).toLocaleString('tr-TR',{minimumFractionDigits:2,maximumFractionDigits:2})+' '+(cur||'');}
  function clear(){while(app.firstChild)app.removeChild(app.firstChild);}
  function fail(code){clear();var c=el('div','card');c.appendChild(el('div','banner bad',MSG[code]||'Bir hata oluştu.'));app.appendChild(c);}

  function render(d){
    clear();
    var head=el('div','card');
    head.appendChild(el('h1',null,d.title||('Teklif '+d.external_ref)));
    head.appendChild(el('div','mut',[d.customer_name,'No: '+d.external_ref,d.valid_until?('Geçerlilik: '+d.valid_until):''].filter(Boolean).join(' · ')));
    app.appendChild(head);

    if(d.status==='accepted')app.appendChild(el('div','banner ok','Bu teklifi kabul ettiniz. Teşekkür ederiz.'));
    else if(d.status==='rejected')app.appendChild(el('div','banner bad','Bu teklifi reddettiniz.'));
    else if(d.action_taken==='countered')app.appendChild(el('div','banner info','Karşı teklifiniz iletildi; yanıt bekleniyor.'));

    var lines=(d.snapshot&&d.snapshot.lines)||[];
    var box=el('div','card');
    var tb=el('table');var thead=el('tr');
    [['Ürün',''],['Miktar','n hide-m'],['Birim Fiyat','n'],['Tutar','n']].forEach(function(h){thead.appendChild(el('th',h[1],h[0]));});
    tb.appendChild(thead);
    lines.forEach(function(l){
      var tr=el('tr');var td=el('td');
      td.appendChild(el('div',null,l.name||''));
      var ex=l.extras||{};
      var parts=Object.keys(ex).map(function(k){return k+': '+ex[k];});
      if(l.note)parts.unshift(l.note);
      if(parts.length)td.appendChild(el('div','extras',parts.join(' · ')));
      tr.appendChild(td);
      tr.appendChild(el('td','n hide-m',(l.qty!=null?l.qty:'')+(l.unit?' '+l.unit:'')));
      tr.appendChild(el('td','n',money(l.unit_price,d.currency)));
      var total=l.total!=null?l.total:(Number(l.qty||0)*Number(l.unit_price||0));
      tr.appendChild(el('td','n',money(total,d.currency)));
      tb.appendChild(tr);
    });
    box.appendChild(tb);
    box.appendChild(el('div','total','Genel Toplam: '+money(d.grand_total,d.currency)));
    app.appendChild(box);

    if(d.status==='published'){
      var act=el('div','card');var row=el('div','actions');
      var bo=el('button','b-ok','✅ Kabul Et'),br=el('button','b-bad','❌ Reddet'),bc=el('button','b-cnt','💰 Karşı Teklif');
      row.appendChild(bo);row.appendChild(br);if(d.allow_counter)row.appendChild(bc);act.appendChild(row);
      var form=el('div','form');var note=el('textarea');note.rows=3;note.placeholder='Not (isteğe bağlı)';
      var amt=el('input');amt.type='number';amt.step='0.01';amt.min='0';amt.placeholder='Önerdiğiniz toplam tutar';
      var send=el('button','b-cnt','Gönder');send.style.marginTop='8px';
      form.appendChild(amt);form.appendChild(note);form.appendChild(send);act.appendChild(form);
      var mode=null;
      function open(m){mode=m;form.classList.add('show');amt.style.display=m==='counter'?'block':'none';
        send.className={accept:'b-ok',reject:'b-bad',counter:'b-cnt'}[m];
        send.textContent={accept:'Kabulü Onayla',reject:'Reddi Onayla',counter:'Karşı Teklifi Gönder'}[m];}
      bo.onclick=function(){open('accept');};br.onclick=function(){open('reject');};bc.onclick=function(){open('counter');};
      send.onclick=function(){
        send.disabled=true;
        var body={note:note.value};if(mode==='counter')body.amount=amt.value;
        fetch(API+'/'+mode,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})
          .then(function(r){return r.json();})
          .then(function(j){if(j.ok)load();else{send.disabled=false;alert(MSG[j.error]||'İşlem başarısız.');}})
          .catch(function(){send.disabled=false;alert('Bağlantı hatası.');});
      };
      app.appendChild(act);
    }
  }
  function load(){
    fetch(API).then(function(r){return r.json();}).then(function(j){j.ok?render(j.data):fail(j.error);}).catch(function(){fail('');});
  }
  if(!TOKEN)fail('not_found');else load();
})();
</script>
</body>
</html>
