<?php
// Alan adının kök dizini (ör. erp.baynetbilisim.tr) şu an `public/` yerine
// doğrudan `portal/` klasörüne bağlı olduğundan, kökte bir index olmayınca
// 404 dönüyordu. Bu dosya yalnızca logo + giriş bağlantısı gösteren, DB'ye
// veya bootstrap.php'ye bağımlı OLMAYAN sade bir karşılama sayfasıdır — bir
// sorun olsa bile (DB, config) bu sayfa yine de açılır.
declare(strict_types=1);
?>
<!doctype html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<title>TOYA ERP Portalı</title>
<style>
:root{--bg:#f8fafc;--card:#fff;--ink:#1e293b;--mut:#64748b;--line:#e2e8f0;--pri:#2563eb}
@media (prefers-color-scheme:dark){:root{--bg:#0f172a;--card:#1e293b;--ink:#e2e8f0;--mut:#94a3b8;--line:#334155}}
*{box-sizing:border-box}
body{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:40px 36px;max-width:380px;width:100%;text-align:center;box-shadow:0 4px 24px rgba(0,0,0,.06)}
.card img{max-width:180px;height:auto;margin-bottom:18px}
h1{font-size:19px;margin:0 0 6px}
p{color:var(--mut);font-size:13px;margin:0 0 22px}
a.btn{display:inline-block;background:var(--pri);color:#fff;text-decoration:none;font-weight:600;padding:11px 26px;border-radius:8px}
a.btn:hover{opacity:.9}
</style>
</head>
<body>
<div class="card">
  <img src="public/assets/toya_logo.png" alt="TOYA">
  <h1>TOYA ERP Portalı</h1>
  <p>Cari ekstresi, teklif ve hesap özeti görüntüleme portalı.</p>
  <a class="btn" href="public/login.php">Portala Giriş Yap</a>
</div>
</body>
</html>
