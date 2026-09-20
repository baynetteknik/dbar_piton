<?php
declare(strict_types=1);
// Müşteri cari hesap özeti: account.php?t=<64 karakterlik token>. Veri /api/v1/a/<token> üzerinden yüklenir.
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
<title>Hesap Özeti</title>
<style>
  :root{--bg:#f8fafc;--card:#fff;--ink:#1e293b;--mut:#64748b;--line:#e2e8f0;--bad:#b91c1c;--ok:#15803d}
  @media (prefers-color-scheme:dark){:root{--bg:#0f172a;--card:#1e293b;--ink:#e2e8f0;--mut:#94a3b8;--line:#334155}}
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
  .wrap{max-width:900px;margin:0 auto;padding:16px}
  .card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px;margin-bottom:14px}
  h1{font-size:20px;margin:0 0 4px}.mut{color:var(--mut);font-size:13px}
  .bal{font-size:26px;font-weight:800;margin-top:8px}
  .bal.debt{color:var(--bad)}.bal.credit{color:var(--ok)}
  table{width:100%;border-collapse:collapse}
  th,td{text-align:left;padding:8px 6px;border-bottom:1px solid var(--line)}
  th{font-size:12px;color:var(--mut);text-transform:uppercase}
  td.n,th.n{text-align:right;white-space:nowrap}
  .banner{padding:10px 14px;border-radius:8px;font-weight:600;background:#fee2e2;color:var(--bad)}
  @media (max-width:560px){.hide-m{display:none}}
</style>
</head>
<body>
<div class="wrap" id="app"><div class="card">Yükleniyor…</div></div>
<script>
(function(){
  var TOKEN = <?= json_encode($valid ? $t : '') ?>;
  var app = document.getElementById('app');
  var MSG = {not_found:'Bu bağlantı bulunamadı.',expired:'Bu bağlantının süresi dolmuş.',revoked:'Bu bağlantı iptal edilmiş.'};
  function el(tag, cls, text){var e=document.createElement(tag);if(cls)e.className=cls;if(text!==undefined)e.textContent=text;return e;}
  function money(v,cur){return Number(v||0).toLocaleString('tr-TR',{minimumFractionDigits:2,maximumFractionDigits:2})+' '+(cur||'');}
  function clear(){while(app.firstChild)app.removeChild(app.firstChild);}
  function fail(code){clear();var c=el('div','card');c.appendChild(el('div','banner',MSG[code]||'Bir hata oluştu.'));app.appendChild(c);}
  function render(d){
    clear();
    var head=el('div','card');
    head.appendChild(el('h1',null,d.customer_name||'Hesap Özeti'));
    head.appendChild(el('div','mut','Durum tarihi: '+(d.as_of||'')));
    var b=Number(d.balance||0);
    var label=b>0?'Borç bakiyesi: ':(b<0?'Alacak bakiyesi: ':'Bakiye: ');
    head.appendChild(el('div','bal '+(b>0?'debt':(b<0?'credit':'')),label+money(Math.abs(b),d.currency)));
    app.appendChild(head);
    var st=d.statement||[];
    var box=el('div','card');
    if(!st.length){box.appendChild(el('div','mut','Listelenecek hareket yok.'));}
    else{
      var tb=el('table');var hr=el('tr');
      [['Tarih',''],['Belge','hide-m'],['Açıklama',''],['Borç','n'],['Alacak','n']].forEach(function(h){hr.appendChild(el('th',h[1],h[0]));});
      tb.appendChild(hr);
      st.forEach(function(r){
        var tr=el('tr');
        tr.appendChild(el('td',null,r.date||''));
        tr.appendChild(el('td','hide-m',r.doc_no||''));
        tr.appendChild(el('td',null,r.description||''));
        tr.appendChild(el('td','n',r.debit?money(r.debit,d.currency):''));
        tr.appendChild(el('td','n',r.credit?money(r.credit,d.currency):''));
        tb.appendChild(tr);
      });
      box.appendChild(tb);
    }
    app.appendChild(box);
  }
  if(!TOKEN){fail('not_found');return;}
  fetch('api/v1/a/'+TOKEN).then(function(r){return r.json();}).then(function(j){j.ok?render(j.data):fail(j.error);}).catch(function(){fail('');});
})();
</script>
</body>
</html>
