from pathlib import Path
import shutil, json, hashlib

root = Path('C:/toya_erp')
aidat = Path('C:/xampp/htdocs/toya')
shared = root / 'shared/toya-design'
stage = root / 'scratch/design-integration'
for p in [shared / 'views', shared / 'assets', stage / 'original', stage / 'aidat/site-admin']:
    p.mkdir(parents=True, exist_ok=True)

def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8', newline='\n')

originals = {}
for name in ['sayfa-builder-grapes.php', 'slider-builder.php']:
    src = aidat / 'site-admin' / name
    originals['site-admin/' + name] = hashlib.sha256(src.read_bytes()).hexdigest()
    shutil.copy2(src, stage / 'original' / name)
write(stage / 'original-hashes.json', json.dumps(originals, indent=2))

page = (aidat / 'site-admin/sayfa-builder-grapes.php').read_text(encoding='utf-8-sig')
split = page.index("if (empty($initialHtml)) {\n    $initialHtml = '")
adapter = page[:split]
adapter += """// Shared UI; authentication, template lookup and database writes remain in Aidat.
define('TOYA_DESIGN_HOST', true);
$designAssetBase = '../modules/toya-design/assets';
$designSaveUrl = 'ajax/sayfa-builder-kaydet.php?action=save_grapes';
$designClassicUrl = 'sayfa-builder.php?tur=' . urlencode($tur) . '&id=' . $itemId;
$designSliderUrl = 'slider-builder.php';
$designBaseUrl = '../';
$designCsrf = '';
require __DIR__ . '/../modules/toya-design/views/page.php';
"""
write(stage / 'aidat/site-admin/sayfa-builder-grapes.php', adapter)
view = "<?php\nif (!defined('TOYA_DESIGN_HOST')) { http_response_code(404); exit; }\n" + page[split:]
view = view.replace('href="sayfa-builder.php?tur=<?= urlencode($tur) ?>&id=<?= (int)$itemId ?>"', 'href="<?= htmlspecialchars($designClassicUrl) ?>"')
view = view.replace('href="slider-builder.php"', 'href="<?= htmlspecialchars($designSliderUrl) ?>"')
view = view.replace("const BUILDER_TUR = '<?= $tur ?>';", 'const BUILDER_TUR = <?= json_encode($tur, JSON_HEX_TAG | JSON_HEX_AMP | JSON_HEX_APOS | JSON_HEX_QUOT) ?>;')
view = view.replace('json_encode($initialHtml, JSON_UNESCAPED_UNICODE)', 'json_encode($initialHtml, JSON_HEX_TAG | JSON_HEX_AMP | JSON_HEX_APOS | JSON_HEX_QUOT | JSON_UNESCAPED_UNICODE)')
for var in ['initialCss', 'initialComponents', 'initialStyles']:
    view = view.replace('json_encode($' + var + ')', 'json_encode($' + var + ', JSON_HEX_TAG | JSON_HEX_AMP | JSON_HEX_APOS | JSON_HEX_QUOT)')
view = view.replace("url: 'ajax/sayfa-builder-kaydet.php?action=save_grapes',", 'url: <?= json_encode($designSaveUrl) ?>,\n                    headers: {"X-CSRF-Token": <?= json_encode($designCsrf) ?>},')
view = view.replace('canvas: {', 'canvas: {\n                    customBadgeLabel: "TOYA",')
# Ensure relative links in saved content resolve against the host public site, not the editor URL.
view = view.replace('// Sol Blok Yöneticisi Taşıyıcısı', '// Sol Blok Yöneticisi Taşıyıcısı')
write(shared / 'views/page.php', view)

