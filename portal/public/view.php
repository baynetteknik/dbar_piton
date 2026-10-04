<?php
declare(strict_types=1);
// Müşteri teklif sayfası: view.php?t=<64 karakterlik token>. Veri /api/v1/p/<token> üzerinden yüklenir.
$t = (string)($_GET['t'] ?? '');
$valid = preg_match('/^[0-9a-f]{64}$/', $t) === 1;
header('Cache-Control: no-store');
header('X-Robots-Tag: noindex, nofollow');
header("Content-Security-Policy: default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; frame-ancestors 'none'");
?><!doctype html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<title>Teklif</title>
<style>
  :root{--bg:#f1f5f9;--card:#fff;--ink:#1e293b;--mut:#64748b;--line:#e2e8f0;--pri:#2563eb;--ok:#15803d;--bad:#b91c1c;--soft:#f8fafc}
  @media (prefers-color-scheme:dark){:root{--bg:#0f172a;--card:#1e293b;--ink:#e2e8f0;--mut:#94a3b8;--line:#334155;--soft:#172033}}
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
  .wrap{max-width:960px;margin:0 auto;padding:16px}
  .card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:18px;margin-bottom:14px}
  h1{font-size:22px;margin:0 0 4px}h2{font-size:15px;margin:0 0 8px}.mut{color:var(--mut);font-size:13px}
  .firm{display:flex;flex-wrap:wrap;gap:16px;align-items:center;justify-content:space-between}
  .firm .id{display:flex;gap:14px;align-items:center}.firm img{max-height:64px;max-width:180px;object-fit:contain}
  .firm .name{font-weight:800;font-size:17px}
  .meta{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:10px;margin-top:14px}
  .meta div{background:var(--soft);border:1px solid var(--line);border-radius:8px;padding:8px 10px}
  .meta b{display:block;font-size:11px;color:var(--mut);text-transform:uppercase;letter-spacing:.4px}
  .pill{display:inline-block;padding:2px 10px;border-radius:999px;font-size:12px;font-weight:700;background:#dbeafe;color:#1e40af}
  .pill.warn{background:#fef3c7;color:#92400e}
  table{width:100%;border-collapse:collapse}
  th,td{text-align:left;padding:8px 6px;border-bottom:1px solid var(--line);vertical-align:top}
  th{font-size:12px;color:var(--mut);text-transform:uppercase}
  td.n,th.n{text-align:right;white-space:nowrap}
  .extras{font-size:12px;color:var(--mut)}
  .sums{margin-left:auto;max-width:340px;margin-top:12px}
  .sums div{display:flex;justify-content:space-between;padding:3px 0}
  .sums .g{font-size:19px;font-weight:800;border-top:2px solid var(--line);margin-top:4px;padding-top:8px}
  .banner{padding:10px 14px;border-radius:8px;font-weight:600;margin-bottom:14px}
  .banner.ok{background:#dcfce7;color:var(--ok)}.banner.bad{background:#fee2e2;color:var(--bad)}.banner.info{background:#dbeafe;color:#1e40af}
  .bar{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:14px}
  .actions{display:flex;flex-wrap:wrap;gap:8px}
  button{font:inherit;font-weight:600;border:0;border-radius:8px;padding:10px 16px;cursor:pointer;color:#fff}
  .b-ok{background:var(--ok)}.b-bad{background:var(--bad)}.b-cnt{background:var(--pri)}
  .b-sec{background:var(--card);color:var(--ink);border:1px solid var(--line)}
  button:disabled{opacity:.5;cursor:default}
  textarea,input{width:100%;font:inherit;padding:8px;border:1px solid var(--line);border-radius:6px;background:var(--card);color:var(--ink);margin-top:6px}
  .form{display:none;margin-top:12px}.form.show{display:block}
  dialog{width:min(920px,96vw);max-height:92vh;border:1px solid var(--line);border-radius:12px;padding:0;background:var(--card);color:var(--ink)}
  dialog::backdrop{background:rgba(15,23,42,.55)}
  .dlg-h{display:flex;justify-content:space-between;align-items:center;padding:12px 16px;border-bottom:1px solid var(--line);position:sticky;top:0;background:var(--card)}
  .dlg-b{padding:16px;overflow:auto;max-height:calc(92vh - 60px)}
  .kv{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:6px 18px;margin-bottom:12px}
  .kv span{color:var(--mut);font-size:12px;display:block}
  @media (max-width:560px){.hide-m{display:none}}
  @media print{
    body{background:#fff;color:#000}.bar,.no-print,#actions,dialog{display:none!important}
    .card{border:0;padding:0;box-shadow:none}.wrap{max-width:none;padding:0}
    body.print-report .wrap>*:not(dialog){display:none!important}body.print-report dialog{display:block!important;position:static;width:auto;max-height:none;border:0}
    body.print-report .dlg-h{display:none}body.print-report .dlg-b{max-height:none;overflow:visible}
  }
</style>
</head>
<body>
<div class="wrap" id="app"><div class="card">Yükleniyor…</div></div>
<script>
(function(){
  var TOKEN = <?= json_encode($valid ? $t : '') ?>;
  var API = 'api/v1/p/' + TOKEN;
  var app = document.getElementById('app');
  var MSG = {not_found:'Bu teklif bulunamadı.',expired:'Bu teklifin geçerlilik süresi dolmuştur.',revoked:'Bu teklif iptal edilmiş.',already_decided:'Bu teklif için karar zaten verilmiş.',counter_not_allowed:'Karşı teklife izin verilmiyor.',invalid_amount:'Geçerli bir tutar girin.',counter_already_sent:'Karşı teklifiniz zaten iletildi; yeniden indirim istenemez.'};
  function el(tag, cls, text){var e=document.createElement(tag);if(cls)e.className=cls;if(text!==undefined&&text!==null)e.textContent=text;return e;}
  function num(v){return Number(v||0);}
  function money(v,cur){return num(v).toLocaleString('tr-TR',{minimumFractionDigits:2,maximumFractionDigits:2})+(cur?' '+cur:'');}
  function dateTr(s){if(!s)return '';var m=String(s).match(/^(\d{4})-(\d{2})-(\d{2})/);return m?m[3]+'.'+m[2]+'.'+m[1]:String(s);}
  function clear(n){while(n.firstChild)n.removeChild(n.firstChild);}
  function fail(code){clear(app);var c=el('div','card');c.appendChild(el('div','banner bad',MSG[code]||'Bir hata oluştu.'));app.appendChild(c);}
  function kv(parent,label,value){if(!value)return;var d=el('div');d.appendChild(el('span',null,label));d.appendChild(el('div',null,value));parent.appendChild(d);}

  // Satır hesabı: total = KDV hariç net tutar (TOYA net_tutar); KDV = net * oran
  function calc(d){
    var lines=(d.snapshot&&d.snapshot.lines)||[],vatBy={},net=0,vat=0;
    var rows=lines.map(function(l){
      var n=l.total!=null?num(l.total):num(l.qty)*num(l.unit_price)*(1-num(l.discount_rate)/100);
      var fx=(l.currency&&l.currency!=='TRY')?(num(l.kur)||1):1;       // döviz satırı: toplamlar TL karşılığı üzerinden
      var r=num(l.vat_rate),v=n*fx*r/100;net+=n*fx;vat+=v;vatBy[r]=(vatBy[r]||0)+v;
      return {l:l,net:n,rate:r,vat:v/fx,cur:l.currency||d.currency};
    });
    var t=(d.snapshot&&d.snapshot.totals)||{};
    var grand=t.grand_total!=null&&num(t.grand_total)>0?num(t.grand_total):num(d.grand_total);
    var vatT=(t.vat!=null&&num(t.vat)>0)?num(t.vat):vat;
    return {rows:rows,net:(grand>0?grand-vatT:net),vat:vatT,vatBy:vatBy,discount:num(t.discount),subtotal:t.subtotal!=null?num(t.subtotal):net,grand:grand};
  }

  function firmBlock(d){
    var co=(d.snapshot&&d.snapshot.company)||{};
    var box=el('div','firm'),id=el('div','id');
    if(co.logo&&/^data:image\/(png|jpe?g|gif|webp);base64,/i.test(co.logo)){var im=el('img');im.alt='';im.src=co.logo;id.appendChild(im);}
    var tx=el('div');tx.appendChild(el('div','name',co.name||''));
    var sub=[co.address,co.phone,co.email,co.website].filter(Boolean).join(' · ');
    if(sub)tx.appendChild(el('div','mut',sub));
    var vg=[co.tax_office?co.tax_office+' V.D.':'',co.tax_number?'VKN: '+co.tax_number:''].filter(Boolean).join(' · ');
    if(vg)tx.appendChild(el('div','mut',vg));
    id.appendChild(tx);box.appendChild(id);return box;
  }

  function banksBlock(d){
    var banks=(d.snapshot&&d.snapshot.company&&d.snapshot.company.banks)||[];
    if(!banks.length)return null;
    var b=el('div');b.appendChild(el('h2',null,'Banka Bilgileri'));
    banks.forEach(function(x){b.appendChild(el('div','mut',[x.banka,x.sube,x.para_birimi].filter(Boolean).join(' · ')+'  —  '+x.iban));});
    return b;
  }

  function linesTable(c,d,detailed){
    var tb=el('table'),th=el('tr');
    var cols=detailed?[['#','' ],['Ürün / Hizmet',''],['Miktar','n'],['Birim Fiyat','n'],['İsk. %','n'],['Net Tutar','n'],['KDV %','n'],['KDV','n']]
                     :[['Ürün',''],['Miktar','n hide-m'],['Birim Fiyat','n'],['Tutar','n']];
    cols.forEach(function(h){th.appendChild(el('th',h[1],h[0]));});tb.appendChild(th);
    c.rows.forEach(function(r,i){
      var l=r.l,tr=el('tr'),td=el('td');
      if(detailed)tr.appendChild(el('td',null,String(i+1)));
      td.appendChild(el('div',null,l.name||''));
      var ex=l.extras||{},parts=Object.keys(ex).map(function(k){return k+': '+ex[k];});
      if(l.sku)parts.unshift('Kod: '+l.sku);if(l.note)parts.unshift(l.note);
      if(parts.length)td.appendChild(el('div','extras',parts.join(' · ')));
      tr.appendChild(td);
      var q=(l.qty!=null?l.qty:'')+(l.unit?' '+l.unit:'');
      if(detailed){
        tr.appendChild(el('td','n',q));tr.appendChild(el('td','n',money(l.unit_price,r.cur!==d.currency?r.cur:'')));
        tr.appendChild(el('td','n',num(l.discount_rate)?String(num(l.discount_rate)):'—'));
        tr.appendChild(el('td','n',money(r.net)));tr.appendChild(el('td','n','%'+r.rate));tr.appendChild(el('td','n',money(r.vat)));
      }else{
        tr.appendChild(el('td','n hide-m',q));tr.appendChild(el('td','n',money(l.unit_price,r.cur)));tr.appendChild(el('td','n',money(r.net,r.cur)));
      }
      tb.appendChild(tr);
    });
    return tb;
  }

  function sums(c,d,detailed){
    var s=el('div','sums');
    function row(a,b,cls){var r=el('div',cls||null);r.appendChild(el('span',null,a));r.appendChild(el('b',null,b));s.appendChild(r);}
    if(c.discount>0)row('Toplam iskonto',money(c.discount,d.currency));
    row('KDV hariç toplam',money(c.net,d.currency));
    if(detailed)Object.keys(c.vatBy).sort(function(a,b){return a-b;}).forEach(function(k){row('KDV %'+k,money(c.vatBy[k],d.currency));});
    else row('KDV',money(c.vat,d.currency));
    row('Genel Toplam',money(c.grand,d.currency),'g');
    return s;
  }

  function metaBlock(d){
    var m=el('div','meta');
    function add(a,b){if(!b)return;var x=el('div');x.appendChild(el('b',null,a));x.appendChild(el('span',null,b));m.appendChild(x);}
    add('Teklif No',d.external_ref);add('Müşteri',d.customer_name);add('Düzenleme',dateTr(d.snapshot&&d.snapshot.issue_date));
    var kalan='';
    if(d.valid_until&&d.status==='published'){
      var end=new Date(String(d.valid_until).replace(' ','T')+'Z');if(String(d.valid_until).slice(11,19)==='00:00:00')end=new Date(end.getTime()+86399000);
      var gun=Math.ceil((end-new Date())/86400000);kalan=gun>=0?' ('+(gun===0?'bugün son gün':gun+' gün kaldı')+')':'';
    }
    add('Geçerlilik',dateTr(d.valid_until)+kalan);add('Ödeme',d.snapshot&&d.snapshot.payment_plan);
    return m;
  }

  function csv(d,c){
    var co=(d.snapshot&&d.snapshot.company)||{},out=[];
    function q(v){v=String(v==null?'':v);return /[;"\n]/.test(v)?'"'+v.replace(/"/g,'""')+'"':v;}
    function line(a){out.push(a.map(q).join(';'));}
    line(['Teklif',d.external_ref]);line(['Firma',co.name||'']);line(['Müşteri',d.customer_name||'']);
    line(['Geçerlilik',dateTr(d.valid_until)]);line([]);
    line(['Ürün / Hizmet','Kod','Miktar','Birim','Birim Fiyat','İskonto %','Net Tutar','KDV %','KDV','Para Birimi']);
    c.rows.forEach(function(r){var l=r.l;line([l.name,l.sku||'',l.qty,l.unit||'',num(l.unit_price).toFixed(2).replace('.',','),num(l.discount_rate),r.net.toFixed(2).replace('.',','),r.rate,r.vat.toFixed(2).replace('.',','),d.currency]);});
    line([]);line(['','','','','','KDV hariç toplam','','','',c.net.toFixed(2).replace('.',',')]);
    line(['','','','','','KDV','','','',c.vat.toFixed(2).replace('.',',')]);
    line(['','','','','','Genel Toplam','','','',c.grand.toFixed(2).replace('.',',')]);
    var blob=new Blob(['﻿'+out.join('\r\n')],{type:'text/csv;charset=utf-8'});
    var a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='teklif-'+String(d.external_ref).replace(/[^\w.-]+/g,'_')+'.csv';
    document.body.appendChild(a);a.click();setTimeout(function(){URL.revokeObjectURL(a.href);a.remove();},500);
  }

  function reportDialog(d,c){
    var dlg=el('dialog');var h=el('div','dlg-h');h.appendChild(el('strong',null,'Detaylı Teklif Raporu'));
    var hb=el('div');var pr=el('button','b-cnt','🖨 Yazdır / PDF');pr.style.marginRight='8px';var cl=el('button','b-sec','Kapat');
    hb.appendChild(pr);hb.appendChild(cl);h.appendChild(hb);dlg.appendChild(h);
    var b=el('div','dlg-b');b.appendChild(firmBlock(d));
    var t=el('h1',null,d.title||('Teklif '+d.external_ref));t.style.marginTop='14px';b.appendChild(t);
    var k=el('div','kv');kv(k,'Teklif No',d.external_ref);kv(k,'Müşteri',d.customer_name);kv(k,'Düzenleme tarihi',dateTr(d.snapshot&&d.snapshot.issue_date));
    kv(k,'Geçerlilik',dateTr(d.valid_until));kv(k,'Para birimi',d.currency);kv(k,'Ödeme planı',d.snapshot&&d.snapshot.payment_plan);b.appendChild(k);
    b.appendChild(linesTable(c,d,true));b.appendChild(sums(c,d,true));
    if(d.snapshot&&d.snapshot.notes){var n=el('div');n.style.marginTop='14px';n.appendChild(el('h2',null,'Notlar'));var np=el('div','mut',d.snapshot.notes);np.style.whiteSpace='pre-wrap';n.appendChild(np);b.appendChild(n);}
    var bk=banksBlock(d);if(bk){bk.style.marginTop='14px';b.appendChild(bk);}
    dlg.appendChild(b);
    cl.onclick=function(){dlg.close();};
    pr.onclick=function(){document.body.classList.add('print-report');window.print();};
    window.addEventListener('afterprint',function(){document.body.classList.remove('print-report');});
    return dlg;
  }

  function render(d){
    clear(app);var c=calc(d);
    document.title=(d.title||('Teklif '+d.external_ref));
    var head=el('div','card');head.appendChild(firmBlock(d));
    var t=el('h1',null,d.title||('Teklif '+d.external_ref));t.style.marginTop='16px';head.appendChild(t);head.appendChild(metaBlock(d));
    app.appendChild(head);

    var bar=el('div','bar no-print');
    var bp=el('button','b-sec','📄 PDF İndir / Yazdır'),bx=el('button','b-sec','📊 Excel\'e Aktar'),br=el('button','b-sec','🔍 Detaylı Rapor');
    bp.onclick=function(){document.body.classList.remove('print-report');window.print();};bx.onclick=function(){csv(d,c);};
    bar.appendChild(bp);bar.appendChild(bx);bar.appendChild(br);app.appendChild(bar);
    var dlg=reportDialog(d,c);app.appendChild(dlg);br.onclick=function(){dlg.showModal();};

    if(d.status==='accepted')app.appendChild(el('div','banner ok','Bu teklifi kabul ettiniz. Teşekkür ederiz.'));
    else if(d.status==='rejected')app.appendChild(el('div','banner bad','Bu teklifi reddettiniz.'));
    else if(d.action_taken==='countered')app.appendChild(el('div','banner info','Karşı teklifiniz ('+money(d.counter_amount,d.currency)+') iletildi; yanıt bekleniyor.'));

    var box=el('div','card');box.appendChild(linesTable(c,d,false));box.appendChild(sums(c,d,false));
    if(d.snapshot&&d.snapshot.notes){var n=el('div','mut',d.snapshot.notes);n.style.cssText='margin-top:12px;white-space:pre-wrap';box.appendChild(n);}
    var bk=banksBlock(d);if(bk){bk.style.marginTop='14px';box.appendChild(bk);}
    app.appendChild(box);

    if(d.status==='published'){
      var act=el('div','card');act.id='actions';var row=el('div','actions');
      var bo=el('button','b-ok','✅ Kabul Et'),brj=el('button','b-bad','❌ Reddet'),bc=el('button','b-cnt','💰 Karşı Teklif');
      row.appendChild(bo);row.appendChild(brj);if(d.allow_counter&&d.action_taken!=='countered')row.appendChild(bc);act.appendChild(row);
      var form=el('div','form');var note=el('textarea');note.rows=3;note.placeholder='Not (isteğe bağlı)';
      var amt=el('input');amt.type='number';amt.step='0.01';amt.min='0';amt.placeholder='Önerdiğiniz toplam tutar';
      var send=el('button','b-cnt','Gönder');send.style.marginTop='8px';
      form.appendChild(amt);form.appendChild(note);form.appendChild(send);act.appendChild(form);
      var mode=null;
      function open(m){mode=m;form.classList.add('show');amt.style.display=m==='counter'?'block':'none';
        send.className={accept:'b-ok',reject:'b-bad',counter:'b-cnt'}[m];
        send.textContent={accept:'Kabulü Onayla',reject:'Reddi Onayla',counter:'Karşı Teklifi Gönder'}[m];}
      bo.onclick=function(){open('accept');};brj.onclick=function(){open('reject');};bc.onclick=function(){open('counter');};
      send.onclick=function(){
        send.disabled=true;
        var body={note:note.value};if(mode==='counter')body.amount=amt.value;
        fetch(API+'/'+mode,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})
          .then(function(r){return r.json();})
          .then(function(j){if(j.ok)load();else{send.disabled=false;alert(MSG[j.error]||'İşlem başarısız.');if(j.error==='counter_already_sent'||j.error==='expired')load();}})
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