slider = (aidat / 'site-admin/slider-builder.php').read_text(encoding='utf-8-sig')
split = slider.index('// Varsayılan Katmanlar')
adapter = slider[:split] + """define('TOYA_DESIGN_HOST', true);
$designAssetBase = '../modules/toya-design/assets';
$designSliderUrl = 'slider-builder.php';
$designBackUrl = 'slider.php';
$designPageUrl = 'sayfa-builder.php?tur=cozum';
$designImageBase = '../';
$designCsrf = '';
require __DIR__ . '/../modules/toya-design/views/slider.php';
"""
write(stage / 'aidat/site-admin/slider-builder.php', adapter)
view = "<?php\nif (!defined('TOYA_DESIGN_HOST')) { http_response_code(404); exit; }\n" + slider[split:]
view = view.replace('href="slider.php"', 'href="<?= htmlspecialchars($designBackUrl) ?>"').replace('href="sayfa-builder.php?tur=cozum"', 'href="<?= htmlspecialchars($designPageUrl) ?>"')
view = view.replace('json_encode($initialLayers, JSON_UNESCAPED_UNICODE)', 'json_encode($initialLayers, JSON_HEX_TAG | JSON_HEX_AMP | JSON_HEX_APOS | JSON_HEX_QUOT | JSON_UNESCAPED_UNICODE)')
view = view.replace("'slider-builder.php?action=upload_ajax'", "<?= json_encode($designSliderUrl . '?action=upload_ajax') ?>")
view = view.replace("'slider-builder.php?action=save_ajax'", "<?= json_encode($designSliderUrl . '?action=save_ajax') ?>")
view = view.replace("'slider-builder.php?id='", "<?= json_encode($designSliderUrl . '?id=') ?>")
view = view.replace("type: 'POST',", "type: 'POST',\n                    headers: {'X-CSRF-Token': <?= json_encode($designCsrf) ?>},")
view = view.replace("../<?= htmlspecialchars($currentBg) ?>", "<?= htmlspecialchars($designImageBase . $currentBg) ?>")
# Existing code prefixes local media URLs with ../ in several JavaScript branches.
view = view.replace("'../'", '<?= json_encode($designImageBase) ?>')
write(shared / 'views/slider.php', view)

assets = {
    'assets/smarty/css/core.min.css': 'css/core.min.css',
    'assets/smarty/css/vendor_bundle.min.css': 'css/vendor.min.css',
    'assets/css/baynet-showcase.css': 'css/baynet-showcase.css',
    'assets/smarty/js/vendor_bundle.min.js': 'js/vendor_bundle.min.js',
    'assets/js/toya-grapes-free-layout.js': 'js/toya-grapes-free-layout.js',
}
for src, dest in assets.items():
    (shared / 'assets' / dest).parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(aidat / src, shared / 'assets' / dest)
fonts = aidat / 'assets/smarty/fonts'
shutil.copytree(fonts, shared / 'assets/fonts', dirs_exist_ok=True)
replacements = {
    '../assets/smarty/css/core.min.css': 'css/core.min.css',
    '../assets/smarty/css/vendor.min.css': 'css/vendor.min.css',
    '../assets/css/baynet-showcase.css': 'css/baynet-showcase.css',
    '../assets/smarty/js/vendor_bundle.min.js': 'js/vendor_bundle.min.js',
    '../assets/js/toya-grapes-free-layout.js': 'js/toya-grapes-free-layout.js',
    '../assets/images/placeholder.webp': 'images/placeholder.svg',
}
for name in ['page.php', 'slider.php']:
    path = shared / 'views' / name
    text = path.read_text(encoding='utf-8')
    for old, new in replacements.items():
        text = text.replace(old, "<?= htmlspecialchars($designAssetBase, ENT_QUOTES, 'UTF-8') ?>/" + new)
    write(path, text)
write(shared / 'assets/images/placeholder.svg', '<svg xmlns="http://www.w3.org/2000/svg" width="800" height="500"><rect width="800" height="500" fill="#dce8f6"/><text x="400" y="260" text-anchor="middle" font-family="sans-serif" font-size="34" fill="#334155">TOYA</text></svg>')
write(shared / 'VERSION', '1.0.0\n')
write(shared / '.htaccess', 'Options -Indexes\nRewriteEngine On\nRewriteRule ^(views|lib)(/|$) - [F,L]\n')
print('Shared views extracted; original hashes and untouched controller backups saved.')
